"""Reprise des webinaires du site : fichiers JSON puis flyers."""

import io
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image

from app.modules.webinars.import_schemas import Evenement
from app.modules.webinars.importer import dater

SITE = "https://datumacademy.com/storage/posts"


@pytest.fixture
async def entete(fabrique_utilisateur, connexion) -> dict[str, str]:  # type: ignore[no-untyped-def]
    utilisateur = await fabrique_utilisateur(droits=["manage_webinars"])
    jetons = await connexion(utilisateur.email)
    return {"Authorization": f"Bearer {jetons['access_token']}"}


def _fiche(slug: str, **champs: Any) -> dict[str, Any]:
    return {
        "slug": slug,
        "titre": {"fr": f"Titre {slug}", "en": f"Title {slug}"},
        "contenu": {"fr": "Contenu", "en": "Content"},
        "statut_suggere": "past",
        "categories": ["AI and BIG DATA"],
        "evenement": {},
        "flyer": {"url_source": f"{SITE}/{slug}.png"},
        "source": {"url_detail_fr": f"https://datumacademy.com/fr/webinars/details/{slug}"},
        "anomalies": ["date_a_valider"],
        **champs,
    }


def _fichiers() -> dict[str, tuple[str, bytes, str]]:
    webinaires = {
        "webinaires": [
            _fiche(
                "sant%C3%A9",
                replay={"urls": ["https://www.youtube.com/embed/abc"]},
                evenement={
                    "dates_detectees": [{"iso": "2024-07-18", "heure": "15:00", "fuseau": "GMT+1"}],
                    "publication_approximative": "2024-07-01",
                },
                inscription={
                    "pages": [
                        {"slug": "x-presentiel", "url": "https://datumacademy.com/p"},
                        {"slug": "x", "url": "https://datumacademy.com/en-ligne"},
                    ]
                },
            ),
            _fiche("ailleurs", flyer={"url_source": "https://attaquant.example/i.png"}),
            _fiche("casse", categories=["Nouveau thème"]),
        ]
    }
    pages = {
        "pages": [
            {
                "slug": "orpheline",
                "url": "https://datumacademy.com/fr/webinar/orpheline",
                "active": False,
                "calendar_from": "2022-02-14 14:00:00",
                "calendar_to": "2022-02-14 15:00:00",
                "webinaire_candidat": {"slug": "casse", "score": 0.84},
            }
        ]
    }
    return {
        "webinars_file": ("webinaires.json", json.dumps(webinaires).encode(), "application/json"),
        "pages_file": ("pages-inscription.json", json.dumps(pages).encode(), "application/json"),
    }


async def _importer(client: AsyncClient, entete: dict[str, str]) -> dict[str, Any]:
    reponse = await client.post("/api/v1/webinars/imports", files=_fichiers(), headers=entete)
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


async def _fiches(client: AsyncClient, entete: dict[str, str]) -> dict[str, dict[str, Any]]:
    liste = await client.get("/api/v1/webinars?size=100", headers=entete)
    return {item["title"]: item for item in liste.json()["items"]}


