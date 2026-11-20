"""Routes du module 08 Publications. Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.deps import SessionDep
from app.modules.publications import service
from app.modules.publications.constants import (
    CREATE_PUBLICATIONS,
    PUBLISH_PUBLICATIONS,
    READ_PUBLICATIONS,
    REVIEW_PUBLICATIONS,
)
from app.modules.publications.schemas import (
    PublicationCreate,
    PublicationDecision,
    PublicationFormatRead,
    PublicationPublishResultRead,
    PublicationRead,
)
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User

router = APIRouter(tags=["publications"])

LecteurPublications = Annotated[User, Depends(require(READ_PUBLICATIONS))]
RedacteurPublications = Annotated[User, Depends(require(CREATE_PUBLICATIONS))]
RelecteurPublications = Annotated[User, Depends(require(REVIEW_PUBLICATIONS))]
DiffuseurPublications = Annotated[User, Depends(require(PUBLISH_PUBLICATIONS))]


@router.get(
    "/publication-formats",
    response_model=list[PublicationFormatRead],
    summary="Lister les formats de publication et leurs plateformes compatibles",
)
async def lister_formats(
    session: SessionDep, _: CurrentUser
) -> list[PublicationFormatRead]:
    return await service.lister_formats(session)


@router.get(
    "/publications",
    response_model=list[PublicationRead],
    summary="Lister les publications",
)
async def lister_publications(
    session: SessionDep, _: LecteurPublications
) -> list[PublicationRead]:
    return await service.lister_publications(session)


@router.get(
    "/publications/{id_publications}",
    response_model=PublicationRead,
    summary="Lire une publication et ses cibles",
)
async def obtenir_publication(
    id_publications: int, session: SessionDep, _: LecteurPublications
) -> PublicationRead:
    return await service.obtenir_publication(session, id_publications)


@router.post(
    "/publications",
    response_model=PublicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer et soumettre une publication à la validation",
)
async def creer_publication(
    corps: PublicationCreate,
    session: SessionDep,
    par: RedacteurPublications,
    reponse: Response,
) -> PublicationRead:
    pub = await service.creer_publication(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/publications/{pub.id_publications}"
    return pub


@router.post(
    "/publications/{id_publications}/approve",
    response_model=PublicationRead,
    summary="Approuver une publication en attente de validation",
)
async def approuver_publication(
    id_publications: int,
    corps: PublicationDecision,
    session: SessionDep,
    par: RelecteurPublications,
) -> PublicationRead:
    return await service.approuver_publication(session, id_publications, par, corps.comment)


@router.post(
    "/publications/{id_publications}/request-correction",
    response_model=PublicationRead,
    summary="Demander une correction sur une publication",
)
async def demander_correction(
    id_publications: int,
    corps: PublicationDecision,
    session: SessionDep,
    par: RelecteurPublications,
) -> PublicationRead:
    return await service.demander_correction(session, id_publications, par, corps.comment)


@router.post(
    "/publications/{id_publications}/publish",
    response_model=PublicationPublishResultRead,
    summary="Publier immédiatement une publication validée vers Facebook (Meta Graph API)",
)
async def publier_maintenant(
    id_publications: int,
    session: SessionDep,
    par: DiffuseurPublications,
) -> PublicationPublishResultRead:
    return await service.publier_maintenant(session, id_publications, par)
