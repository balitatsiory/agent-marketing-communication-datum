"""Routes du module Média. Aucune règle métier ici."""

from collections.abc import Sequence
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy import select

from app.core.deps import SessionDep
from app.core.downloads import HostResolver
from app.core.pagination import Page, PageParams, page_params
from app.core.storage import Stockage, get_stockage
from app.modules.media import service
from app.modules.media.constants import MANAGE_MEDIA, MANAGE_MEDIA_REFERENCE, PURGE_MEDIA
from app.modules.media.dependencies import get_host_resolver, get_image_link_transport
from app.modules.media.models import Media, MediaReference, MediaReferenceNature
from app.modules.media.schemas import (
    MediaRead,
    MediaReferenceCreate,
    MediaReferenceImageReplace,
    MediaReferenceNatureRead,
    MediaReferenceRead,
    MediaReferenceUpdate,
    MediaRename,
)
from app.modules.users.deps import require
from app.modules.users.models import User

router = APIRouter(tags=["médias"])

Params = Annotated[PageParams, Depends(page_params)]
StockageDep = Annotated[Stockage, Depends(get_stockage)]
GestionnaireMedias = Annotated[User, Depends(require(MANAGE_MEDIA))]
GestionnaireReferences = Annotated[User, Depends(require(MANAGE_MEDIA_REFERENCE))]
Purgeur = Annotated[User, Depends(require(PURGE_MEDIA))]
ImageLinkTransportDep = Annotated[
    httpx.AsyncBaseTransport | None, Depends(get_image_link_transport)
]
HostResolverDep = Annotated[HostResolver, Depends(get_host_resolver)]


def _lire_media(media: Media, stockage: Stockage) -> MediaRead:
    """L'URL se recompose à la lecture : la base ne garde que la clé."""
    return MediaRead.model_validate(media).model_copy(
        update={"url": stockage.url_publique(media.storage_key)}
    )


async def _lire_references(
    session: SessionDep, references: Sequence[MediaReference]
) -> list[MediaReferenceRead]:
    """Compose les lectures avec le code de leur nature, en UNE requête."""
    if not references:
        return []

    natures = (await session.execute(select(MediaReferenceNature))).scalars().all()
    code_par_id = {n.id_media_reference_natures: n.code for n in natures}
    return [
        MediaReferenceRead.model_validate(r).model_copy(
            update={"nature_code": code_par_id.get(r.id_media_reference_natures, "")}
        )
        for r in references
    ]


# --------------------------------------------------------------- bibliothèque


@router.post(
    "/media",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Déposer un fichier",
    description=(
        "Le type est détecté aux octets et non déduit de l'extension. Une image "
        "de plus de 8 Mo est compressée pour repasser sous le plafond, non "
        "refusée. Une vidéo n'est ni mesurée ni transformée."
    ),
    responses={
        413: {"description": "Fichier trop lourd, ou image au-delà de la limite de pixels."},
        415: {"description": "Format de fichier non reconnu."},
        422: {"description": "Image impossible à ramener sous le plafond."},
    },
)
async def deposer(
    session: SessionDep,
    stockage: StockageDep,
    par: GestionnaireMedias,
    reponse: Response,
    fichier: Annotated[UploadFile, File(description="Le fichier à déposer.")],
    display_name: Annotated[str | None, Form()] = None,
) -> MediaRead:
    media = await service.deposer(
        session,
        stockage,
        fichier.file,
        display_name or fichier.filename or "sans nom",
        par,
    )
    reponse.headers["Location"] = f"/api/v1/media/{media.id_media}"
    return _lire_media(media, stockage)


@router.get("/media", response_model=Page[MediaRead], summary="Lister les médias")
async def lister(
    session: SessionDep,
    stockage: StockageDep,
    params: Params,
    _: GestionnaireMedias,
    inclure_archives: bool = Query(
        False, alias="include_archived", description="Inclure les médias archivés."
    ),
) -> Page[MediaRead]:
    medias, total = await service.lister(session, params, inclure_archives)
    return Page[MediaRead].build([_lire_media(m, stockage) for m in medias], total, params)


@router.get("/media/{id_media}", response_model=MediaRead, summary="Lire un média")
async def obtenir(
    id_media: int, session: SessionDep, stockage: StockageDep, _: GestionnaireMedias
) -> MediaRead:
    return _lire_media(await service.obtenir(session, id_media), stockage)


@router.patch("/media/{id_media}", response_model=MediaRead, summary="Renommer un média")
async def renommer(
    id_media: int,
    corps: MediaRename,
    session: SessionDep,
    stockage: StockageDep,
    _: GestionnaireMedias,
) -> MediaRead:
    media = await service.renommer(session, id_media, corps.display_name)
    return _lire_media(media, stockage)


