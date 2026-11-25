"""Règles métier des fiches webinaires : liste, détail, statistiques, écritures.

La création de la réunion sur Zoom et la synchronisation vivent dans
`zoom_service.py`, les inscriptions dans `registration_service.py`.
"""

import logging
import re
import secrets
import unicodedata
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import Page, PageParams
from app.core.storage import Stockage
from app.modules.platforms import service as platforms_service
from app.modules.users.models import User
from app.modules.webinars import queries
from app.modules.webinars.constants import (
    APPROVAL_NONE,
    LINK_MANUAL,
    LINK_ZOOM_AUTO,
    ORIGIN_MANUAL,
    ORIGIN_SITE_IMPORT,
    PAGE_IAGORA_FORM,
    PUBLICATION_TYPES_AFTER_EVENT,
    REGISTRATION_EXTERNAL,
    REGISTRATION_IAGORA_FORM,
    REGISTRATION_NONE,
    REGISTRATION_SERIES_DAYS,
    REGISTRATION_ZOOM_PAGE,
    STATUS_CANCELLED,
    STATUS_DRAFT,
    STATUS_PAST,
    STATUS_SCHEDULED,
    TYPE_SITE_WEBINAR,
    TYPE_ZOOM_MEETING,
)
from app.modules.webinars.models import (
    Webinar,
    WebinarCategory,
    WebinarCategoryLink,
    WebinarPublicationLink,
    WebinarPublicationType,
    WebinarRegistration,
    WebinarRegistrationPage,
    WebinarStatus,
    WebinarType,
)
from app.modules.webinars.queries import WebinarFilters
from app.modules.webinars.schemas import (
    AccountStats,
    CountItem,
    DailyCount,
    MeetingSettings,
    MonthCount,
    PublicationLinkCreate,
    PublicationLinkRead,
    RefItem,
    RegistrationPageRead,
    SortDirection,
    SortKey,
    WebinarCreate,
    WebinarDetailRead,
    WebinarListItem,
    WebinarReferenceRead,
    WebinarStatsRead,
    WebinarUpdate,
)
from app.modules.zoom_accounts import service as zoom_accounts_service

logger = logging.getLogger(__name__)

# Champs que Zoom détient une fois la réunion créée. IAGORA n'a pas le droit de
# la modifier (`meeting:update` n'est pas demandé) : les changer ici seulement
# ferait mentir la fiche.
CHAMPS_DETENUS_PAR_ZOOM = (
    "title",
    "description",
    "starts_at",
    "duration_minutes",
    "timezone",
    "link_mode",
    "id_zoom_accounts",
    "join_url",
    "meeting_settings",
)


# ---------------------------------------------------------------------------
# Référentiels et petites aides
# ---------------------------------------------------------------------------


async def id_statut(session: AsyncSession, code: str) -> int:
    requete = select(WebinarStatus.id_webinar_statuses).where(WebinarStatus.code == code)
    return (await session.execute(requete)).scalar_one()


async def id_type(session: AsyncSession, code: str) -> int:
    requete = select(WebinarType.id_webinar_types).where(WebinarType.code == code)
    return (await session.execute(requete)).scalar_one()


async def code_statut(session: AsyncSession, webinaire: Webinar) -> str:
    statut = await session.get(WebinarStatus, webinaire.id_webinar_statuses)
    assert statut is not None  # garanti par la clé étrangère
    return statut.code


async def charger(session: AsyncSession, id_webinars: int, verrouiller: bool = False) -> Webinar:
    """Fiche non archivée.

    `verrouiller` réserve la fiche jusqu'à la fin de la transaction : une autre
    écriture attend, mais une inscription passe. Le verrou est tenu pendant les
    appels à Zoom, d'où `FOR NO KEY UPDATE` et non `FOR UPDATE`, qui bloquerait
    toute ligne rattachée.

    Raises:
        NotFoundError: webinaire inconnu ou archivé.
    """
    requete = select(Webinar).where(
        Webinar.id_webinars == id_webinars, Webinar.deleted_at.is_(None)
    )
    if verrouiller:
        requete = requete.with_for_update(key_share=True)
    webinaire = (await session.execute(requete)).scalar_one_or_none()
    if webinaire is None:
        raise NotFoundError("Webinaire introuvable.")
    return webinaire


