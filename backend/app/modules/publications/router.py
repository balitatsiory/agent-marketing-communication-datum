"""Routes du module Publications et cycle de validation."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.core.pagination import Page, PageParams, page_params
from app.modules.publications import service
from app.modules.publications.schemas import (
    ApprovePublicationInput,
    CommentInput,
    PublicationCreate,
    PublicationDetailRead,
    PublicationSummaryRead,
    PublicationUpdate,
    SubmitValidationInput,
    ValidatorOptionRead,
)
from app.modules.users.deps import CurrentUser

router = APIRouter(prefix="/publications", tags=["publications"])

Params = Annotated[PageParams, Depends(page_params)]


@router.get(
    "/validators",
    response_model=list[ValidatorOptionRead],
    summary="Lister les validateurs disponibles",
)
async def lister_validateurs(
    session: SessionDep,
    utilisateur: CurrentUser,
) -> list[ValidatorOptionRead]:
    return await service.lister_validateurs(session, utilisateur)


@router.get("", response_model=Page[PublicationSummaryRead], summary="Lister les publications")
async def lister(
    session: SessionDep,
    _: CurrentUser,
    params: Params,
    status_code: str | None = Query(None, alias="status", description="Filtrer par statut."),
) -> Page[PublicationSummaryRead]:
    items, total = await service.lister(session, params, status_code=status_code)
    return Page[PublicationSummaryRead].build(items, total, params)


@router.post(
    "",
    response_model=PublicationDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une publication (brouillon ou envoyée à la validation)",
)
async def creer(
    corps: PublicationCreate,
    session: SessionDep,
    utilisateur: CurrentUser,
    reponse: Response,
) -> PublicationDetailRead:
    pub = await service.creer(session, corps, utilisateur)
    reponse.headers["Location"] = f"/api/v1/publications/{pub.id_publications}"
    return pub


@router.get(
    "/{id_publications}",
    response_model=PublicationDetailRead,
    summary="Lire le détail d'une publication et son journal de validation",
)
async def obtenir(
    id_publications: int,
    session: SessionDep,
    _: CurrentUser,
) -> PublicationDetailRead:
    return await service.obtenir(session, id_publications)


@router.patch(
    "/{id_publications}",
    response_model=PublicationDetailRead,
    summary="Modifier une publication",
)
async def modifier(
    id_publications: int,
    corps: PublicationUpdate,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> PublicationDetailRead:
    return await service.modifier(session, id_publications, corps, utilisateur)


@router.post(
    "/{id_publications}/submit",
    response_model=PublicationDetailRead,
    summary="Envoyer ou renvoyer une publication à la validation",
)
async def soumettre(
    id_publications: int,
    session: SessionDep,
    utilisateur: CurrentUser,
    corps: SubmitValidationInput | None = None,
) -> PublicationDetailRead:
    payload = corps or SubmitValidationInput()
    return await service.soumettre(
        session,
        id_publications,
        utilisateur,
        id_users_validator=payload.id_users_validator,
        comment=payload.comment,
    )


@router.post(
    "/{id_publications}/request-changes",
    response_model=PublicationDetailRead,
    summary="Suggérer une correction (en commentaire) et notifier l'auteur",
)
async def suggerer_correction(
    id_publications: int,
    corps: CommentInput,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> PublicationDetailRead:
    return await service.suggerer_correction(session, id_publications, utilisateur, corps.comment)


@router.post(
    "/{id_publications}/comments",
    response_model=PublicationDetailRead,
    summary="Ajouter un commentaire dans le fil de la publication",
)
async def ajouter_commentaire(
    id_publications: int,
    corps: CommentInput,
    session: SessionDep,
    utilisateur: CurrentUser,
) -> PublicationDetailRead:
    return await service.ajouter_commentaire(session, id_publications, utilisateur, corps.comment)


@router.post(
    "/{id_publications}/approve",
    response_model=PublicationDetailRead,
    summary="Approuver, programmer ou confirmer et publier une publication",
)
async def approuver(
    id_publications: int,
    session: SessionDep,
    utilisateur: CurrentUser,
    corps: ApprovePublicationInput | None = None,
) -> PublicationDetailRead:
    payload = corps or ApprovePublicationInput()
    return await service.approuver(session, id_publications, utilisateur, payload)
