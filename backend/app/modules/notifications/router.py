"""Routes du module Notifications."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import SessionDep
from app.core.pagination import Page, PageParams, page_params
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    MarkAllReadResponse,
    NotificationRead,
    NotificationStatsRead,
)
from app.modules.users.deps import CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])

Params = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[NotificationRead], summary="Lister mes notifications")
async def lister(
    session: SessionDep,
    utilisateur: CurrentUser,
    params: Params,
    q: str | None = Query(None, description="Recherche sur le titre ou le contenu."),
    source: str | None = Query(None, description="Filtre de portée : internal ou platform."),
    types: list[str] | None = Query(None, alias="type", description="Types de notification."),
    platforms: list[str] | None = Query(
        None, alias="platform", description="Plateformes ou 'internal'."
    ),
    unread_only: bool = Query(False, description="Uniquement les notifications non lues."),
    requires_action: bool = Query(False, description="Uniquement celles demandant une action."),
) -> Page[NotificationRead]:
    items, total = await service.lister(
        session,
        utilisateur.id_users,
        params,
        q=q,
        source=source,
        types=types,
        platforms=platforms,
        unread_only=unread_only,
        requires_action=requires_action,
    )
    return Page[NotificationRead].build(items, total, params)


@router.get("/stats", response_model=NotificationStatsRead, summary="Statistiques des notifications")
async def statistiques(
    session: SessionDep,
    utilisateur: CurrentUser,
) -> NotificationStatsRead:
    return await service.statistiques(session, utilisateur.id_users)


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Tout marquer comme lu",
)
async def tout_marquer_lu(
    session: SessionDep,
    utilisateur: CurrentUser,
) -> MarkAllReadResponse:
    updated = await service.tout_marquer_lu(session, utilisateur.id_users)
    return MarkAllReadResponse(updated=updated)


@router.post(
    "/{id_notifications}/read",
    response_model=NotificationRead,
    summary="Marquer une notification comme lue",
)
async def marquer_lue(
    id_notifications: int,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> NotificationRead:
    return await service.marquer_lue(session, id_notifications, utilisateur.id_users, lue=True)


@router.post(
    "/{id_notifications}/unread",
    response_model=NotificationRead,
    summary="Marquer une notification comme non lue",
)
async def marquer_non_lue(
    id_notifications: int,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> NotificationRead:
    return await service.marquer_lue(session, id_notifications, utilisateur.id_users, lue=False)


@router.delete(
    "/{id_notifications}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notification",
)
async def supprimer(
    id_notifications: int,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> None:
    await service.supprimer(session, id_notifications, utilisateur.id_users)