async def get_reference(session: AsyncSession) -> WebinarReferenceRead:
    """Listes de valeurs des écrans Webinaires."""

    async def lire(
        modele: type[WebinarStatus | WebinarType | WebinarCategory | WebinarPublicationType],
    ) -> list[RefItem]:
        lignes = await session.execute(
            select(modele.code, modele.label).order_by(modele.sort_order, modele.label)
        )
        return [RefItem(code=code, label=label) for code, label in lignes.all()]

    return WebinarReferenceRead(
        statuses=await lire(WebinarStatus),
        types=await lire(WebinarType),
        categories=await lire(WebinarCategory),
        publication_types=await lire(WebinarPublicationType),
        platforms=[
            RefItem(code=reseau.code, label=reseau.label)
            for reseau in await platforms_service.list_platforms(session)
        ],
    )


# ---------------------------------------------------------------------------
# Liste et détail
# ---------------------------------------------------------------------------


async def list_webinars(
    session: AsyncSession,
    stockage: Stockage,
    filtres: WebinarFilters,
    params: PageParams,
    tri: SortKey = "date",
    sens: SortDirection = "desc",
) -> Page[WebinarListItem]:
    """Une page de webinaires, filtrée et ordonnée."""
    requete = queries.appliquer_filtres(queries.requete_de_base(), filtres)
    total = (
        await session.execute(select(func.count()).select_from(requete.subquery()))
    ).scalar_one()
    lignes = await queries.lire_lignes(
        session, queries.trier(requete, tri, sens).offset(params.offset).limit(params.size)
    )
    fiches = await queries.mettre_en_forme(session, stockage, lignes)
    return Page.build(fiches, total, params)


async def _pages_lues(session: AsyncSession, condition: Any) -> list[RegistrationPageRead]:
    """Pages d'inscription correspondant à une condition, avec les titres liés."""
    pages = (
        (
            await session.execute(
                select(WebinarRegistrationPage)
                .where(condition)
                .order_by(WebinarRegistrationPage.kind.desc(), WebinarRegistrationPage.slug)
            )
        )
        .scalars()
        .all()
    )
    identifiants = {
        identifiant
        for page in pages
        for identifiant in (page.id_webinars, page.id_webinars_candidate)
        if identifiant is not None
    }
    titres: dict[int, str] = {}
    if identifiants:
        lignes = await session.execute(
            select(Webinar.id_webinars, Webinar.title).where(Webinar.id_webinars.in_(identifiants))
        )
        titres = dict(lignes.all())
    return [
        RegistrationPageRead(
            id_webinar_registration_pages=page.id_webinar_registration_pages,
            kind=page.kind,
            slug=page.slug,
            url=page.url,
            is_active=page.is_active,
            id_webinars=page.id_webinars,
            webinar_title=titres.get(page.id_webinars) if page.id_webinars else None,
            id_webinars_candidate=page.id_webinars_candidate,
            candidate_title=(
                titres.get(page.id_webinars_candidate) if page.id_webinars_candidate else None
            ),
            candidate_score=(
                float(page.candidate_score) if page.candidate_score is not None else None
            ),
            event_starts_at=page.event_starts_at,
            event_ends_at=page.event_ends_at,
            note=page.note,
        )
        for page in pages
    ]


