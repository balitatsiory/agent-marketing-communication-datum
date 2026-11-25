"""Inscriptions : saisie, formulaire public, Zoom et destinataires de newsletter.

Données personnelles : les journaux ne portent que des identifiants de lignes.
Un effacement vide le nom et l'adresse ; la ligne reste pour que les comptes
restent justes.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import Page, PageParams
from app.core.security import fingerprint
from app.core.storage import Stockage
from app.modules.webinars import queries, service
from app.modules.webinars.constants import (
    APPROVAL_NONE,
    PAGE_IAGORA_FORM,
    REGISTRATION_MODES_ON_ZOOM,
    SOURCE_IAGORA_FORM,
    SOURCE_MANUAL,
    SOURCE_ZOOM_SYNC,
    STATUS_DRAFT,
    STATUS_SCHEDULED,
    ZOOM_PAGE_SIZE,
    ZOOM_PAGES_MAX,
    ZOOM_REGISTRANT_STATUSES,
)
from app.modules.webinars.models import (
    Webinar,
    WebinarRegistration,
    WebinarRegistrationPage,
)
from app.modules.webinars.schemas import (
    NewsletterAudienceItem,
    NewsletterAudienceRead,
    PublicPageRead,
    PublicRegistrationCreate,
    PublicRegistrationRead,
    RegistrantSyncResult,
    RegistrationCreate,
    RegistrationRead,
)
from app.modules.zoom_accounts import service as zoom_accounts_service
from app.modules.zoom_accounts.zoom_client import ZoomClient

logger = logging.getLogger(__name__)

# Une seule réponse, vraie dans tous les cas : Zoom peut refuser l'inscription
# après coup, et l'équipe la retente alors à la main.
MESSAGE_PUBLIC = (
    "Votre inscription est enregistrée. Si le lien d'accès ne vous parvient pas avant "
    "la séance, contactez l'équipe Datum Academy."
)


def _inscrit_sur_zoom(webinaire: Webinar) -> bool:
    """Vrai quand les inscrits doivent être déclarés sur la réunion Zoom."""
    reglages = (webinaire.zoom_snapshot_json or {}).get("settings") or {}
    return (
        webinaire.external_zoom_meeting_id is not None
        and webinaire.id_zoom_accounts is not None
        and webinaire.registration_mode in REGISTRATION_MODES_ON_ZOOM
        and reglages.get("approval_type") != APPROVAL_NONE
    )


async def _declarer_sur_zoom(
    session: AsyncSession,
    client: ZoomClient,
    webinaire: Webinar,
    inscription: WebinarRegistration,
) -> None:
    """`POST /meetings/{meetingId}/registrants`.

    Un refus de Zoom n'annule pas l'inscription : il est consigné sur la ligne,
    et l'envoi peut être retenté.
    """
    assert webinaire.id_zoom_accounts is not None
    try:
        reponse = await zoom_accounts_service.call_api(
            session,
            client,
            webinaire.id_zoom_accounts,
            "POST",
            f"/meetings/{webinaire.external_zoom_meeting_id}/registrants",
            json={
                "email": inscription.email,
                "first_name": inscription.first_name,
                "last_name": inscription.last_name,
            },
        )
    except ApiError as erreur:
        inscription.zoom_error = erreur.message
    else:
        inscription.external_zoom_registrant_id = reponse.get("registrant_id")
        inscription.zoom_join_url = reponse.get("join_url")
        inscription.zoom_status = "approved" if reponse.get("join_url") else "pending"
        inscription.zoom_error = None
    await session.flush()


async def _trouver(
    session: AsyncSession, id_webinars: int, email: str
) -> WebinarRegistration | None:
    requete = select(WebinarRegistration).where(
        WebinarRegistration.id_webinars == id_webinars, WebinarRegistration.email == email
    )
    return (await session.execute(requete)).scalar_one_or_none()


async def _inserer(session: AsyncSession, inscription: WebinarRegistration) -> bool:
    """Ajoute l'inscription. Faux si l'adresse vient d'être inscrite par ailleurs.

    Deux envois simultanés passent tous deux la recherche préalable : l'index
    unique tranche, dans un point de reprise pour garder la transaction.
    """
    try:
        async with session.begin_nested():
            session.add(inscription)
            await session.flush()
    except IntegrityError:
        if await _trouver(session, inscription.id_webinars, inscription.email or "") is None:
            raise
        return False
    return True


async def _est_effacee(session: AsyncSession, id_webinars: int, email: str) -> bool:
    """Vrai quand cette adresse a été effacée de ce webinaire."""
    requete = select(WebinarRegistration.id_webinar_registrations).where(
        WebinarRegistration.id_webinars == id_webinars,
        WebinarRegistration.erased_email_fingerprint == fingerprint(email),
    )
    return (await session.execute(requete)).first() is not None


async def _charger(
    session: AsyncSession, id_webinars: int, id_registration: int
) -> WebinarRegistration:
    inscription = await session.get(WebinarRegistration, id_registration)
    if inscription is None or inscription.id_webinars != id_webinars:
        raise NotFoundError("Inscription introuvable.")
    return inscription


async def _lue(session: AsyncSession, inscription: WebinarRegistration) -> RegistrationRead:
    await session.refresh(inscription)
    return RegistrationRead.model_validate(inscription)


def _accorder(inscription: WebinarRegistration, accord: bool) -> None:
    inscription.has_newsletter_consent = accord
    inscription.consented_at = datetime.now(UTC) if accord else None


async def list_registrations(
    session: AsyncSession, id_webinars: int, params: PageParams
) -> Page[RegistrationRead]:
    """Inscrits d'un webinaire, les plus récents en tête."""
    await service.charger(session, id_webinars)
    condition = WebinarRegistration.id_webinars == id_webinars
    total = (
        await session.execute(
            select(func.count()).select_from(WebinarRegistration).where(condition)
        )
    ).scalar_one()
    lignes = (
        await session.execute(
            select(WebinarRegistration)
            .where(condition)
            .order_by(
                WebinarRegistration.registered_at.desc(),
                WebinarRegistration.id_webinar_registrations.desc(),
            )
            .offset(params.offset)
            .limit(params.size)
        )
    ).scalars()
    return Page.build([RegistrationRead.model_validate(ligne) for ligne in lignes], total, params)