@router.delete(
    "/media/{id_media}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un média",
    description=(
        "Le fichier reste dans le stockage : un média porté par une publication "
        "déjà diffusée ne peut pas disparaître sans emporter l'historique. Ses "
        "références sont archivées dans la même transaction."
    ),
    responses={409: {"description": "Média déjà archivé."}},
)
async def archiver(id_media: int, session: SessionDep, par: GestionnaireMedias) -> None:
    await service.archiver(session, id_media, par)


@router.delete(
    "/media/{id_media}/purge",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer définitivement un média",
    description=(
        "Détruit le fichier ET sa ligne, sans retour possible. Demande le droit "
        "« purge_media », distinct de « manage_media », et exige que le média "
        "ait d'abord été archivé."
    ),
    responses={409: {"description": "Média non archivé au préalable."}},
)
async def purger(id_media: int, session: SessionDep, stockage: StockageDep, par: Purgeur) -> None:
    await service.purger(session, stockage, id_media, par)


# ----------------------------------------------------------- médias de référence


@router.get(
    "/media-reference-natures",
    response_model=list[MediaReferenceNatureRead],
    summary="Lister les natures de référence",
)
async def lister_natures(
    session: SessionDep, _: GestionnaireReferences
) -> list[MediaReferenceNatureRead]:
    return [
        MediaReferenceNatureRead.model_validate(n) for n in await service.lister_natures(session)
    ]


@router.post(
    "/media-references",
    response_model=MediaReferenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Déclarer un média comme référence",
    description=(
        "La déclaration est un geste explicite : l'utilisateur désigne le média "
        "et choisit ce qu'il représente. Rien ne naît automatiquement au dépôt."
    ),
    responses={409: {"description": "Média archivé, déjà référencé, ou qui n'est pas une image."}},
)
async def declarer(
    corps: MediaReferenceCreate, session: SessionDep, par: GestionnaireReferences
) -> MediaReferenceRead:
    reference = await service.declarer_reference(session, corps, par)
    return (await _lire_references(session, [reference]))[0]


@router.get(
    "/media-references",
    response_model=Page[MediaReferenceRead],
    summary="Lister les médias de référence",
)
async def lister_refs(
    session: SessionDep,
    params: Params,
    _: GestionnaireReferences,
    inclure_archivees: bool = Query(False, alias="include_archived"),
) -> Page[MediaReferenceRead]:
    references, total = await service.lister_references(session, params, inclure_archivees)
    return Page[MediaReferenceRead].build(
        await _lire_references(session, references), total, params
    )


@router.patch(
    "/media-references/{id_reference}",
    response_model=MediaReferenceRead,
    summary="Modifier une référence",
)
async def modifier(
    id_reference: int,
    corps: MediaReferenceUpdate,
    session: SessionDep,
    par: GestionnaireReferences,
) -> MediaReferenceRead:
    reference = await service.modifier_reference(session, id_reference, corps, par)
    return (await _lire_references(session, [reference]))[0]


@router.post(
    "/media-references/{id_reference}/image",
    response_model=MediaReferenceRead,
    summary="Remplacer l'image d'une référence par celle d'une adresse",
    description=(
        "Le serveur rapatrie l'image, en fait un nouveau média et le donne à la "
        "référence ; l'adresse saisie n'est pas conservée et l'ancien média reste "
        "en bibliothèque. Seules les adresses HTTPS publiques sont acceptées, sans "
        "redirection. Demande les droits « manage_media_reference » et « manage_media »."
    ),
    responses={
        409: {"description": "Référence archivée."},
        413: {"description": "Image au-delà de la limite de pixels."},
        415: {"description": "L'adresse ne renvoie pas une image lisible."},
        422: {"description": "Adresse refusée ou injoignable, ou image trop lourde."},
    },
)
async def replace_reference_image(
    id_reference: int,
    body: MediaReferenceImageReplace,
    session: SessionDep,
    storage: StockageDep,
    by: GestionnaireReferences,
    _: GestionnaireMedias,
    transport: ImageLinkTransportDep,
    resolve: HostResolverDep,
) -> MediaReferenceRead:
    reference = await service.replace_reference_image(
        session, storage, id_reference, body.url, by, transport=transport, resolve=resolve
    )
    return (await _lire_references(session, [reference]))[0]


@router.delete(
    "/media-references/{id_reference}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer la qualité de référence",
    description="Le média, lui, reste dans la bibliothèque.",
)
async def archiver_ref(id_reference: int, session: SessionDep, par: GestionnaireReferences) -> None:
    await service.archiver_reference(session, id_reference, par)