async def _liens_publications(session: AsyncSession, id_webinars: int) -> list[PublicationLinkRead]:
    lignes = (
        await session.execute(
            select(WebinarPublicationLink, WebinarPublicationType, User)
            .join(
                WebinarPublicationType,
                WebinarPublicationType.id_webinar_publication_types
                == WebinarPublicationLink.id_webinar_publication_types,
            )
            .outerjoin(User, User.id_users == WebinarPublicationLink.id_users_created_by)
            .where(WebinarPublicationLink.id_webinars == id_webinars)
            .order_by(
                WebinarPublicationType.sort_order,
                WebinarPublicationLink.id_webinar_publication_links,
            )
        )
    ).all()
    reseaux = {
        reseau.id_social_platforms: reseau
        for reseau in await platforms_service.list_platforms(session)
    }
    resultat = []
    for lien, type_publication, auteur in lignes:
        reseau = reseaux.get(lien.id_social_platforms) if lien.id_social_platforms else None
        resultat.append(
            PublicationLinkRead(
                id_webinar_publication_links=lien.id_webinar_publication_links,
                type_code=type_publication.code,
                type_label=type_publication.label,
                platform_code=reseau.code if reseau else None,
                platform_label=reseau.label if reseau else None,
                url=lien.url,
                label=lien.label,
                created_by_name=auteur.nom_affiche if auteur else None,
                created_at=lien.created_at,
            )
        )
    return resultat


async def _courbe_inscriptions(session: AsyncSession, id_webinars: int) -> list[DailyCount]:
    """Inscriptions par jour sur les 30 jours qui précèdent la dernière. Vide sans inscrit."""
    dates = (
        (
            await session.execute(
                select(WebinarRegistration.registered_at).where(
                    WebinarRegistration.id_webinars == id_webinars
                )
            )
        )
        .scalars()
        .all()
    )
    if not dates:
        return []
    par_jour = Counter(quand.astimezone(UTC).date() for quand in dates)
    dernier = max(par_jour)
    debut = dernier - timedelta(days=REGISTRATION_SERIES_DAYS - 1)
    return [
        DailyCount(day=debut + timedelta(days=i), count=par_jour.get(debut + timedelta(days=i), 0))
        for i in range(REGISTRATION_SERIES_DAYS)
    ]


async def get_webinar(
    session: AsyncSession, stockage: Stockage, id_webinars: int, can_manage: bool = False
) -> WebinarDetailRead:
    """Fiche complète.

    Args:
        can_manage: vrai pour qui peut gérer les webinaires ; lui seul voit les
            réglages de la réunion, mot de passe compris.

    Raises:
        NotFoundError: webinaire inconnu ou archivé.
    """
    webinaire = await charger(session, id_webinars)
    # `updated_at` est posé par un déclencheur : on relit la ligne.
    await session.refresh(webinaire)
    lignes = await queries.lire_lignes(
        session, queries.requete_de_base().where(Webinar.id_webinars == id_webinars)
    )
    fiche = (await queries.mettre_en_forme(session, stockage, lignes))[0]
    auteur = (
        await session.get(User, webinaire.id_users_created_by)
        if webinaire.id_users_created_by
        else None
    )
    details = webinaire.import_details_json or {}
    inscrits = await queries.inscriptions_par_webinaire(session, [id_webinars])
    reglages = webinaire.meeting_settings_json
    return WebinarDetailRead(
        **fiche.model_dump(),
        title_en=webinaire.title_en,
        description=webinaire.description,
        description_en=webinaire.description_en,
        timezone=webinaire.timezone,
        link_mode=webinaire.link_mode,  # type: ignore[arg-type]
        meeting_settings=(
            MeetingSettings.model_validate(reglages) if reglages and can_manage else None
        ),
        zoom_meeting=webinaire.zoom_snapshot_json,
        zoom_synced_at=webinaire.zoom_synced_at,
        source_url=webinaire.source_url,
        flyer_source_url=webinaire.flyer_source_url,
        flyer_error=webinaire.flyer_error,
        anomalies=list(details.get("anomalies") or []),
        date_hint=None if webinaire.is_date_confirmed else details.get("date_source"),
        registration_pages=await _pages_lues(
            session,
            (WebinarRegistrationPage.id_webinars == id_webinars)
            | (
                (WebinarRegistrationPage.id_webinars_candidate == id_webinars)
                & WebinarRegistrationPage.id_webinars.is_(None)
            ),
        ),
        publication_links=await _liens_publications(session, id_webinars),
        consented_count=inscrits.get(id_webinars, (0, 0))[1],
        registration_series=await _courbe_inscriptions(session, id_webinars),
        created_by_name=auteur.nom_affiche if auteur else None,
        created_at=webinaire.created_at,
        updated_at=webinaire.updated_at,
    )


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


