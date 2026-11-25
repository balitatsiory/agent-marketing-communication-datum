"""Routes du module Webinaires. Aucune règle métier ici."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.deps import SessionDep
from app.core.errors import ApiError
from app.core.pagination import Page, PageParams, page_params
from app.core.storage import Stockage, get_stockage
from app.modules.users.deps import CurrentUser, codes_de, require
from app.modules.users.models import User
from app.modules.webinars import (
    flyers,
    importer,
    registration_export,
    registration_service,
    service,
    zoom_service,
)
from app.modules.webinars.constants import (
    CREATE_ZOOM_MEETINGS,
    FLYER_BATCH_MAX,
    FLYER_MAX_BYTES,
    IMPORT_FILE_MAX_BYTES,
    MANAGE_WEBINARS,
)
from app.modules.webinars.import_schemas import FlyerManifest, PagesExport, SiteExport
from app.modules.webinars.queries import WebinarFilters
from app.modules.webinars.schemas import (
    FlyerBatchResult,
    ImportReport,
    NewsletterAudienceRead,
    PublicationLinkCreate,
    PublicationLinkRead,
    PublicPageRead,
    PublicRegistrationCreate,
    PublicRegistrationRead,
    RegistrantSyncResult,
    RegistrationCreate,
    RegistrationPageLink,
    RegistrationPageRead,
    RegistrationRead,
    RegistrationUpdate,
    SortDirection,
    SortKey,
    WebinarCreate,
    WebinarDetailRead,
    WebinarListItem,
    WebinarReferenceRead,
    WebinarStatsRead,
    WebinarUpdate,
    ZoomMeetingImport,
    ZoomSyncRequest,
    ZoomSyncResult,
)
from app.modules.zoom_accounts.zoom_client import ZoomClient, get_zoom_client

router = APIRouter(prefix="/webinars", tags=["webinaires"])
public_router = APIRouter(prefix="/public/registration-pages", tags=["inscription-publique"])

GestionnaireWebinaires = Annotated[User, Depends(require(MANAGE_WEBINARS))]
ZoomDep = Annotated[ZoomClient, Depends(get_zoom_client)]
StockageDep = Annotated[Stockage, Depends(get_stockage)]
FlyerTransportDep = Annotated[httpx.AsyncBaseTransport | None, Depends(flyers.get_flyer_transport)]
PaginationDep = Annotated[PageParams, Depends(page_params)]


def filtres(
    status_code: Annotated[str | None, Query(alias="status")] = None,
    type_code: Annotated[str | None, Query(alias="type")] = None,
    category: str | None = None,
    id_zoom_accounts: int | None = None,
    unassigned: Annotated[bool, Query(description="Sans compte Zoom.")] = False,
    search: Annotated[str | None, Query(alias="q", max_length=200)] = None,
) -> WebinarFilters:
    return WebinarFilters(
        status=status_code,
        type_code=type_code,
        category=category,
        id_zoom_accounts=id_zoom_accounts,
        unassigned=unassigned,
        search=search,
    )


FiltresDep = Annotated[WebinarFilters, Depends(filtres)]


async def _droits(session: SessionDep, utilisateur: User) -> list[str]:
    return await codes_de(session, utilisateur.id_users)


# --- collection -----------------------------------------------------------


@router.get("", response_model=Page[WebinarListItem], summary="Lister les webinaires")
async def list_webinars(
    session: SessionDep,
    stockage: StockageDep,
    _: CurrentUser,
    criteres: FiltresDep,
    pagination: PaginationDep,
    sort: SortKey = "date",
    direction: SortDirection = "desc",
) -> Page[WebinarListItem]:
    return await service.list_webinars(session, stockage, criteres, pagination, sort, direction)


@router.post(
    "",
    response_model=WebinarDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un webinaire en brouillon",
)
async def create_webinar(
    corps: WebinarCreate,
    session: SessionDep,
    stockage: StockageDep,
    par: GestionnaireWebinaires,
    reponse: Response,
) -> WebinarDetailRead:
    fiche = await service.create_webinar(session, stockage, corps, par)
    reponse.headers["Location"] = f"/api/v1/webinars/{fiche.id_webinars}"
    return fiche


@router.get("/stats", response_model=WebinarStatsRead, summary="Statistiques générales")
async def get_stats(
    session: SessionDep, stockage: StockageDep, _: CurrentUser, criteres: FiltresDep
) -> WebinarStatsRead:
    return await service.get_stats(session, stockage, criteres)


@router.get("/reference", response_model=WebinarReferenceRead, summary="Listes de valeurs")
async def get_reference(session: SessionDep, _: CurrentUser) -> WebinarReferenceRead:
    return await service.get_reference(session)


# --- import et synchronisation --------------------------------------------


async def _lire(fichier: UploadFile) -> bytes:
    contenu = await fichier.read(IMPORT_FILE_MAX_BYTES + 1)
    if len(contenu) > IMPORT_FILE_MAX_BYTES:
        raise ApiError("file_too_large", f"{fichier.filename} dépasse 5 Mo.", 413)
    return contenu


@router.post(
    "/imports",
    response_model=ImportReport,
    summary="Importer les webinaires exportés du site (fichiers JSON)",
)
async def import_site_export(
    session: SessionDep,
    par: GestionnaireWebinaires,
    webinars_file: Annotated[UploadFile, File(description="webinaires.json")],
    pages_file: Annotated[UploadFile | None, File(description="pages-inscription.json")] = None,
    flyers_file: Annotated[UploadFile | None, File(description="flyers.manifest.json")] = None,
) -> ImportReport:
    export = importer.lire_fichier(await _lire(webinars_file), SiteExport, "webinaires.json")
    pages = (
        importer.lire_fichier(await _lire(pages_file), PagesExport, "pages-inscription.json")
        if pages_file
        else None
    )
    manifeste = (
        importer.lire_fichier(await _lire(flyers_file), FlyerManifest, "flyers.manifest.json")
        if flyers_file
        else None
    )
    return await importer.import_site_export(session, export, pages, manifeste, par)


@router.post(
    "/flyers/fetch",
    response_model=FlyerBatchResult,
    summary="Rapatrier un lot de flyers dans le stockage",
)
async def fetch_flyers(
    session: SessionDep,
    stockage: StockageDep,
    transport: FlyerTransportDep,
    _: GestionnaireWebinaires,
    limit: Annotated[int, Query(ge=1, le=FLYER_BATCH_MAX)] = 5,
    retry_failed: bool = False,
) -> FlyerBatchResult:
    return await flyers.fetch_pending_flyers(session, stockage, limit, retry_failed, transport)


@router.post(
    "/zoom-sync",
    response_model=ZoomSyncResult,
    summary="Reprendre les réunions d'un compte Zoom, ou de tous",
)
async def sync_meetings(
    corps: ZoomSyncRequest, session: SessionDep, zoom: ZoomDep, par: GestionnaireWebinaires
) -> ZoomSyncResult:
    return await zoom_service.sync_meetings(session, zoom, corps.id_zoom_accounts, par)


@router.post(
    "/zoom-meetings",
    response_model=WebinarDetailRead,
    summary="Ajouter une réunion Zoom par son numéro",
)
async def import_meeting(
    corps: ZoomMeetingImport,
    session: SessionDep,
    zoom: ZoomDep,
    stockage: StockageDep,
    par: GestionnaireWebinaires,
) -> WebinarDetailRead:
    return await zoom_service.import_meeting(
        session,
        zoom,
        stockage,
        corps.id_zoom_accounts,
        int(corps.meeting_id),
        par,
    )


# --- pages d'inscription ---------------------------------------------------


@router.get(
    "/registration-pages",
    response_model=list[RegistrationPageRead],
    summary="Pages d'inscription connues",
)
async def list_registration_pages(
    session: SessionDep, _: CurrentUser, unlinked_only: bool = False
) -> list[RegistrationPageRead]:
    return await service.list_registration_pages(session, unlinked_only)


@router.patch(
    "/registration-pages/{id_webinar_registration_pages}",
    response_model=RegistrationPageRead,
    summary="Rattacher une page à un webinaire, ou la détacher",
)
async def link_registration_page(
    id_webinar_registration_pages: int,
    corps: RegistrationPageLink,
    session: SessionDep,
    par: GestionnaireWebinaires,
) -> RegistrationPageRead:
    return await service.link_registration_page(
        session, id_webinar_registration_pages, corps.id_webinars, par
    )


# --- une fiche -------------------------------------------------------------


@router.get("/{id_webinars}", response_model=WebinarDetailRead, summary="Détail d'un webinaire")
async def get_webinar(
    id_webinars: int, session: SessionDep, stockage: StockageDep, par: CurrentUser
) -> WebinarDetailRead:
    gestion = MANAGE_WEBINARS in await _droits(session, par)
    return await service.get_webinar(session, stockage, id_webinars, can_manage=gestion)


@router.patch("/{id_webinars}", response_model=WebinarDetailRead, summary="Modifier un webinaire")
async def update_webinar(
    id_webinars: int,
    corps: WebinarUpdate,
    session: SessionDep,
    stockage: StockageDep,
    par: GestionnaireWebinaires,
) -> WebinarDetailRead:
    return await service.update_webinar(session, stockage, id_webinars, corps, par)


@router.delete(
    "/{id_webinars}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un webinaire (la réunion Zoom n'est pas supprimée)",
)
async def archive_webinar(
    id_webinars: int, session: SessionDep, par: GestionnaireWebinaires
) -> None:
    await service.archive_webinar(session, id_webinars, par)


@router.post(
    "/{id_webinars}/schedule",
    response_model=WebinarDetailRead,
    summary="Valider un brouillon : crée la réunion Zoom si le lien est automatique",
)
async def schedule_webinar(
    id_webinars: int,
    session: SessionDep,
    zoom: ZoomDep,
    stockage: StockageDep,
    par: GestionnaireWebinaires,
) -> WebinarDetailRead:
    peut_creer = CREATE_ZOOM_MEETINGS in await _droits(session, par)
    return await zoom_service.schedule_webinar(
        session, zoom, stockage, id_webinars, par, peut_creer
    )


@router.post(
    "/{id_webinars}/refresh-from-zoom",
    response_model=WebinarDetailRead,
    summary="Relire la réunion sur Zoom (GET /meetings/{meetingId})",
)
async def refresh_from_zoom(
    id_webinars: int,
    session: SessionDep,
    zoom: ZoomDep,
    stockage: StockageDep,
    _: GestionnaireWebinaires,
) -> WebinarDetailRead:
    return await zoom_service.refresh_from_zoom(session, zoom, stockage, id_webinars)


# --- visuel ----------------------------------------------------------------


@router.put(
    "/{id_webinars}/flyer",
    response_model=WebinarDetailRead,
    summary="Importer le visuel d'un webinaire",
    description=(
        "PNG, JPEG ou WebP, 10 Mo au plus. Le type est lu dans le fichier et non "
        "déduit de son nom. Le visuel précédent est remplacé."
    ),
    responses={
        413: {"description": "Fichier trop lourd."},
        415: {"description": "Le fichier n'est pas une image acceptée."},
    },
)
async def upload_flyer(
    id_webinars: int,
    session: SessionDep,
    stockage: StockageDep,
    par: GestionnaireWebinaires,
    file: Annotated[UploadFile, File(description="L'image à utiliser comme visuel.")],
) -> WebinarDetailRead:
    contenu = await file.read(FLYER_MAX_BYTES + 1)
    await flyers.upload_flyer(session, stockage, id_webinars, contenu, par)
    return await service.get_webinar(session, stockage, id_webinars, can_manage=True)


@router.delete(
    "/{id_webinars}/flyer",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer le visuel d'un webinaire",
)
async def remove_flyer(id_webinars: int, session: SessionDep, par: GestionnaireWebinaires) -> None:
    await flyers.remove_flyer(session, id_webinars, par)


# --- publications liées ----------------------------------------------------


@router.post(
    "/{id_webinars}/publication-links",
    response_model=list[PublicationLinkRead],
    status_code=status.HTTP_201_CREATED,
    summary="Lier une publication",
)
async def add_publication_link(
    id_webinars: int,
    corps: PublicationLinkCreate,
    session: SessionDep,
    par: GestionnaireWebinaires,
) -> list[PublicationLinkRead]:
    return await service.add_publication_link(session, id_webinars, corps, par)


@router.delete(
    "/{id_webinars}/publication-links/{id_webinar_publication_links}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un lien de publication",
)
async def remove_publication_link(
    id_webinars: int,
    id_webinar_publication_links: int,
    session: SessionDep,
    _: GestionnaireWebinaires,
) -> None:
    await service.remove_publication_link(session, id_webinars, id_webinar_publication_links)


# --- inscriptions (données personnelles : droit de gestion exigé) ----------


@router.get(
    "/{id_webinars}/registrations",
    response_model=Page[RegistrationRead],
    summary="Inscrits",
)
async def list_registrations(
    id_webinars: int,
    session: SessionDep,
    _: GestionnaireWebinaires,
    pagination: PaginationDep,
) -> Page[RegistrationRead]:
    return await registration_service.list_registrations(session, id_webinars, pagination)


@router.get(
    "/{id_webinars}/registrations/export",
    response_class=Response,
    summary="Exporter les inscrits en CSV",
    responses={200: {"content": {"text/csv": {}}}},
)
async def export_registrations(
    id_webinars: int, session: SessionDep, par: GestionnaireWebinaires
) -> Response:
    contenu = await registration_export.export_registrations(session, id_webinars, par)
    return Response(
        content=contenu.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="inscrits-{id_webinars}.csv"',
            # Des données personnelles : aucune copie ne doit rester en cache.
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/{id_webinars}/registrations",
    response_model=RegistrationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Inscrire une personne",
)
async def add_registration(
    id_webinars: int,
    corps: RegistrationCreate,
    session: SessionDep,
    zoom: ZoomDep,
    _: GestionnaireWebinaires,
) -> RegistrationRead:
    return await registration_service.add_registration(session, zoom, id_webinars, corps)


@router.post(
    "/{id_webinars}/registrations/zoom-sync",
    response_model=RegistrantSyncResult,
    summary="Reprendre les inscrits de la réunion Zoom",
)
async def sync_registrants(
    id_webinars: int, session: SessionDep, zoom: ZoomDep, _: GestionnaireWebinaires
) -> RegistrantSyncResult:
    return await registration_service.sync_registrants(session, zoom, id_webinars)


@router.patch(
    "/{id_webinars}/registrations/{id_webinar_registrations}",
    response_model=RegistrationRead,
    summary="Enregistrer ou retirer l'accord newsletter",
)
async def set_consent(
    id_webinars: int,
    id_webinar_registrations: int,
    corps: RegistrationUpdate,
    session: SessionDep,
    _: GestionnaireWebinaires,
) -> RegistrationRead:
    return await registration_service.set_consent(
        session, id_webinars, id_webinar_registrations, corps.has_newsletter_consent
    )


@router.post(
    "/{id_webinars}/registrations/{id_webinar_registrations}/push-to-zoom",
    response_model=RegistrationRead,
    summary="Retenter l'inscription sur Zoom",
)
async def push_registration(
    id_webinars: int,
    id_webinar_registrations: int,
    session: SessionDep,
    zoom: ZoomDep,
    _: GestionnaireWebinaires,
) -> RegistrationRead:
    return await registration_service.push_registration(
        session, zoom, id_webinars, id_webinar_registrations
    )


@router.delete(
    "/{id_webinars}/registrations/{id_webinar_registrations}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Effacer les données personnelles d'un inscrit",
)
async def anonymize_registration(
    id_webinars: int,
    id_webinar_registrations: int,
    session: SessionDep,
    _: GestionnaireWebinaires,
) -> None:
    await registration_service.anonymize_registration(
        session, id_webinars, id_webinar_registrations
    )


@router.get(
    "/{id_webinars}/newsletter-audience",
    response_model=NewsletterAudienceRead,
    summary="Inscrits ayant consenti, prêts pour un envoi",
)
async def get_newsletter_audience(
    id_webinars: int, session: SessionDep, _: GestionnaireWebinaires
) -> NewsletterAudienceRead:
    return await registration_service.get_newsletter_audience(session, id_webinars)


# --- formulaire public : aucune authentification ---------------------------


@public_router.get("/{slug}", response_model=PublicPageRead, summary="Formulaire d'inscription")
async def get_public_page(slug: str, session: SessionDep, stockage: StockageDep) -> PublicPageRead:
    return await registration_service.get_public_page(session, stockage, slug)


@public_router.post(
    "/{slug}/registrations",
    response_model=PublicRegistrationRead,
    status_code=status.HTTP_201_CREATED,
    summary="S'inscrire",
)
async def register_from_public_page(
    slug: str, corps: PublicRegistrationCreate, session: SessionDep, zoom: ZoomDep
) -> PublicRegistrationRead:
    return await registration_service.register_from_public_page(session, zoom, slug, corps)
