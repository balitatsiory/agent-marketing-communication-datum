"""Reprise des logos d'organisations.

Le site est simulé par un transport local et le stockage est un dossier jetable :
aucun appel réseau, aucun dépôt dans Cloudflare.
"""

import hashlib
import io
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import StockageLocal
from app.modules.media import service
from app.modules.media.logo_import import LogoOutcome, LogoResult, import_logos
from app.modules.media.models import Media, MediaReference

SITE = "https://datumacademy.com/images/partners/"


def image(couleur: str = "red", format_pillow: str = "PNG") -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (40, 20), couleur).save(tampon, format=format_pillow)
    return tampon.getvalue()


def organisation(code: str = "oracle", **valeurs: Any) -> dict[str, Any]:
    return {
        "code": code,
        "nom": f"Organisation {code}",
        "role": "partenaire_industriel",
        "logo": f"{SITE}{code}.png",
        "alt": f"Logo {code}",
        "dimensions": "40x20",
        "cle_r2_modele": f"organisations/{code}/logo-{{sha12}}.png",
    } | valeurs


@pytest.fixture
def importer(session: AsyncSession, stockage_de_test: StockageLocal):  # type: ignore[no-untyped-def]
    """Lance la reprise contre un site qui sert le contenu du dictionnaire fourni."""

    @asynccontextmanager
    async def ouvrir() -> AsyncIterator[AsyncSession]:
        yield session

    async def lancer(
        entrees: list[dict[str, Any]], site: dict[str, bytes | httpx.Response]
    ) -> list[LogoResult]:
        def repondre(requete: httpx.Request) -> httpx.Response:
            servi = site.get(str(requete.url), httpx.Response(404))
            return (
                servi if isinstance(servi, httpx.Response) else httpx.Response(200, content=servi)
            )

        return await import_logos(ouvrir, stockage_de_test, entrees, httpx.MockTransport(repondre))

    return lancer


async def compter(session: AsyncSession, modele: type[Media] | type[MediaReference]) -> int:
    return int((await session.execute(select(func.count()).select_from(modele))).scalar_one())


def fichiers_ranges(racine: Path) -> list[Path]:
    return [chemin for chemin in racine.rglob("*") if chemin.is_file()]


async def test_import_logo_range_le_fichier_et_declare_une_reference_logo(
    importer, session: AsyncSession, tmp_path: Path
) -> None:
    contenu = image()

    [resultat] = await importer([organisation()], {f"{SITE}oracle.png": contenu})

    cle = f"organisations/oracle/logo-{hashlib.sha256(contenu).hexdigest()[:12]}.png"
    assert resultat.outcome == LogoOutcome.IMPORTED
    assert resultat.storage_key == cle
    assert resultat.warnings == ()
    assert (tmp_path / "medias" / cle).read_bytes() == contenu

    media = (await session.execute(select(Media).where(Media.storage_key == cle))).scalar_one()
    assert (media.file_type, media.width, media.height) == ("image/png", 40, 20)
    assert media.size_bytes == len(contenu)
    reference = (
        await session.execute(
            select(MediaReference).where(MediaReference.id_media == media.id_media)
        )
    ).scalar_one()
    assert reference.label == "Organisation oracle"
    assert reference.description == "Logo oracle"
    assert await service.code_de_nature(session, reference.id_media_reference_natures) == "logo"


async def test_import_logos_relance_ne_cree_aucun_doublon(
    importer, session: AsyncSession, tmp_path: Path
) -> None:
    entrees = [organisation("oracle"), organisation("fun")]
    site = {f"{SITE}oracle.png": image("red"), f"{SITE}fun.png": image("blue")}
    medias = await compter(session, Media)
    references = await compter(session, MediaReference)

    await importer(entrees, site)
    seconde = await importer(entrees, site)

    assert [r.outcome for r in seconde] == [LogoOutcome.ALREADY_PRESENT] * 2
    assert await compter(session, Media) == medias + 2
    assert await compter(session, MediaReference) == references + 2
    assert len(fichiers_ranges(tmp_path / "medias")) == 2


async def test_import_logo_extension_tiree_du_contenu_signale_l_ecart(importer) -> None:
    [resultat] = await importer(
        [organisation(dimensions="999x999")],
        {f"{SITE}oracle.png": image(format_pillow="JPEG")},
    )

    assert resultat.storage_key is not None
    assert resultat.storage_key.endswith(".jpg")
    assert len(resultat.warnings) == 2