async def get_stats(
    session: AsyncSession, stockage: Stockage, filtres: WebinarFilters
) -> WebinarStatsRead:
    """Chiffres généraux sur les webinaires retenus par les filtres."""
    lignes = await queries.lire_lignes(
        session, queries.appliquer_filtres(queries.requete_de_base(), filtres)
    )
    reference = await get_reference(session)
    identifiants = [webinaire.id_webinars for webinaire, _, _ in lignes]
    categories = await queries.categories_par_webinaire(session, identifiants)
    inscriptions = await queries.inscriptions_par_webinaire(session, identifiants)

    statuts: Counter[str] = Counter()
    types: Counter[str] = Counter()
    themes: Counter[str] = Counter()
    mois: Counter[str] = Counter()
    par_compte: dict[int | None, Counter[str]] = {}
    avec_replay = a_confirmer = flyers = 0
    prochain: queries.Ligne | None = None
    prochaine_date: datetime | None = None

    for webinaire, statut, type_evenement in lignes:
        code = queries.est_passe(statut.code, webinaire.starts_at, webinaire.duration_minutes)
        statuts[code] += 1
        types[type_evenement.code] += 1
        for categorie in categories.get(webinaire.id_webinars, []):
            themes[categorie.code] += 1
        quand = webinaire.starts_at or webinaire.published_on
        if quand is not None:
            mois[f"{quand:%Y-%m}"] += 1
        par_compte.setdefault(webinaire.id_zoom_accounts, Counter())[code] += 1
        avec_replay += bool(webinaire.replay_url)
        a_confirmer += not webinaire.is_date_confirmed
        flyers += bool(webinaire.flyer_source_url and not webinaire.flyer_storage_key)
        debut = webinaire.starts_at
        if (
            code == STATUS_SCHEDULED
            and debut is not None
            and (prochaine_date is None or debut < prochaine_date)
        ):
            prochain, prochaine_date = (webinaire, statut, type_evenement), debut

    comptes = await zoom_accounts_service.list_labels(session)
    return WebinarStatsRead(
        total=len(lignes),
        scheduled=statuts[STATUS_SCHEDULED],
        past=statuts[STATUS_PAST],
        draft=statuts[STATUS_DRAFT],
        cancelled=statuts[STATUS_CANCELLED],
        by_type=[
            CountItem(code=t.code, label=t.label, count=types[t.code]) for t in reference.types
        ],
        by_category=[
            CountItem(code=c.code, label=c.label, count=themes[c.code])
            for c in reference.categories
        ],
        by_month=[MonthCount(month=cle, count=mois[cle]) for cle in sorted(mois)],
        accounts=[
            AccountStats(
                id_zoom_accounts=identifiant,
                label=(
                    comptes.get(identifiant, "Compte inconnu")
                    if identifiant is not None
                    else "Sans compte Zoom"
                ),
                total=sum(compte.values()),
                scheduled=compte[STATUS_SCHEDULED],
                past=compte[STATUS_PAST],
                draft=compte[STATUS_DRAFT],
            )
            for identifiant, compte in sorted(
                par_compte.items(), key=lambda paire: -sum(paire[1].values())
            )
        ],
        registrations=sum(total for total, _ in inscriptions.values()),
        consented_registrations=sum(accord for _, accord in inscriptions.values()),
        with_replay=avec_replay,
        dates_to_confirm=a_confirmer,
        pending_flyers=flyers,
        next_webinar=(
            (await queries.mettre_en_forme(session, stockage, [prochain]))[0] if prochain else None
        ),
    )


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


