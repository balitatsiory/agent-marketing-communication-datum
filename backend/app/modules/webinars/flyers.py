"""Visuels des webinaires : rapatriés du site, ou importés depuis le poste.

Un fichier importé passe les mêmes contrôles qu'un flyer rapatrié : seul ce
qui s'ouvre réellement comme une image PNG, JPEG ou WebP est rangé.

Le serveur ne télécharge que depuis le site de l'école, sans suivre de
redirection, et ne range que ce qui s'ouvre réellement comme une image : un
fichier d'import ne doit pouvoir ni faire appeler une adresse quelconque, ni
déposer un contenu quelconque.
"""

import hashlib
import io
import logging
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.downloads import DownloadRefusedError, download_image
from app.core.errors import ApiError
from app.core.storage import Stockage
from app.modules.media.images import compresser
from app.modules.users.models import User
from app.modules.webinars import service
from app.modules.webinars.constants import (
    FLYER_ALLOWED_HOSTS,
    FLYER_FORMATS,
    FLYER_MAX_BYTES,
    FLYER_TIMEOUT_SECONDS,
)
from app.modules.webinars.importer import normaliser_slug
from app.modules.webinars.models import Webinar
from app.modules.webinars.schemas import FlyerBatchResult, FlyerError

logger = logging.getLogger(__name__)

# Extensions admises pour chaque format, la première servant par défaut.
EXTENSIONS = {"PNG": ("png",), "JPEG": ("jpg", "jpeg"), "WEBP": ("webp",)}


class FlyerRefusedError(Exception):
    """Fichier qu'on ne rapatrie pas ; le message est affiché tel quel."""


def get_flyer_transport() -> httpx.AsyncBaseTransport | None:
    """Transport des téléchargements ; les tests lui substituent une réponse locale."""
    return None


async def _telecharger(adresse: str, transport: httpx.AsyncBaseTransport | None) -> bytes:
    try:
        return await download_image(
            adresse,
            allowed_hosts=FLYER_ALLOWED_HOSTS,
            max_bytes=FLYER_MAX_BYTES,
            timeout_seconds=FLYER_TIMEOUT_SECONDS,
            transport=transport,
        )
    except DownloadRefusedError as erreur:
        raise FlyerRefusedError(str(erreur)) from erreur


def _format_image(contenu: bytes) -> str:
    try:
        with Image.open(io.BytesIO(contenu)) as image:
            genre = image.format or ""
            if image.width * image.height > get_settings().MEDIA_MAX_PIXELS:
                raise FlyerRefusedError("Image trop grande.")
            image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as e:
        raise FlyerRefusedError("Le fichier reçu n'est pas une image lisible.") from e
    if genre not in FLYER_FORMATS:
        raise FlyerRefusedError(f"Format d'image non pris en charge : {genre or 'inconnu'}.")
    return genre


def cle_flyer(webinaire: Webinar, contenu: bytes, genre: str) -> str:
    """`webinaires/{slug}/flyer-origine-{sha12}.{ext}`.

    Le slug est normalisé : un « %C3%A9 » laissé dans une clé serait redécodé
    par le navigateur et l'image deviendrait introuvable.
    """
    slug = normaliser_slug(unquote(webinaire.external_site_slug or "")) or str(
        webinaire.id_webinars
    )
    suffixe = PurePosixPath(urlsplit(webinaire.flyer_source_url or "").path).suffix
    extension = suffixe.lstrip(".").lower()
    if extension not in EXTENSIONS[genre]:
        extension = EXTENSIONS[genre][0]
    empreinte = hashlib.sha256(contenu).hexdigest()
    return f"webinaires/{slug}/flyer-origine-{empreinte[:12]}.{extension}"


async def _noter(
    session: AsyncSession, id_webinars: int, source: str, **valeurs: str | int
) -> bool:
    """Écrit le résultat seulement si la fiche vise toujours l'adresse téléchargée.

    La condition est évaluée par la base : un import validé pendant le
    téléchargement l'emporte, et la fiche reste à rapatrier.
    """
    requete = (
        update(Webinar)
        .where(Webinar.id_webinars == id_webinars, Webinar.flyer_source_url == source)
        .values(**valeurs)
        .returning(Webinar.id_webinars)
    )
    return (await session.execute(requete)).first() is not None