@pytest.mark.parametrize(
    "servi",
    [
        b"<html>introuvable</html>",
        image()[:40],
        b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20,
        httpx.Response(404),
        httpx.Response(302, headers={"Location": "https://exemple.test/logo.png"}),
    ],
    ids=["page-html", "image-tronquee", "video", "absent", "redirection"],
)
async def test_import_logo_contenu_refuse_n_ecrit_rien(
    importer, session: AsyncSession, tmp_path: Path, servi: bytes | httpx.Response
) -> None:
    medias = await compter(session, Media)

    [resultat] = await importer([organisation()], {f"{SITE}oracle.png": servi})

    assert resultat.outcome == LogoOutcome.FAILED
    assert resultat.message
    assert await compter(session, Media) == medias
    assert fichiers_ranges(tmp_path / "medias") == []


@pytest.mark.parametrize(
    "adresse",
    ["http://datumacademy.com/logo.png", "https://exemple.test/logo.png"],
)
async def test_import_logo_adresse_hors_du_site_est_refusee(importer, adresse: str) -> None:
    [resultat] = await importer([organisation(logo=adresse)], {adresse: image()})

    assert resultat.outcome == LogoOutcome.FAILED
    assert "hors du site" in resultat.message


async def test_import_logo_trop_lourd_est_refuse(importer, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    contenu = image()
    monkeypatch.setattr(get_settings(), "MEDIA_MAX_STORED_BYTES", len(contenu) - 1)

    [resultat] = await importer([organisation()], {f"{SITE}oracle.png": contenu})

    assert resultat.outcome == LogoOutcome.FAILED
    assert "trop lourde" in resultat.message


async def test_import_logos_entree_invalide_n_arrete_pas_le_lot(importer) -> None:
    resultats = await importer(
        [organisation(code="../evasion"), organisation("fun")],
        {f"{SITE}fun.png": image()},
    )

    assert [r.outcome for r in resultats] == [LogoOutcome.FAILED, LogoOutcome.IMPORTED]
    assert "code" in resultats[0].message


async def test_import_logo_media_archive_n_est_pas_ressuscite(
    importer, session: AsyncSession, fabrique_utilisateur
) -> None:
    site = {f"{SITE}oracle.png": image()}
    [premier] = await importer([organisation()], site)
    media = (
        await session.execute(select(Media).where(Media.storage_key == premier.storage_key))
    ).scalar_one()
    await service.archiver(session, media.id_media, await fabrique_utilisateur())
    references = await compter(session, MediaReference)

    [second] = await importer([organisation()], site)

    assert second.outcome == LogoOutcome.SKIPPED
    assert media.deleted_at is not None
    assert await compter(session, MediaReference) == references


async def test_import_logo_reference_retiree_n_est_pas_redeclaree(
    importer, session: AsyncSession, fabrique_utilisateur
) -> None:
    site = {f"{SITE}oracle.png": image()}
    [premier] = await importer([organisation()], site)
    reference = (
        await session.execute(
            select(MediaReference)
            .join(Media, Media.id_media == MediaReference.id_media)
            .where(Media.storage_key == premier.storage_key)
        )
    ).scalar_one()
    await service.archiver_reference(
        session, reference.id_media_references, await fabrique_utilisateur()
    )
    references = await compter(session, MediaReference)

    [second] = await importer([organisation()], site)

    assert second.outcome == LogoOutcome.SKIPPED
    assert await compter(session, MediaReference) == references


async def test_import_logo_change_sur_le_site_attend_l_archivage_de_l_ancien(
    importer, session: AsyncSession, fabrique_utilisateur
) -> None:
    [ancien] = await importer([organisation()], {f"{SITE}oracle.png": image("red")})
    nouveau_site = {f"{SITE}oracle.png": image("blue")}
    medias = await compter(session, Media)

    [bloque] = await importer([organisation()], nouveau_site)

    assert bloque.outcome == LogoOutcome.SKIPPED
    assert bloque.storage_key == ancien.storage_key
    assert await compter(session, Media) == medias

    media = (
        await session.execute(select(Media).where(Media.storage_key == ancien.storage_key))
    ).scalar_one()
    await service.archiver(session, media.id_media, await fabrique_utilisateur())

    [repris] = await importer([organisation()], nouveau_site)

    assert repris.outcome == LogoOutcome.IMPORTED
    assert repris.storage_key != ancien.storage_key