async def add_registration(
    session: AsyncSession,
    client: ZoomClient,
    id_webinars: int,
    donnees: RegistrationCreate,
) -> RegistrationRead:
    """Inscription saisie par l'équipe.

    Raises:
        NotFoundError, ConflictError: adresse déjà inscrite.
    """
    webinaire = await service.charger(session, id_webinars)
    email = str(donnees.email).lower()
    if await _trouver(session, id_webinars, email) is not None:
        raise ConflictError("Cette adresse est déjà inscrite à ce webinaire.")
    inscription = WebinarRegistration(
        id_webinars=id_webinars,
        email=email,
        first_name=donnees.first_name,
        last_name=donnees.last_name,
        source=SOURCE_MANUAL,
    )
    _accorder(inscription, donnees.has_newsletter_consent)
    if not await _inserer(session, inscription):
        raise ConflictError("Cette adresse est déjà inscrite à ce webinaire.")
    if _inscrit_sur_zoom(webinaire):
        await _declarer_sur_zoom(session, client, webinaire, inscription)
    return await _lue(session, inscription)


async def set_consent(
    session: AsyncSession, id_webinars: int, id_registration: int, accord: bool
) -> RegistrationRead:
    """Enregistre ou retire l'accord pour les newsletters."""
    await service.charger(session, id_webinars)
    inscription = await _charger(session, id_webinars, id_registration)
    if inscription.anonymized_at is not None:
        raise ConflictError("Cette inscription a été effacée.")
    _accorder(inscription, accord)
    await session.flush()
    return await _lue(session, inscription)


async def push_registration(
    session: AsyncSession, client: ZoomClient, id_webinars: int, id_registration: int
) -> RegistrationRead:
    """Retente la déclaration d'un inscrit sur Zoom."""
    webinaire = await service.charger(session, id_webinars)
    inscription = await _charger(session, id_webinars, id_registration)
    if inscription.anonymized_at is not None or not _inscrit_sur_zoom(webinaire):
        raise ConflictError("Cette inscription ne peut pas être envoyée à Zoom.")
    await _declarer_sur_zoom(session, client, webinaire, inscription)
    return await _lue(session, inscription)


