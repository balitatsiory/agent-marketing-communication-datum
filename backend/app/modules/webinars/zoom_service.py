"""Échanges avec Zoom : créer une réunion, synchroniser, lire une fiche.

Aucun appel direct à Zoom ici : tout passe par `zoom_accounts.service.call_api`.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, PermissionDeniedError
from app.core.storage import Stockage
from app.modules.users.models import User
from app.modules.webinars import service
from app.modules.webinars.constants import (
    APPROVAL_AUTOMATIC,
    APPROVAL_NONE,
    CREATE_ZOOM_MEETINGS,
    LINK_ZOOM_AUTO,
    ORIGIN_ZOOM_SYNC,
    REGISTRATION_MODES_ON_ZOOM,
    REGISTRATION_NONE,
    REGISTRATION_ZOOM_PAGE,
    STATUS_DRAFT,
    STATUS_SCHEDULED,
    TYPE_ZOOM_MEETING,
    ZOOM_AGENDA_MAX,
    ZOOM_LIST_TYPES,
    ZOOM_MEETING_TYPE_SCHEDULED,
    ZOOM_PAGE_SIZE,
    ZOOM_PAGES_MAX,
    ZOOM_TOPIC_MAX,
)
from app.modules.webinars.models import Webinar
from app.modules.webinars.schemas import (
    MeetingSettings,
    WebinarDetailRead,
    ZoomSyncAccountResult,
    ZoomSyncResult,
)
from app.modules.zoom_accounts import service as zoom_accounts_service
from app.modules.zoom_accounts.zoom_client import ZoomClient

logger = logging.getLogger(__name__)

# Seuls ces champs de Zoom sont conservés. Ni `start_url` — il permet de démarrer
# la réunion à la place de l'hôte — ni les mots de passe n'entrent en base.
CHAMPS_CONSERVES = (
    "id",
    "uuid",
    "host_email",
    "topic",
    "type",
    "status",
    "start_time",
    "duration",
    "timezone",
    "agenda",
    "created_at",
    "join_url",
    "registration_url",
)
REGLAGES_CONSERVES = (
    "approval_type",
    "host_video",
    "participant_video",
    "join_before_host",
    "mute_upon_entry",
    "waiting_room",
    "auto_recording",
    "audio",
    "meeting_authentication",
    "registrants_email_notification",
)


def nettoyer(reunion: dict[str, Any]) -> dict[str, Any]:
    """Fiche Zoom réduite aux champs que l'on peut montrer et garder."""
    fiche = {nom: reunion[nom] for nom in CHAMPS_CONSERVES if nom in reunion}
    reglages = reunion.get("settings")
    if isinstance(reglages, dict):
        fiche["settings"] = {nom: reglages[nom] for nom in REGLAGES_CONSERVES if nom in reglages}
    if isinstance(reunion.get("occurrences"), list):
        fiche["occurrence_count"] = len(reunion["occurrences"])
    return fiche


def _lire_date(valeur: object) -> datetime | None:
    if not isinstance(valeur, str) or not valeur:
        return None
    try:
        lue = datetime.fromisoformat(valeur)
    except ValueError:
        return None
    return lue if lue.tzinfo else lue.replace(tzinfo=UTC)


def _entier(valeur: object) -> int | None:
    return valeur if isinstance(valeur, int) and valeur > 0 else None


def _reporter_description(webinaire: Webinar, agenda: str, complet: bool) -> None:
    """L'ordre du jour de Zoom fait foi, sauf quand le texte reçu est tronqué."""
    locale = webinaire.description or ""
    if complet:
        # La fiche complète dit tout, y compris que le texte a été vidé. Seul un
        # texte plus long que la limite de Zoom reste celui saisi ici.
        if not (len(agenda) >= ZOOM_AGENDA_MAX and locale.startswith(agenda)):
            webinaire.description = agenda or None
    elif agenda and not locale.startswith(agenda):
        # La liste des réunions tronque : un début du texte connu ne le remplace pas.
        webinaire.description = agenda


def _reporter(webinaire: Webinar, reunion: dict[str, Any], complet: bool = False) -> None:
    """Recopie sur la fiche ce dont Zoom est la référence.

    `complet` distingue la fiche d'une réunion de sa ligne dans la liste.
    """
    sujet = str(reunion.get("topic") or "").strip()
    if sujet:
        webinaire.title = sujet[:255]
    agenda = str(reunion.get("agenda") or "").strip()
    _reporter_description(webinaire, agenda, complet)
    debut = _lire_date(reunion.get("start_time"))
    if debut is not None:
        webinaire.starts_at = debut
        webinaire.is_date_confirmed = True
        webinaire.is_time_known = True
    webinaire.duration_minutes = _entier(reunion.get("duration")) or webinaire.duration_minutes
    webinaire.timezone = str(reunion.get("timezone") or "")[:64] or webinaire.timezone
    webinaire.join_url = reunion.get("join_url") or webinaire.join_url
    webinaire.external_zoom_uuid = str(reunion.get("uuid") or "")[:64] or None
    webinaire.zoom_meeting_type = _entier(reunion.get("type"))
    webinaire.zoom_synced_at = datetime.now(UTC)


