"""Reprise des logos d'organisations comme médias de référence.

Chaque logo est rapatrié du site de l'école, ouvert en entier comme image, rangé
sous `organisations/{code}/logo-{sha12}.{ext}` puis déclaré comme référence de
nature « logo ». La clé dérive du contenu : rejouer l'import retrouve le média
et n'écrit rien. Un geste fait à l'écran (archivage, retrait de la référence)
n'est jamais défait.
"""

import hashlib
import io
import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.downloads import DownloadRefusedError, download_image
from app.core.errors import ApiError
from app.core.storage import Stockage
from app.modules.media import service
from app.modules.media.constants import (
    LOGO_ALLOWED_HOSTS,
    LOGO_NATURE_CODE,
    LOGO_TIMEOUT_SECONDS,
)
from app.modules.media.images import inspect_image
from app.modules.media.import_schemas import OrganisationLogo
from app.modules.media.models import Media, MediaReference
from app.modules.media.schemas import MediaReferenceCreate

logger = logging.getLogger(__name__)

SessionOpener = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class LogoOutcome(StrEnum):
    IMPORTED = "imported"
    ALREADY_PRESENT = "already_present"
    # Rien n'est écrit : un choix fait à l'écran, ou à faire, l'emporte.
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class LogoResult:
    """Sort d'une entrée du fichier. `message` est affiché tel quel."""

    code: str
    outcome: LogoOutcome
    message: str = ""
    storage_key: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _LogoFile:
    content: bytes
    file_type: str
    width: int
    height: int

    @property
    def extension(self) -> str:
        return service.EXTENSIONS[self.file_type]


def _inspect_image(content: bytes) -> _LogoFile:
    """Contenu reçu, avec le type et les dimensions lus dans ses octets.

    Raises:
        ApiError: format non reconnu, image illisible ou trop grande.
    """
    file_type, width, height = inspect_image(content, get_settings().MEDIA_MAX_PIXELS)
    return _LogoFile(content, file_type, width, height)


def _list_warnings(entry: OrganisationLogo, logo: _LogoFile) -> tuple[str, ...]:
    warnings = []
    actual = f"{logo.width}x{logo.height}"
    if entry.declared_dimensions and entry.declared_dimensions != actual:
        warnings.append(
            f"dimensions annoncées {entry.declared_dimensions}, mesurées {actual} (retenues)."
        )
    if entry.key_template and not entry.key_template.endswith(logo.extension):
        warnings.append(
            f"le modèle de clé annonce une autre extension que {logo.extension}, "
            "tirée du contenu (retenue)."
        )
    return tuple(warnings)


async def _declare_logo(session: AsyncSession, entry: OrganisationLogo, id_media: int) -> None:
    await service.declarer_reference(
        session,
        MediaReferenceCreate(
            id_media=id_media,
            nature_code=LOGO_NATURE_CODE,
            label=entry.name,
            description=entry.alt,
        ),
        None,
    )


async def _resume_known_media(
    session: AsyncSession, entry: OrganisationLogo, media: Media
) -> tuple[LogoOutcome, str]:
    """Le fichier est déjà en bibliothèque : seule la référence peut encore manquer."""
    if media.deleted_at is not None:
        return LogoOutcome.SKIPPED, "Média archivé : laissé tel quel."
    archived_flags = [
        deleted_at is not None
        for deleted_at in (
            await session.execute(
                select(MediaReference.deleted_at).where(MediaReference.id_media == media.id_media)
            )
        ).scalars()
    ]
    if not archived_flags:
        await _declare_logo(session, entry, media.id_media)
        return LogoOutcome.IMPORTED, "Média déjà présent, déclaré comme référence."
    if all(archived_flags):
        return LogoOutcome.SKIPPED, "Référence retirée à l'écran : non redéclarée."
    return LogoOutcome.ALREADY_PRESENT, "Déjà importé."