async def anonymize_registration(
    session: AsyncSession, id_webinars: int, id_registration: int
) -> None:
    """Efface les données personnelles d'un inscrit (la ligne reste comptée).

    L'inscription éventuellement faite sur Zoom n'est pas retirée : IAGORA n'a
    pas ce droit.
    """
    await service.charger(session, id_webinars)
    inscription = await _charger(session, id_webinars, id_registration)
    if inscription.email is not None:
        inscription.erased_email_fingerprint = fingerprint(inscription.email)
    inscription.email = None
    inscription.first_name = None
    inscription.last_name = None
    inscription.zoom_join_url = None
    inscription.external_zoom_registrant_id = None
    inscription.zoom_error = None
    _accorder(inscription, False)
    inscription.anonymized_at = datetime.now(UTC)
    await session.flush()
    logger.info("Inscription %s anonymisée", id_registration)


async def sync_registrants(
    session: AsyncSession, client: ZoomClient, id_webinars: int
) -> RegistrantSyncResult:
    """`GET /meetings/{meetingId}/registrants` : reprend les inscrits de Zoom.

    Les nouveaux venus n'ont pas d'accord pour les newsletters : s'inscrire sur
    la page de Zoom ne le donne pas. Une adresse effacée n'est pas reprise : Zoom
    la garde, IAGORA non.

    Raises:
        ConflictError: pas de réunion Zoom.
        ApiError: refus de Zoom (inscription non activée comprise).
    """
    webinaire = await service.charger(session, id_webinars, verrouiller=True)
    if webinaire.external_zoom_meeting_id is None or webinaire.id_zoom_accounts is None:
        raise ConflictError("Ce webinaire n'a pas de réunion Zoom.")
    resultat = RegistrantSyncResult(found=0, created=0, updated=0)
    for statut in ZOOM_REGISTRANT_STATUSES:
        jeton_page = ""
        for _ in range(ZOOM_PAGES_MAX):
            params: dict[str, str | int] = {"status": statut, "page_size": ZOOM_PAGE_SIZE}
            if jeton_page:
                params["next_page_token"] = jeton_page
            page = await zoom_accounts_service.call_api(
                session,
                client,
                webinaire.id_zoom_accounts,
                "GET",
                f"/meetings/{webinaire.external_zoom_meeting_id}/registrants",
                params=params,
            )
            for inscrit in page.get("registrants") or []:
                email = str(inscrit.get("email") or "").strip().lower()
                if not email:
                    continue
                resultat.found += 1
                inscription = await _trouver(session, id_webinars, email)
                if inscription is None:
                    if await _est_effacee(session, id_webinars, email):
                        continue
                    inscription = WebinarRegistration(
                        id_webinars=id_webinars,
                        email=email,
                        first_name=str(inscrit.get("first_name") or "")[:120] or None,
                        last_name=str(inscrit.get("last_name") or "")[:120] or None,
                        source=SOURCE_ZOOM_SYNC,
                    )
                    inscrit_le = str(inscrit.get("create_time") or "")
                    if inscrit_le:
                        inscription.registered_at = datetime.fromisoformat(inscrit_le)
                    if await _inserer(session, inscription):
                        resultat.created += 1
                    else:
                        inscription = await _trouver(session, id_webinars, email)
                        assert inscription is not None  # _inserer vient de la voir
                        resultat.updated += 1
                else:
                    resultat.updated += 1
                inscription.external_zoom_registrant_id = inscrit.get("id")
                inscription.zoom_join_url = inscrit.get("join_url") or inscription.zoom_join_url
                inscription.zoom_status = statut
                inscription.zoom_error = None
                await session.flush()
            jeton_page = str(page.get("next_page_token") or "")
            if not jeton_page:
                break
    return resultat