def _reporter_fiche(webinaire: Webinar, reunion: dict[str, Any]) -> None:
    """Comme `_reporter`, depuis la fiche complète : elle porte aussi les réglages."""
    _reporter(webinaire, reunion, complet=True)
    webinaire.zoom_snapshot_json = nettoyer(reunion)
    adresse = reunion.get("registration_url")
    if adresse and webinaire.registration_mode == REGISTRATION_NONE:
        webinaire.registration_mode = REGISTRATION_ZOOM_PAGE
    if webinaire.registration_mode == REGISTRATION_ZOOM_PAGE:
        webinaire.registration_url = adresse


# ---------------------------------------------------------------------------
# Programmation
# ---------------------------------------------------------------------------


def _demande(webinaire: Webinar) -> dict[str, Any]:
    """Corps de `POST /users/{userId}/meetings`."""
    reglages = MeetingSettings.model_validate(webinaire.meeting_settings_json or {})
    assert webinaire.starts_at is not None  # vérifié par elements_manquants
    inscription = webinaire.registration_mode in REGISTRATION_MODES_ON_ZOOM
    corps: dict[str, Any] = {
        "topic": webinaire.title[:ZOOM_TOPIC_MAX],
        "type": ZOOM_MEETING_TYPE_SCHEDULED,
        # Le « Z » final dit à Zoom que l'heure est en UTC ; `timezone` ne sert
        # alors qu'à l'affichage.
        "start_time": f"{webinaire.starts_at.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}",
        "timezone": webinaire.timezone or "UTC",
        "settings": {
            "host_video": reglages.host_video,
            "participant_video": reglages.participant_video,
            "join_before_host": reglages.join_before_host,
            "mute_upon_entry": reglages.mute_upon_entry,
            "waiting_room": reglages.waiting_room,
            "auto_recording": reglages.auto_recording,
            "approval_type": APPROVAL_AUTOMATIC if inscription else APPROVAL_NONE,
            "registrants_email_notification": reglages.email_notification,
        },
    }
    if webinaire.duration_minutes:
        corps["duration"] = webinaire.duration_minutes
    if webinaire.description:
        corps["agenda"] = webinaire.description[:ZOOM_AGENDA_MAX]
    if reglages.passcode:
        corps["password"] = reglages.passcode
    return corps


async def _reunion_deja_creee(
    session: AsyncSession,
    client: ZoomClient,
    webinaire: Webinar,
    hote: str,
) -> dict[str, Any] | None:
    """Réunion laissée par un essai dont la réponse s'est perdue, s'il y en a une.

    Zoom peut avoir créé la réunion alors qu'IAGORA n'en a rien su (délai
    dépassé, coupure). Une réunion de même titre à la même heure, rattachée à
    aucune fiche, est reprise au lieu d'en créer une seconde.
    """
    assert webinaire.id_zoom_accounts is not None and webinaire.starts_at is not None
    voulu = webinaire.title[:ZOOM_TOPIC_MAX].strip()
    debut = webinaire.starts_at.replace(second=0, microsecond=0)
    reunions = await _lister_reunions(
        session, client, webinaire.id_zoom_accounts, hote, genres=("scheduled",)
    )
    for meeting_id, reunion in reunions.items():
        quand = _lire_date(reunion.get("start_time"))
        if (
            str(reunion.get("topic") or "").strip() == voulu
            and quand is not None
            and quand.replace(second=0, microsecond=0) == debut
            and await _trouver_par_reunion(session, meeting_id) is None
        ):
            fiche = await _fiche_zoom(session, client, webinaire.id_zoom_accounts, meeting_id)
            reglages = fiche.get("settings") or {}
            if (
                webinaire.registration_mode in REGISTRATION_MODES_ON_ZOOM
                and reglages.get("approval_type") == APPROVAL_NONE
            ):
                raise ConflictError(
                    f"Une réunion identique existe déjà sur Zoom (n° {meeting_id}), sans "
                    "inscription. L'activer ou la supprimer sur zoom.us, puis valider."
                )
            return fiche
    return None