async def fetch_pending_flyers(
    session: AsyncSession,
    stockage: Stockage,
    limit: int,
    retry_failed: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FlyerBatchResult:
    """Rapatrie un lot de flyers encore servis par le site.

    Un échec est noté sur la fiche et n'arrête pas le lot. `remaining` compte ce
    qu'un appel suivant traiterait.
    """
    en_attente = [
        Webinar.deleted_at.is_(None),
        Webinar.flyer_source_url.is_not(None),
        Webinar.flyer_storage_key.is_(None),
    ]
    if retry_failed:
        # Les échecs repassent une fois : on efface leur marque avant de choisir.
        for webinaire in (
            await session.execute(
                select(Webinar).where(*en_attente, Webinar.flyer_error.is_not(None))
            )
        ).scalars():
            webinaire.flyer_error = None
        await session.flush()
    en_attente.append(Webinar.flyer_error.is_(None))

    lot = (
        (
            await session.execute(
                select(Webinar).where(*en_attente).order_by(Webinar.id_webinars).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    resultat = FlyerBatchResult(stored=0, failed=0, remaining=0, errors=[])
    for webinaire in lot:
        source = webinaire.flyer_source_url
        assert source is not None
        try:
            contenu = await _telecharger(source, transport)
            genre = _format_image(contenu)
            cle = cle_flyer(webinaire, contenu, genre)
            await stockage.deposer(cle, io.BytesIO(contenu), FLYER_FORMATS[genre])
        except Exception as erreur:
            # Réseau, refus ou stockage indisponible : la fiche garde la cause.
            if not isinstance(erreur, FlyerRefusedError | httpx.HTTPError | ApiError):
                logger.exception("Flyer du webinaire %s non rapatrié", webinaire.id_webinars)
            message = (
                str(erreur)
                if isinstance(erreur, FlyerRefusedError)
                else f"Échec technique ({type(erreur).__name__})."
            )
            if await _noter(session, webinaire.id_webinars, source, flyer_error=message):
                resultat.failed += 1
                resultat.errors.append(
                    FlyerError(
                        id_webinars=webinaire.id_webinars,
                        title=webinaire.title,
                        message=message,
                    )
                )
        else:
            if await _noter(
                session,
                webinaire.id_webinars,
                source,
                flyer_storage_key=cle,
                flyer_sha256=hashlib.sha256(contenu).hexdigest(),
                flyer_byte_size=len(contenu),
            ):
                resultat.stored += 1

    resultat.remaining = (
        await session.execute(select(func.count()).select_from(Webinar).where(*en_attente))
    ).scalar_one()
    return resultat


def _preparer(contenu: bytes) -> tuple[bytes, str]:
    """Vérifie une image importée, et la compresse au-delà du plafond des médias."""
    genre = _format_image(contenu)
    donnees, _, _ = compresser(contenu, get_settings().MEDIA_MAX_STORED_BYTES)
    return donnees, genre


async def upload_flyer(
    session: AsyncSession, stockage: Stockage, id_webinars: int, contenu: bytes, par: User
) -> None:
    """Remplace le visuel d'un webinaire par un fichier importé.

    La fiche est marquée comme modifiée à la main et perd son adresse d'origine :
    ni un nouvel import du site ni un rapatriement en cours ne l'écrasent.
    L'ancien fichier reste dans le stockage.

    Raises:
        NotFoundError: webinaire inconnu ou archivé.
        ApiError: fichier trop lourd (`file_too_large`) ou refusé (`invalid_image`).
    """
    if len(contenu) > FLYER_MAX_BYTES:
        raise ApiError(
            "file_too_large",
            f"L'image dépasse {FLYER_MAX_BYTES // (1024 * 1024)} Mo.",
            413,
        )
    try:
        # Décoder et compresser occupent le processeur : hors de la boucle de l'API.
        donnees, genre = await run_in_threadpool(_preparer, contenu)
    except FlyerRefusedError as erreur:
        raise ApiError("invalid_image", str(erreur), 415) from erreur

    webinaire = await service.charger(session, id_webinars, verrouiller=True)
    empreinte = hashlib.sha256(donnees).hexdigest()
    cle = f"webinaires/{id_webinars}/visuel-{empreinte[:12]}.{EXTENSIONS[genre][0]}"
    await stockage.deposer(cle, io.BytesIO(donnees), FLYER_FORMATS[genre])
    webinaire.flyer_storage_key = cle
    webinaire.flyer_sha256 = empreinte
    webinaire.flyer_byte_size = len(donnees)
    webinaire.flyer_source_url = None
    webinaire.flyer_error = None
    webinaire.id_users_changed_by = par.id_users
    await session.flush()
    logger.info("Visuel importé : webinaire %s, utilisateur %s", id_webinars, par.id_users)


async def remove_flyer(session: AsyncSession, id_webinars: int, par: User) -> None:
    """Retire le visuel de la fiche. Le fichier reste dans le stockage.

    Raises:
        NotFoundError: webinaire inconnu ou archivé.
    """
    webinaire = await service.charger(session, id_webinars, verrouiller=True)
    webinaire.flyer_storage_key = None
    webinaire.flyer_sha256 = None
    webinaire.flyer_byte_size = None
    webinaire.flyer_source_url = None
    webinaire.flyer_error = None
    webinaire.id_users_changed_by = par.id_users
    await session.flush()
    logger.info("Visuel retiré : webinaire %s, utilisateur %s", id_webinars, par.id_users)