async def definir_categories(session: AsyncSession, id_webinars: int, codes: list[str]) -> None:
    """Remplace les catégories d'une fiche.

    Raises:
        ApiError: code de catégorie inconnu.
    """
    lignes = await session.execute(
        select(WebinarCategory.code, WebinarCategory.id_webinar_categories).where(
            WebinarCategory.code.in_(codes)
        )
    )
    connues = dict(lignes.all())
    inconnues = sorted(set(codes) - set(connues))
    if inconnues:
        raise ApiError("unknown_category", f"Catégorie inconnue : {', '.join(inconnues)}.", 422)
    await session.execute(
        delete(WebinarCategoryLink).where(WebinarCategoryLink.id_webinars == id_webinars)
    )
    for identifiant in connues.values():
        session.add(WebinarCategoryLink(id_webinars=id_webinars, id_webinar_categories=identifiant))
    await session.flush()


def _slug(titre: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:80].strip("-")
    # Le suffixe aléatoire distingue deux titres identiques et rend l'adresse
    # d'un formulaire non ouvert difficile à deviner.
    return f"{base or 'webinaire'}-{secrets.token_hex(3)}"


async def appliquer_inscription(session: AsyncSession, webinaire: Webinar) -> None:
    """Met le formulaire IAGORA et l'adresse d'inscription en accord avec le mode choisi."""
    formulaire = (
        await session.execute(
            select(WebinarRegistrationPage).where(
                WebinarRegistrationPage.id_webinars == webinaire.id_webinars,
                WebinarRegistrationPage.kind == PAGE_IAGORA_FORM,
            )
        )
    ).scalar_one_or_none()
    mode = webinaire.registration_mode
    if mode == REGISTRATION_IAGORA_FORM:
        if formulaire is None:
            session.add(
                WebinarRegistrationPage(
                    id_webinars=webinaire.id_webinars,
                    kind=PAGE_IAGORA_FORM,
                    slug=_slug(webinaire.title),
                )
            )
        else:
            formulaire.is_active = True
    elif formulaire is not None:
        formulaire.is_active = False

    if mode in (REGISTRATION_NONE, REGISTRATION_IAGORA_FORM):
        webinaire.registration_url = None
    elif mode == REGISTRATION_ZOOM_PAGE:
        snapshot = webinaire.zoom_snapshot_json or {}
        webinaire.registration_url = snapshot.get("registration_url")
    await session.flush()


def _verifier_inscription(webinaire: Webinar) -> None:
    """Le mode d'inscription doit pouvoir fonctionner avec la réunion telle qu'elle est."""
    if webinaire.registration_mode != REGISTRATION_ZOOM_PAGE:
        return
    if webinaire.link_mode == LINK_MANUAL:
        raise ApiError(
            "zoom_registration_unavailable",
            "La page d'inscription Zoom suppose une réunion créée sur Zoom.",
            422,
        )
    reglages = (webinaire.zoom_snapshot_json or {}).get("settings") or {}
    if webinaire.external_zoom_meeting_id and reglages.get("approval_type") == APPROVAL_NONE:
        raise ConflictError(
            "Cette réunion Zoom n'a pas d'inscription activée, et IAGORA n'a pas le droit "
            "de la modifier : l'activer sur zoom.us puis actualiser la fiche."
        )