async def schedule_webinar(
    session: AsyncSession,
    client: ZoomClient,
    stockage: Stockage,
    id_webinars: int,
    par: User,
    can_create_meetings: bool,
) -> WebinarDetailRead:
    """Valide un brouillon : crée la réunion sur Zoom si le lien est automatique.

    La fiche est réservée pendant l'appel : deux clics rapprochés ne créent pas
    deux réunions. Un essai précédent resté sans réponse est repris.

    Raises:
        ConflictError: la fiche n'est pas un brouillon, ou il y manque quelque chose.
        PermissionDeniedError: réunion Zoom sans le droit de la créer.
        ApiError: refus de Zoom.
    """
    webinaire = await service.charger(session, id_webinars, verrouiller=True)
    if await service.code_statut(session, webinaire) != STATUS_DRAFT:
        raise ConflictError("Seul un brouillon peut être validé.")
    manquants = await service.elements_manquants(session, webinaire)
    if manquants:
        raise ApiError("webinar_incomplete", f"Il manque : {', '.join(manquants)}.", 409)

    if webinaire.link_mode == LINK_ZOOM_AUTO and webinaire.external_zoom_meeting_id is None:
        if not can_create_meetings:
            raise PermissionDeniedError(f"Ce geste demande le droit « {CREATE_ZOOM_MEETINGS} ».")
        assert webinaire.id_zoom_accounts is not None  # vérifié par elements_manquants
        hote = await zoom_accounts_service.get_host_email(session, webinaire.id_zoom_accounts)
        reunion = await _reunion_deja_creee(session, client, webinaire, hote)
        if reunion is None:
            reunion = await zoom_accounts_service.call_api(
                session,
                client,
                webinaire.id_zoom_accounts,
                "POST",
                f"/users/{hote}/meetings",
                json=_demande(webinaire),
            )
        if not isinstance(reunion.get("id"), int):
            raise ApiError("zoom_unavailable", "Réponse de Zoom sans numéro de réunion.", 502)
        description = webinaire.description
        webinaire.external_zoom_meeting_id = reunion["id"]
        _reporter_fiche(webinaire, reunion)
        # La saisie de l'utilisateur reste la référence si Zoom a tronqué le texte.
        webinaire.description = description
        # Le mot de passe a servi : il est désormais dans le lien d'accès, et
        # n'a plus à être conservé.
        webinaire.meeting_settings_json = {
            **(webinaire.meeting_settings_json or {}),
            "passcode": None,
        }
        logger.info("Webinaire %s : réunion Zoom créée", id_webinars)

    webinaire.id_webinar_statuses = await service.id_statut(session, STATUS_SCHEDULED)
    webinaire.id_users_changed_by = par.id_users
    await session.flush()
    await service.appliquer_inscription(session, webinaire)
    return await service.get_webinar(session, stockage, id_webinars, can_manage=True)


# ---------------------------------------------------------------------------
# Lecture et synchronisation
# ---------------------------------------------------------------------------


async def _fiche_zoom(
    session: AsyncSession, client: ZoomClient, id_zoom_accounts: int, meeting_id: int
) -> dict[str, Any]:
    """`GET /meetings/{meetingId}`."""
    return await zoom_accounts_service.call_api(
        session, client, id_zoom_accounts, "GET", f"/meetings/{meeting_id}"
    )


async def refresh_from_zoom(
    session: AsyncSession, client: ZoomClient, stockage: Stockage, id_webinars: int
) -> WebinarDetailRead:
    """Relit la réunion sur Zoom et met la fiche à jour.

    Raises:
        ConflictError: la fiche n'a pas de réunion Zoom.
        ApiError: refus de Zoom (réunion supprimée ou expirée comprise).
    """
    webinaire = await service.charger(session, id_webinars, verrouiller=True)
    if webinaire.external_zoom_meeting_id is None or webinaire.id_zoom_accounts is None:
        raise ConflictError("Ce webinaire n'a pas de réunion Zoom à relire.")
    reunion = await _fiche_zoom(
        session, client, webinaire.id_zoom_accounts, webinaire.external_zoom_meeting_id
    )
    _reporter_fiche(webinaire, reunion)
    await session.flush()
    await service.appliquer_inscription(session, webinaire)
    return await service.get_webinar(session, stockage, id_webinars, can_manage=True)


async def _trouver_par_reunion(session: AsyncSession, meeting_id: int) -> Webinar | None:
    """Fiche liée à ce numéro, archivée comprise."""
    requete = select(Webinar).where(Webinar.external_zoom_meeting_id == meeting_id)
    return (await session.execute(requete)).scalar_one_or_none()


