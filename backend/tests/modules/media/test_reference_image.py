"""Remplacement de l'image d'une référence à partir d'une adresse.

Les sites et leur résolution DNS sont simulés (`faux_site`, `faux_dns`) : aucun
test n'appelle dehors.
"""

import io
from typing import Any

import pytest
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import StockageLocal
from app.modules.media import service
from app.modules.media.models import Media
from tests.conftest import entete

SITE = "https://images.example.com"
LINK = f"{SITE}/partenaires/logo%20officiel.png?v=2"
BOTH_RIGHTS = ["manage_media", "manage_media_reference"]


def image(colour: str = "red", image_format: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), colour).save(buffer, format=image_format)
    return buffer.getvalue()


async def create_reference(client: AsyncClient, tokens: dict[str, str]) -> dict[str, Any]:
    upload = await client.post(
        "/api/v1/media",
        headers=entete(tokens),
        files={"fichier": ("ancien.png", io.BytesIO(image("blue")), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    reference = await client.post(
        "/api/v1/media-references",
        headers=entete(tokens),
        json={"id_media": upload.json()["id_media"], "nature_code": "logo", "label": "Partenaire"},
    )
    assert reference.status_code == 201, reference.text
    return dict(reference.json())


async def replace_image(
    client: AsyncClient, tokens: dict[str, str], id_reference: int, url: str = LINK
) -> Response:
    return await client.post(
        f"/api/v1/media-references/{id_reference}/image",
        headers=entete(tokens),
        json={"url": url},
    )


async def read_media(client: AsyncClient, tokens: dict[str, str], id_media: int) -> dict[str, Any]:
    response = await client.get(f"/api/v1/media/{id_media}", headers=entete(tokens))
    assert response.status_code == 200, response.text
    return dict(response.json())


async def assert_nothing_changed(
    client: AsyncClient,
    session: AsyncSession,
    tokens: dict[str, str],
    reference: dict[str, Any],
) -> None:
    listing = await client.get("/api/v1/media-references", headers=entete(tokens))
    [current] = listing.json()["items"]
    assert current["id_media"] == reference["id_media"]
    assert await session.scalar(select(func.count()).select_from(Media)) == 1


@pytest.fixture
async def tokens(fabrique_utilisateur, connexion) -> dict[str, str]:  # type: ignore[no-untyped-def]
    manager = await fabrique_utilisateur(droits=BOTH_RIGHTS)
    return dict(await connexion(manager.email))


class TestReplaceImage:
    async def test_replace_image_from_link_gives_the_reference_a_new_media(
        self,
        client: AsyncClient,
        tokens: dict[str, str],
        faux_site: dict[str, bytes],
        stockage_de_test: StockageLocal,
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = content = image("red")

        response = await replace_image(client, tokens, reference["id_media_references"])

        assert response.status_code == 200, response.text
        updated = response.json()
        assert updated["id_media"] != reference["id_media"]
        assert (updated["label"], updated["nature_code"]) == ("Partenaire", "logo")

        media = await read_media(client, tokens, updated["id_media"])
        assert media["display_name"] == "logo officiel.png"
        assert (media["file_type"], media["width"], media["height"]) == ("image/png", 40, 20)
        # Le lien montré à l'écran est celui de la copie, jamais l'adresse saisie.
        assert media["url"].startswith("https://medias.test/")
        key = media["url"].removeprefix("https://medias.test/")
        assert (stockage_de_test._racine / key).read_bytes() == content

    async def test_replace_image_keeps_the_previous_media_in_the_library(
        self, client: AsyncClient, tokens: dict[str, str], faux_site: dict[str, bytes]
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = image()

        await replace_image(client, tokens, reference["id_media_references"])

        previous = await read_media(client, tokens, reference["id_media"])
        assert previous["deleted_at"] is None

    async def test_replace_image_link_without_file_name_uses_the_reference_label(
        self, client: AsyncClient, tokens: dict[str, str], faux_site: dict[str, bytes]
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[f"{SITE}/"] = image(image_format="JPEG")

        response = await replace_image(
            client, tokens, reference["id_media_references"], f"  {SITE}/  "
        )

        assert response.status_code == 200, response.text
        media = await read_media(client, tokens, response.json()["id_media"])
        assert (media["display_name"], media["file_type"]) == ("Partenaire", "image/jpeg")


class TestRequiredRights:
    async def test_replace_image_without_token_is_unauthenticated(
        self, client: AsyncClient
    ) -> None:
        response = await client.post("/api/v1/media-references/1/image", json={"url": LINK})

        assert response.status_code == 401

    @pytest.mark.parametrize("right", BOTH_RIGHTS)
    async def test_replace_image_with_one_right_only_is_forbidden(
        self,
        client: AsyncClient,
        session: AsyncSession,
        tokens: dict[str, str],
        faux_site: dict[str, bytes],
        fabrique_utilisateur,
        connexion,
        right: str,
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = image()
        partial = await fabrique_utilisateur(droits=[right])

        response = await replace_image(
            client, await connexion(partial.email), reference["id_media_references"]
        )

        assert response.status_code == 403
        await assert_nothing_changed(client, session, tokens, reference)


class TestRefusedLinks:
    @pytest.mark.parametrize(
        "url",
        [
            "http://images.example.com/logo.png",
            "ftp://images.example.com/logo.png",
            "/medias/2026/11/logo.png",
            "logo.png",
            "https://",
            "https://images.example.com:8443/logo.png",
            "https://user:secret@images.example.com/logo.png",
            "https://127.0.0.1/logo.png",
            "https://[::1]/logo.png",
            "https://169.254.169.254/latest/meta-data/",
            "https://intranet.example.com/logo.png",
            "https://absent.example.com/logo.png",
        ],
    )
    async def test_replace_image_refused_link_changes_nothing(
        self,
        client: AsyncClient,
        session: AsyncSession,
        tokens: dict[str, str],
        faux_site: dict[str, bytes],
        faux_dns: dict[str, list[str]],
        url: str,
    ) -> None:
        reference = await create_reference(client, tokens)
        # Le fichier existe à cette adresse : seul le contrôle du lien l'écarte.
        faux_site[url] = image()
        faux_dns["intranet.example.com"] = ["10.0.0.12"]
        faux_dns["absent.example.com"] = []

        response = await replace_image(client, tokens, reference["id_media_references"], url)

        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "image_link_refused"
        await assert_nothing_changed(client, session, tokens, reference)

    async def test_replace_image_missing_file_is_refused(
        self, client: AsyncClient, session: AsyncSession, tokens: dict[str, str]
    ) -> None:
        reference = await create_reference(client, tokens)

        response = await replace_image(client, tokens, reference["id_media_references"])

        assert response.status_code == 422
        assert "404" in response.json()["error"]["message"]
        await assert_nothing_changed(client, session, tokens, reference)

    @pytest.mark.parametrize(
        "content",
        [
            b"<!doctype html><title>Page</title>",
            b"<svg xmlns='http://www.w3.org/2000/svg'/>",
            image()[:40],
            # L'en-tête est entier, les pixels coupés.
            image()[:-20],
            b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64,
            b"",
        ],
        ids=["page-html", "svg", "en-tete-coupe", "pixels-coupes", "video", "vide"],
    )
    async def test_replace_image_not_an_image_changes_nothing(
        self,
        client: AsyncClient,
        session: AsyncSession,
        tokens: dict[str, str],
        faux_site: dict[str, bytes],
        content: bytes,
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = content

        response = await replace_image(client, tokens, reference["id_media_references"])

        assert response.status_code == 415, response.text
        assert response.json()["error"]["code"] == "not_an_image"
        await assert_nothing_changed(client, session, tokens, reference)

    async def test_replace_image_too_heavy_is_refused(
        self,
        client: AsyncClient,
        session: AsyncSession,
        tokens: dict[str, str],
        faux_site: dict[str, bytes],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = image()
        monkeypatch.setattr(service, "IMAGE_LINK_MAX_BYTES", 10)

        response = await replace_image(client, tokens, reference["id_media_references"])

        assert response.status_code == 422
        assert "trop lourde" in response.json()["error"]["message"]
        await assert_nothing_changed(client, session, tokens, reference)

    @pytest.mark.parametrize("url", ["", f"{SITE}/{'a' * 2048}"], ids=["vide", "trop-longue"])
    async def test_replace_image_invalid_body_is_rejected(
        self, client: AsyncClient, tokens: dict[str, str], url: str
    ) -> None:
        response = await replace_image(client, tokens, 1, url)

        assert response.status_code == 422


class TestReferenceState:
    async def test_replace_image_unknown_reference_is_not_found(
        self, client: AsyncClient, tokens: dict[str, str]
    ) -> None:
        response = await replace_image(client, tokens, 999_999)

        assert response.status_code == 404

    async def test_replace_image_archived_reference_raises_conflict(
        self, client: AsyncClient, tokens: dict[str, str], faux_site: dict[str, bytes]
    ) -> None:
        reference = await create_reference(client, tokens)
        faux_site[LINK] = image()
        await client.delete(
            f"/api/v1/media-references/{reference['id_media_references']}",
            headers=entete(tokens),
        )

        response = await replace_image(client, tokens, reference["id_media_references"])

        assert response.status_code == 409