async def create_webinar(
    session: AsyncSession, stockage: Stockage, donnees: WebinarCreate, par: User
) -> WebinarDetailRead:
    """Crée un brouillon.

    Raises:
        NotFoundError: compte Zoom inconnu.
        ApiError: catégorie, rôle de publication ou réseau inconnu.
    """
    if donnees.id_zoom_accounts is not None:
        await zoom_accounts_service.get_host_email(session, donnees.id_zoom_accounts)
    webinaire = Webinar(
        id_webinar_statuses=await id_statut(session, STATUS_DRAFT),
        id_webinar_types=await id_type(
            session,
            TYPE_SITE_WEBINAR if donnees.link_mode == LINK_MANUAL else TYPE_ZOOM_MEETING,
        ),
        origin=ORIGIN_MANUAL,
        title=donnees.title,
        description=donnees.description or None,
        starts_at=donnees.starts_at,
        duration_minutes=donnees.duration_minutes,
        timezone=donnees.timezone,
        link_mode=donnees.link_mode,
        id_zoom_accounts=(donnees.id_zoom_accounts if donnees.link_mode != LINK_MANUAL else None),
        join_url=donnees.join_url if donnees.link_mode == LINK_MANUAL else None,
        registration_mode=donnees.registration_mode,
        registration_url=(
            donnees.registration_url if donnees.registration_mode == REGISTRATION_EXTERNAL else None
        ),
        replay_url=donnees.replay_url,
        meeting_settings_json=donnees.meeting_settings.model_dump(),
        id_users_created_by=par.id_users,
        id_users_changed_by=par.id_users,
    )
    _verifier_inscription(webinaire)
    session.add(webinaire)
    await session.flush()
    await definir_categories(session, webinaire.id_webinars, donnees.category_codes)
    await appliquer_inscription(session, webinaire)
    for lien in donnees.publication_links:
        await _ajouter_lien(session, webinaire, lien, par)
    logger.info("Webinaire %s créé en brouillon", webinaire.id_webinars)
    return await get_webinar(session, stockage, webinaire.id_webinars, can_manage=True)


def _refuser_si_detenu_par_zoom(webinaire: Webinar, champs: dict[str, Any]) -> None:
    if webinaire.external_zoom_meeting_id is None:
        return
    actuels = {nom: getattr(webinaire, nom, None) for nom in CHAMPS_DETENUS_PAR_ZOOM}
    actuels["meeting_settings"] = webinaire.meeting_settings_json
    changes = [
        nom for nom in CHAMPS_DETENUS_PAR_ZOOM if nom in champs and champs[nom] != actuels[nom]
    ]
    if changes:
        raise ApiError(
            "managed_by_zoom",
            "Titre, date, durée et lien de cette réunion se modifient sur zoom.us : "
            "IAGORA n'a pas le droit de la changer. Actualiser ensuite la fiche.",
            409,
        )


async def update_webinar(
    session: AsyncSession,
    stockage: Stockage,
    id_webinars: int,
    donnees: WebinarUpdate,
    par: User,
) -> WebinarDetailRead:
    """Modifie les champs envoyés.

    Raises:
        NotFoundError, ApiError (`managed_by_zoom`, catégorie inconnue), ConflictError.
    """
    webinaire = await charger(session, id_webinars, verrouiller=True)
    champs = donnees.model_dump(exclude_unset=True)
    categories = champs.pop("category_codes", None)
    # Ces colonnes ne sont pas nullables : un `null` envoyé veut dire « inchangé ».
    for nom in ("title", "link_mode", "registration_mode", "is_date_confirmed"):
        if champs.get(nom) is None:
            champs.pop(nom, None)
    _refuser_si_detenu_par_zoom(webinaire, champs)
    # La réunion ne se crée qu'à la validation d'un brouillon : une fiche déjà
    # validée passée en « Zoom » resterait sans réunion ni lien.
    if (
        champs.get("link_mode") == LINK_ZOOM_AUTO
        and webinaire.link_mode != LINK_ZOOM_AUTO
        and await code_statut(session, webinaire) != STATUS_DRAFT
    ):
        raise ConflictError(
            "Ce webinaire est déjà validé : sa réunion Zoom ne peut plus être créée "
            "depuis IAGORA. Créer un nouveau webinaire, ou garder un lien fourni."
        )
    if champs.get("id_zoom_accounts") is not None:
        await zoom_accounts_service.get_host_email(session, champs["id_zoom_accounts"])

    if "meeting_settings" in champs:
        webinaire.meeting_settings_json = champs.pop("meeting_settings")
    if "starts_at" in champs and champs["starts_at"] != webinaire.starts_at:
        # Une date saisie à la main vaut confirmation.
        webinaire.is_date_confirmed = champs["starts_at"] is not None
        webinaire.is_time_known = True
    for nom, valeur in champs.items():
        setattr(webinaire, nom, valeur)

    if webinaire.external_zoom_meeting_id is None and "link_mode" in champs:
        manuel = webinaire.link_mode == LINK_MANUAL
        if not manuel:
            webinaire.join_url = None
        if webinaire.origin == ORIGIN_MANUAL:
            webinaire.id_webinar_types = await id_type(
                session, TYPE_SITE_WEBINAR if manuel else TYPE_ZOOM_MEETING
            )

    if webinaire.link_mode == LINK_MANUAL:
        webinaire.id_zoom_accounts = None

    statut = await code_statut(session, webinaire)
    if statut == STATUS_SCHEDULED and webinaire.origin == ORIGIN_MANUAL:
        manquants = await elements_manquants(session, webinaire, exiger_futur=False)
        if manquants:
            raise ConflictError(f"Un webinaire programmé garde : {', '.join(manquants)}.")
    _verifier_inscription(webinaire)
    webinaire.id_users_changed_by = par.id_users
    await session.flush()
    if categories is not None:
        await definir_categories(session, id_webinars, categories)
    if "registration_mode" in champs or "registration_url" in champs:
        await appliquer_inscription(session, webinaire)
    return await get_webinar(session, stockage, id_webinars, can_manage=True)