async def _nouvelle_fiche(
    session: AsyncSession, id_zoom_accounts: int, meeting_id: int, par: User
) -> Webinar:
    return Webinar(
        id_webinar_statuses=await service.id_statut(session, STATUS_SCHEDULED),
        id_webinar_types=await service.id_type(session, TYPE_ZOOM_MEETING),
        id_zoom_accounts=id_zoom_accounts,
        origin=ORIGIN_ZOOM_SYNC,
        link_mode=LINK_ZOOM_AUTO,
        external_zoom_meeting_id=meeting_id,
        title=f"Réunion {meeting_id}",
        id_users_created_by=par.id_users,
    )


async def import_meeting(
    session: AsyncSession,
    client: ZoomClient,
    stockage: Stockage,
    id_zoom_accounts: int,
    meeting_id: int,
    par: User,
) -> WebinarDetailRead:
    """Ajoute (ou actualise) la fiche d'une réunion désignée par son numéro.

    Raises:
        ConflictError: la fiche de cette réunion a été archivée.
        ApiError: refus de Zoom.
    """
    webinaire = await _trouver_par_reunion(session, meeting_id)
    if webinaire is not None and webinaire.deleted_at is not None:
        raise ConflictError("La fiche de cette réunion a été archivée.")
    reunion = await _fiche_zoom(session, client, id_zoom_accounts, meeting_id)
    if webinaire is None:
        webinaire = await _nouvelle_fiche(session, id_zoom_accounts, meeting_id, par)
        session.add(webinaire)
    webinaire.id_zoom_accounts = id_zoom_accounts
    _reporter_fiche(webinaire, reunion)
    await session.flush()
    await service.appliquer_inscription(session, webinaire)
    return await service.get_webinar(session, stockage, webinaire.id_webinars, can_manage=True)


async def _lister_reunions(
    session: AsyncSession,
    client: ZoomClient,
    id_zoom_accounts: int,
    hote: str,
    genres: tuple[str, ...] = ZOOM_LIST_TYPES,
) -> dict[int, dict[str, Any]]:
    """Réunions de l'hôte, une entrée par numéro, toutes pages comprises."""
    reunions: dict[int, dict[str, Any]] = {}
    for genre in genres:
        jeton_page = ""
        for _ in range(ZOOM_PAGES_MAX):
            params: dict[str, str | int] = {"type": genre, "page_size": ZOOM_PAGE_SIZE}
            if jeton_page:
                params["next_page_token"] = jeton_page
            page = await zoom_accounts_service.call_api(
                session,
                client,
                id_zoom_accounts,
                "GET",
                f"/users/{hote}/meetings",
                params=params,
            )
            for reunion in page.get("meetings") or []:
                # Une réunion récurrente revient une fois par séance : on garde
                # la première lue, la prochaine à venir.
                if isinstance(reunion, dict) and isinstance(reunion.get("id"), int):
                    reunions.setdefault(reunion["id"], reunion)
            jeton_page = str(page.get("next_page_token") or "")
            if not jeton_page:
                break
    return reunions


async def sync_meetings(
    session: AsyncSession, client: ZoomClient, id_zoom_accounts: int | None, par: User
) -> ZoomSyncResult:
    """Reprend les réunions d'un compte, ou de tous.

    Un compte qui échoue n'empêche pas les autres : son message est rapporté.
    Rien n'est supprimé : une réunion expirée sur Zoom reste dans l'historique.
    """
    comptes = await zoom_accounts_service.list_accounts(session)
    if id_zoom_accounts is not None:
        comptes = [c for c in comptes if c.id_zoom_accounts == id_zoom_accounts]
        if not comptes:
            await zoom_accounts_service.get_host_email(session, id_zoom_accounts)

    resultats: list[ZoomSyncAccountResult] = []
    for compte in comptes:
        resultat = ZoomSyncAccountResult(
            id_zoom_accounts=compte.id_zoom_accounts, label=compte.label, ok=True, message=""
        )
        try:
            reunions = await _lister_reunions(
                session, client, compte.id_zoom_accounts, compte.host_email
            )
        except ApiError as erreur:
            resultat.ok = False
            resultat.message = erreur.message
            resultats.append(resultat)
            continue

        resultat.found = len(reunions)
        for meeting_id, reunion in reunions.items():
            webinaire = await _trouver_par_reunion(session, meeting_id)
            if webinaire is None:
                webinaire = await _nouvelle_fiche(session, compte.id_zoom_accounts, meeting_id, par)
                session.add(webinaire)
                resultat.created += 1
            elif webinaire.deleted_at is not None:
                continue
            else:
                resultat.updated += 1
            webinaire.id_zoom_accounts = compte.id_zoom_accounts
            _reporter(webinaire, reunion)
        await session.flush()
        resultat.message = (
            f"{resultat.found} réunion(s) lue(s), {resultat.created} ajoutée(s), "
            f"{resultat.updated} actualisée(s)."
        )
        resultats.append(resultat)
    return ZoomSyncResult(accounts=resultats)