async def _store_logo(
    session: AsyncSession,
    storage: Stockage,
    entry: OrganisationLogo,
    logo: _LogoFile,
    storage_key: str,
) -> None:
    """L'objet part d'abord, les lignes ensuite.

    Si l'écriture en base échoue, l'objet reste : sa clé dérive du contenu, la
    relance le réécrit à l'identique, et le retirer pourrait casser une ligne qui
    le désigne déjà.
    """
    size = await storage.deposer(storage_key, io.BytesIO(logo.content), logo.file_type)
    media = Media(
        storage_key=storage_key,
        file_type=logo.file_type,
        source="upload",
        display_name=entry.name,
        size_bytes=size,
        width=logo.width,
        height=logo.height,
    )
    session.add(media)
    await session.flush()
    await _declare_logo(session, entry, media.id_media)


async def import_logo(
    session: AsyncSession,
    storage: Stockage,
    entry: OrganisationLogo,
    transport: httpx.AsyncBaseTransport | None = None,
) -> LogoResult:
    """Rapatrie un logo et le déclare comme référence, sans valider la transaction.

    Raises:
        DownloadRefusedError: adresse refusée ou fichier trop lourd.
        ApiError: fichier qui n'est pas une image lisible, image trop grande ou
            stockage refusant le dépôt.
        httpx.HTTPError: panne réseau.
    """
    content = await download_image(
        entry.logo_url,
        allowed_hosts=LOGO_ALLOWED_HOSTS,
        # Un logo n'est jamais réencodé : au-delà du plafond rangé, il est refusé.
        max_bytes=get_settings().MEDIA_MAX_STORED_BYTES,
        timeout_seconds=LOGO_TIMEOUT_SECONDS,
        transport=transport,
    )
    logo = await run_in_threadpool(_inspect_image, content)
    prefix = f"organisations/{entry.code}/logo-"
    storage_key = f"{prefix}{hashlib.sha256(content).hexdigest()[:12]}{logo.extension}"

    known = (
        await session.execute(select(Media).where(Media.storage_key == storage_key))
    ).scalar_one_or_none()
    if known is not None:
        outcome, message = await _resume_known_media(session, entry, known)
    else:
        previous = (
            await session.execute(
                select(Media.storage_key)
                .where(
                    Media.storage_key.startswith(prefix, autoescape=True),
                    Media.deleted_at.is_(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if previous is None:
            await _store_logo(session, storage, entry, logo, storage_key)
            outcome, message = LogoOutcome.IMPORTED, "Importé."
        else:
            outcome, storage_key = LogoOutcome.SKIPPED, previous
            message = (
                "Le logo a changé sur le site. L'ancien est toujours en bibliothèque : "
                "l'archiver puis relancer pour reprendre le nouveau."
            )
    return LogoResult(entry.code, outcome, message, storage_key, _list_warnings(entry, logo))


async def import_logos(
    open_session: SessionOpener,
    storage: Stockage,
    entries: Sequence[dict[str, Any]],
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[LogoResult]:
    """Reprend chaque entrée dans sa propre transaction : un échec n'arrête pas le lot."""
    results: list[LogoResult] = []
    for position, raw in enumerate(entries, start=1):
        code = str(raw.get("code") or f"entrée n° {position}")
        try:
            entry = OrganisationLogo.model_validate(raw)
        except ValidationError as error:
            fields = ", ".join(sorted({str(detail["loc"][0]) for detail in error.errors()}))
            results.append(
                LogoResult(code, LogoOutcome.FAILED, f"Champs absents ou invalides : {fields}.")
            )
            continue
        try:
            async with open_session() as session:
                result = await import_logo(session, storage, entry, transport)
                await session.commit()
        except (DownloadRefusedError, ApiError) as error:
            result = LogoResult(code, LogoOutcome.FAILED, str(error))
        except Exception as error:
            # Réseau, stockage ou base indisponible : l'entrée suivante est tentée.
            logger.exception("Logo de l'organisation %s non repris", code)
            result = LogoResult(
                code, LogoOutcome.FAILED, f"Échec technique ({type(error).__name__})."
            )
        results.append(result)
    return results