async def elements_manquants(
    session: AsyncSession, webinaire: Webinar, exiger_futur: bool = True
) -> list[str]:
    """Ce qui manque à une fiche pour être programmée."""
    manquants: list[str] = []
    if webinaire.origin != ORIGIN_SITE_IMPORT:
        categories = await queries.categories_par_webinaire(session, [webinaire.id_webinars])
        if exiger_futur and not categories:
            manquants.append("au moins une catégorie")
    if webinaire.starts_at is None:
        manquants.append("une date et une heure")
    elif exiger_futur and webinaire.starts_at <= datetime.now(UTC):
        manquants.append("une date dans le futur")
    if webinaire.link_mode == LINK_MANUAL:
        if not (webinaire.join_url or "").startswith("https://"):
            manquants.append("un lien de visioconférence en https")
    elif webinaire.id_zoom_accounts is None:
        manquants.append("un compte Zoom")
    if webinaire.registration_mode == REGISTRATION_EXTERNAL and not webinaire.registration_url:
        manquants.append("l'adresse de la page d'inscription")
    return manquants


async def archive_webinar(session: AsyncSession, id_webinars: int, par: User) -> None:
    """Archive la fiche et ferme ses formulaires. La réunion Zoom n'est pas touchée."""
    webinaire = await charger(session, id_webinars, verrouiller=True)
    webinaire.deleted_at = datetime.now(UTC)
    webinaire.id_users_changed_by = par.id_users
    pages = await session.execute(
        select(WebinarRegistrationPage).where(
            WebinarRegistrationPage.id_webinars == id_webinars,
            WebinarRegistrationPage.kind == PAGE_IAGORA_FORM,
        )
    )
    for page in pages.scalars():
        page.is_active = False
    await session.flush()
    logger.info("Webinaire %s archivé", id_webinars)


# ---------------------------------------------------------------------------
# Publications liées
# ---------------------------------------------------------------------------


