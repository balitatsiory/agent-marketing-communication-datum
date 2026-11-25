"""Routes du module Comptes Zoom. Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User
from app.modules.zoom_accounts import service
from app.modules.zoom_accounts.constants import MANAGE_ZOOM_ACCOUNTS
from app.modules.zoom_accounts.schemas import (
    ZoomAccountCheckRead,
    ZoomAccountCreate,
    ZoomAccountRead,
    ZoomAccountUpdate,
    ZoomAccountVerifyRead,
    ZoomClientSecretSave,
)
from app.modules.zoom_accounts.zoom_client import ZoomClient, get_zoom_client

router = APIRouter(prefix="/zoom-accounts", tags=["comptes-zoom"])

# La lecture est ouverte à tout utilisateur connecté (la liste des webinaires
# filtre par compte) ; elle ne porte aucun secret. Le reste demande le droit.
GestionnaireZoom = Annotated[User, Depends(require(MANAGE_ZOOM_ACCOUNTS))]
ZoomDep = Annotated[ZoomClient, Depends(get_zoom_client)]


@router.get("", response_model=list[ZoomAccountRead], summary="Lister les comptes Zoom")
async def list_accounts(session: SessionDep, _: CurrentUser) -> list[ZoomAccountRead]:
    return await service.list_accounts(session)


@router.post(
    "",
    response_model=ZoomAccountVerifyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Raccorder un compte Zoom (secret chiffré) et tester la connexion",
)
async def create_account(
    corps: ZoomAccountCreate,
    session: SessionDep,
    zoom: ZoomDep,
    par: GestionnaireZoom,
    reponse: Response,
) -> ZoomAccountVerifyRead:
    resultat = await service.create_account(session, zoom, corps, par)
    reponse.headers["Location"] = f"/api/v1/zoom-accounts/{resultat.account.id_zoom_accounts}"
    return resultat


@router.get("/{id_zoom_accounts}", response_model=ZoomAccountRead, summary="Lire un compte Zoom")
async def get_account(
    id_zoom_accounts: int, session: SessionDep, _: CurrentUser
) -> ZoomAccountRead:
    return await service.get_account(session, id_zoom_accounts)


@router.patch(
    "/{id_zoom_accounts}",
    response_model=ZoomAccountRead,
    summary="Modifier un compte Zoom (nom, hôte, identifiants non secrets)",
)
async def update_account(
    id_zoom_accounts: int, corps: ZoomAccountUpdate, session: SessionDep, par: GestionnaireZoom
) -> ZoomAccountRead:
    return await service.update_account(session, id_zoom_accounts, corps, par)


@router.post(
    "/{id_zoom_accounts}/client-secret",
    response_model=ZoomAccountVerifyRead,
    summary="Remplacer le Client Secret",
)
async def replace_client_secret(
    id_zoom_accounts: int,
    corps: ZoomClientSecretSave,
    session: SessionDep,
    zoom: ZoomDep,
    par: GestionnaireZoom,
) -> ZoomAccountVerifyRead:
    return await service.replace_client_secret(session, zoom, id_zoom_accounts, corps, par)


@router.post(
    "/{id_zoom_accounts}/verify",
    response_model=ZoomAccountVerifyRead,
    summary="Tester la connexion (jeton neuf puis lecture des réunions de l'hôte)",
)
async def verify_account(
    id_zoom_accounts: int, session: SessionDep, zoom: ZoomDep, par: GestionnaireZoom
) -> ZoomAccountVerifyRead:
    return await service.verify_account(session, zoom, id_zoom_accounts, par)


@router.post(
    "/{id_zoom_accounts}/refresh-token",
    response_model=ZoomAccountVerifyRead,
    summary="Renouveler le jeton d'accès",
)
async def refresh_token(
    id_zoom_accounts: int, session: SessionDep, zoom: ZoomDep, par: GestionnaireZoom
) -> ZoomAccountVerifyRead:
    return await service.refresh_token(session, zoom, id_zoom_accounts, par)


@router.get(
    "/{id_zoom_accounts}/checks",
    response_model=list[ZoomAccountCheckRead],
    summary="Historique des vérifications",
)
async def list_checks(
    id_zoom_accounts: int,
    session: SessionDep,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = service.VERIFICATIONS_PAR_DEFAUT,
) -> list[ZoomAccountCheckRead]:
    return await service.list_checks(session, id_zoom_accounts, limit)


@router.delete(
    "/{id_zoom_accounts}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un compte Zoom et révoquer son secret",
)
async def archive_account(
    id_zoom_accounts: int, session: SessionDep, par: GestionnaireZoom
) -> None:
    await service.archive_account(session, id_zoom_accounts, par)