async def get_newsletter_audience(
    session: AsyncSession, id_webinars: int
) -> NewsletterAudienceRead:
    """Inscrits à qui une newsletter peut être envoyée : ceux qui ont consenti."""
    webinaire = await service.charger(session, id_webinars)
    lignes = (
        await session.execute(
            select(WebinarRegistration)
            .where(
                WebinarRegistration.id_webinars == id_webinars,
                WebinarRegistration.email.is_not(None),
            )
            .order_by(WebinarRegistration.email)
        )
    ).scalars()
    destinataires: list[NewsletterAudienceItem] = []
    ecartes = 0
    for inscription in lignes:
        if not inscription.has_newsletter_consent:
            ecartes += 1
            continue
        assert inscription.email is not None
        destinataires.append(
            NewsletterAudienceItem(
                email=inscription.email,
                # La variable {{prenom}} des modèles se remplit avec ce champ.
                display_name=inscription.first_name,
            )
        )
    return NewsletterAudienceRead(
        id_webinars=id_webinars,
        title=webinaire.title,
        items=destinataires,
        excluded_without_consent=ecartes,
    )


# ---------------------------------------------------------------------------
# Formulaire public
# ---------------------------------------------------------------------------


async def _page_publique(
    session: AsyncSession, slug: str
) -> tuple[WebinarRegistrationPage, Webinar, bool]:
    """Formulaire, webinaire et ouverture.

    Un brouillon répond « introuvable » : son contenu n'est pas encore public.

    Raises:
        NotFoundError.
    """
    page = (
        await session.execute(
            select(WebinarRegistrationPage).where(
                WebinarRegistrationPage.kind == PAGE_IAGORA_FORM,
                WebinarRegistrationPage.slug == slug,
            )
        )
    ).scalar_one_or_none()
    if page is None or page.id_webinars is None or not page.is_active:
        raise NotFoundError("Page d'inscription introuvable.")
    webinaire = await session.get(Webinar, page.id_webinars)
    if webinaire is None or webinaire.deleted_at is not None:
        raise NotFoundError("Page d'inscription introuvable.")
    statut = queries.est_passe(
        await service.code_statut(session, webinaire),
        webinaire.starts_at,
        webinaire.duration_minutes,
    )
    if statut == STATUS_DRAFT:
        raise NotFoundError("Page d'inscription introuvable.")
    return page, webinaire, statut == STATUS_SCHEDULED


async def get_public_page(session: AsyncSession, stockage: Stockage, slug: str) -> PublicPageRead:
    """Ce qu'affiche le formulaire public."""
    _, webinaire, ouvert = await _page_publique(session, slug)
    return PublicPageRead(
        title=webinaire.title,
        description=webinaire.description,
        starts_at=webinaire.starts_at,
        is_time_known=webinaire.is_time_known,
        duration_minutes=webinaire.duration_minutes,
        flyer_url=queries.adresse_flyer(webinaire, stockage),
        is_open=ouvert,
    )


async def register_from_public_page(
    session: AsyncSession, client: ZoomClient, slug: str, donnees: PublicRegistrationCreate
) -> PublicRegistrationRead:
    """Inscription anonyme.

    La réponse est la même que l'adresse soit nouvelle ou déjà inscrite, et ne
    porte aucun lien personnel : sinon, saisir l'adresse d'autrui suffirait à
    apprendre qu'elle est inscrite, ou à obtenir son lien.

    Raises:
        NotFoundError, ConflictError: inscriptions closes.
    """
    page, webinaire, ouvert = await _page_publique(session, slug)
    if not ouvert:
        raise ConflictError("Les inscriptions à ce webinaire sont closes.")
    reponse = PublicRegistrationRead(message=MESSAGE_PUBLIC)
    if donnees.website:  # robot : on répond comme à une personne, sans rien garder
        return reponse

    email = str(donnees.email).lower()
    if await _trouver(session, webinaire.id_webinars, email) is None:
        inscription = WebinarRegistration(
            id_webinars=webinaire.id_webinars,
            id_webinar_registration_pages=page.id_webinar_registration_pages,
            email=email,
            first_name=donnees.first_name,
            last_name=donnees.last_name,
            source=SOURCE_IAGORA_FORM,
        )
        _accorder(inscription, donnees.has_newsletter_consent)
        if await _inserer(session, inscription):
            if _inscrit_sur_zoom(webinaire):
                await _declarer_sur_zoom(session, client, webinaire, inscription)
            logger.info("Inscription %s reçue", inscription.id_webinar_registrations)
    return reponse