async def test_import_site_export_creates_webinars_and_pages(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    rapport = await _importer(client, entete)

    assert (rapport["webinars_created"], rapport["pages_created"]) == (3, 3)
    assert rapport["dates_to_confirm"] == 1
    assert rapport["pending_flyers"] == 3
    fiche = (await _fiches(client, entete))["Titre sant%C3%A9"]
    assert fiche["status_code"] == "past"
    assert fiche["starts_at"] == "2024-07-18T14:00:00Z"
    assert fiche["is_date_confirmed"] is False
    assert fiche["registration_url"] == "https://datumacademy.com/en-ligne"
    assert fiche["registration_count"] is None
    pages = await client.get(
        "/api/v1/webinars/registration-pages?unlinked_only=true", headers=entete
    )
    assert pages.json()[0]["candidate_title"] == "Titre casse"


async def test_import_site_export_twice_keeps_manual_changes(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    await _importer(client, entete)
    identifiant = (await _fiches(client, entete))["Titre casse"]["id_webinars"]
    await client.patch(f"/api/v1/webinars/{identifiant}", json={"title": "Corrigé"}, headers=entete)

    rapport = await _importer(client, entete)

    assert (rapport["webinars_created"], rapport["webinars_updated"]) == (0, 2)
    assert rapport["webinars_kept"] == 1
    assert "Corrigé" in await _fiches(client, entete)


async def test_link_registration_page_validates_the_candidate(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    await _importer(client, entete)
    page = (
        await client.get("/api/v1/webinars/registration-pages?unlinked_only=true", headers=entete)
    ).json()[0]

    reponse = await client.patch(
        f"/api/v1/webinars/registration-pages/{page['id_webinar_registration_pages']}",
        json={"id_webinars": page["id_webinars_candidate"]},
        headers=entete,
    )

    assert reponse.json()["webinar_title"] == "Titre casse"
    assert (await _fiches(client, entete))["Titre casse"]["registration_mode"] == "external"
    await _importer(client, entete)
    assert (await _fiches(client, entete))["Titre casse"]["registration_mode"] == "external"


async def test_import_site_export_wrong_shape_is_refused(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    reponse = await client.post(
        "/api/v1/webinars/imports",
        files={"webinars_file": ("webinaires.json", b'{"autre": 1}', "application/json")},
        headers=entete,
    )

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "invalid_import_file"


async def test_fetch_flyers_stores_images_and_refuses_the_rest(
    client: AsyncClient,
    entete: dict[str, str],
    faux_site: dict[str, bytes],
    stockage_de_test: Any,
) -> None:
    image = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(image, "PNG")
    faux_site[f"{SITE}/sant%C3%A9.png"] = image.getvalue()
    faux_site[f"{SITE}/casse.png"] = b"<html>pas une image</html>"
    await _importer(client, entete)

    premier = await client.post("/api/v1/webinars/flyers/fetch?limit=10", headers=entete)
    second = await client.post("/api/v1/webinars/flyers/fetch?limit=10", headers=entete)

    assert (premier.json()["stored"], premier.json()["failed"]) == (1, 2)
    assert (second.json()["stored"], second.json()["failed"]) == (0, 0)
    messages = " ".join(e["message"] for e in premier.json()["errors"])
    assert "hors du site" in messages
    assert "pas une image" in messages
    adresse = (await _fiches(client, entete))["Titre sant%C3%A9"]["flyer_url"]
    assert adresse.startswith("https://medias.test/webinaires/sante/flyer-origine-")
    assert adresse.endswith(".png")


async def test_import_site_export_keeps_an_uploaded_flyer(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    await _importer(client, entete)
    identifiant = (await _fiches(client, entete))["Titre casse"]["id_webinars"]
    image = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(image, "PNG")
    depot = await client.put(
        f"/api/v1/webinars/{identifiant}/flyer",
        files={"file": ("affiche.png", image.getvalue(), "image/png")},
        headers=entete,
    )

    rapport = await _importer(client, entete)
    lot = await client.post("/api/v1/webinars/flyers/fetch?limit=10", headers=entete)

    assert rapport["webinars_kept"] == 1
    assert rapport["pending_flyers"] == 2
    assert lot.json()["stored"] + lot.json()["failed"] == 2
    assert (await _fiches(client, entete))["Titre casse"]["flyer_url"] == depot.json()["flyer_url"]


@pytest.mark.parametrize(
    ("evenement", "attendu"),
    [
        (
            {"date_candidate": {"debut": "2022-09-09 09:00:00", "fin": "2022-09-09 11:00:00"}},
            (datetime(2022, 9, 9, 9, tzinfo=UTC), 120, False, True),
        ),
        (
            {"dates_detectees": [{"iso": "2024-01-24"}]},
            (datetime(2024, 1, 24, 12, tzinfo=UTC), None, False, False),
        ),
        ({}, (None, None, True, True)),
    ],
)
def test_dater_uses_the_best_available_hint(
    evenement: dict[str, Any], attendu: tuple[Any, ...]
) -> None:
    date = dater(Evenement.model_validate(evenement))

    assert (date.starts_at, date.duration_minutes, date.is_confirmed, date.is_time_known) == attendu