async def _ajouter_lien(
    session: AsyncSession, webinaire: Webinar, donnees: PublicationLinkCreate, par: User
) -> None:
    type_publication = (
        await session.execute(
            select(WebinarPublicationType).where(WebinarPublicationType.code == donnees.type_code)
        )
    ).scalar_one_or_none()
    if type_publication is None:
        raise ApiError("unknown_publication_type", "Rôle de publication inconnu.", 422)
    if type_publication.code in PUBLICATION_TYPES_AFTER_EVENT:
        statut = queries.est_passe(
            await code_statut(session, webinaire),
            webinaire.starts_at,
            webinaire.duration_minutes,
        )
        if statut != STATUS_PAST:
            raise ConflictError("Compte rendu et rediffusion ne se lient qu'à un webinaire passé.")
    id_reseau = None
    if donnees.platform_code:
        reseaux = {r.code: r for r in await platforms_service.list_platforms(session)}
        if donnees.platform_code not in reseaux:
            raise ApiError("unknown_platform", "Réseau inconnu.", 422)
        id_reseau = reseaux[donnees.platform_code].id_social_platforms
    deja = await session.execute(
        select(WebinarPublicationLink.id_webinar_publication_links).where(
            WebinarPublicationLink.id_webinars == webinaire.id_webinars,
            WebinarPublicationLink.url == donnees.url,
        )
    )
    if deja.first() is not None:
        raise ConflictError("Cette publication est déjà liée à ce webinaire.")
    session.add(
        WebinarPublicationLink(
            id_webinars=webinaire.id_webinars,
            id_webinar_publication_types=type_publication.id_webinar_publication_types,
            id_social_platforms=id_reseau,
            url=donnees.url,
            label=donnees.label or None,
            id_users_created_by=par.id_users,
        )
    )
    await session.flush()


async def add_publication_link(
    session: AsyncSession, id_webinars: int, donnees: PublicationLinkCreate, par: User
) -> list[PublicationLinkRead]:
    """Lie une publication à un webinaire.

    Raises:
        NotFoundError, ConflictError (doublon, rôle impossible), ApiError.
    """
    webinaire = await charger(session, id_webinars)
    await _ajouter_lien(session, webinaire, donnees, par)
    return await _liens_publications(session, id_webinars)


async def remove_publication_link(session: AsyncSession, id_webinars: int, id_link: int) -> None:
    await charger(session, id_webinars)
    lien = await session.get(WebinarPublicationLink, id_link)
    if lien is None or lien.id_webinars != id_webinars:
        raise NotFoundError("Lien de publication introuvable.")
    await session.delete(lien)
    await session.flush()


# ---------------------------------------------------------------------------
# Pages d'inscription
# ---------------------------------------------------------------------------


async def list_registration_pages(
    session: AsyncSession, unlinked_only: bool = False
) -> list[RegistrationPageRead]:
    """Toutes les pages d'inscription, ou seulement celles sans webinaire."""
    condition = WebinarRegistrationPage.id_webinar_registration_pages.is_not(None)
    if unlinked_only:
        condition = WebinarRegistrationPage.id_webinars.is_(None)
    return await _pages_lues(session, condition)


async def link_registration_page(
    session: AsyncSession, id_page: int, id_webinars: int | None, par: User
) -> RegistrationPageRead:
    """Rattache une page externe à un webinaire (validation d'un candidat comprise).

    Raises:
        NotFoundError, ConflictError: un formulaire IAGORA ne se déplace pas.
    """
    page = await session.get(WebinarRegistrationPage, id_page)
    if page is None:
        raise NotFoundError("Page d'inscription introuvable.")
    if page.kind == PAGE_IAGORA_FORM:
        raise ConflictError("Un formulaire IAGORA reste attaché à son webinaire.")
    precedent = page.id_webinars
    if precedent is not None and precedent != id_webinars:
        # La page quitte cette fiche : son adresse ne doit pas y rester.
        ancien = await session.get(Webinar, precedent)
        if ancien is not None and ancien.registration_url == page.url:
            ancien.registration_mode = REGISTRATION_NONE
            ancien.registration_url = None
            ancien.id_users_changed_by = par.id_users
    if id_webinars is not None:
        webinaire = await charger(session, id_webinars, verrouiller=True)
        if webinaire.registration_mode == REGISTRATION_NONE and page.url:
            webinaire.registration_mode = REGISTRATION_EXTERNAL
            webinaire.registration_url = page.url
        # Un rattachement validé à la main : un nouvel import ne le défera pas.
        webinaire.id_users_changed_by = par.id_users
    page.id_webinars = id_webinars
    await session.flush()
    return (
        await _pages_lues(session, WebinarRegistrationPage.id_webinar_registration_pages == id_page)
    )[0]
