"""Un test par défaut relevé en revue de la PR 29 (CONTRIBUTING §9)."""

import io
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.webinars import flyers
from app.modules.zoom_accounts import service as zoom_accounts_service
from app.modules.zoom_accounts.models import ZoomAccount
from app.modules.zoom_accounts.zoom_client import ZoomClient, ZoomError
from tests.faux_zoom import API_URL, CLIENT_ID, CLIENT_SECRET, HOTE, OAUTH_URL, FauxZoom

FUTUR = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0, second=0)


@pytest.fixture
async def entete(fabrique_utilisateur, connexion):  # type: ignore[no-untyped-def]
    utilisateur = await fabrique_utilisateur(
        droits=["manage_webinars", "create_zoom_meetings", "manage_zoom_accounts"]
    )
    jetons = await connexion(utilisateur.email)
    return {"Authorization": f"Bearer {jetons['access_token']}"}


@pytest.fixture
async def compte(client: AsyncClient, entete: dict[str, str]) -> int:
    reponse = await client.post(
        "/api/v1/zoom-accounts",
        json={
            "label": "Datum",
            "host_email": HOTE,
            "external_zoom_account_id": "compte-essai",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers=entete,
    )
    return int(reponse.json()["account"]["id_zoom_accounts"])


async def _brouillon(client: AsyncClient, entete: dict[str, str], **champs: Any) -> dict[str, Any]:
    reponse = await client.post(
        "/api/v1/webinars", json={"title": "Atelier", **champs}, headers=entete
    )
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


def _complet(compte: int, **champs: Any) -> dict[str, Any]:
    return {
        "category_codes": ["ai_and_big_data"],
        "starts_at": FUTUR.isoformat(),
        "id_zoom_accounts": compte,
        **champs,
    }


async def _programmer(
    client: AsyncClient, entete: dict[str, str], compte: int, **champs: Any
) -> dict[str, Any]:
    fiche = await _brouillon(client, entete, **_complet(compte, **champs))
    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def _fiche(slug: str, **champs: Any) -> dict[str, Any]:
    return {"slug": slug, "titre": {"fr": slug}, **champs}


async def _importer(client: AsyncClient, entete: dict[str, str], *fiches: Any) -> httpx.Response:
    contenu = json.dumps({"webinaires": list(fiches)}).encode()
    return await client.post(
        "/api/v1/webinars/imports",
        files={"webinars_file": ("webinaires.json", contenu, "application/json")},
        headers=entete,
    )


async def _par_titre(client: AsyncClient, entete: dict[str, str]) -> dict[str, Any]:
    liste = await client.get("/api/v1/webinars?size=100", headers=entete)
    return {item["title"]: item for item in liste.json()["items"]}


# --- base de données ------------------------------------------------------


def test_migrations_have_a_single_head() -> None:
    tetes = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()

    assert len(tetes) == 1, f"« alembic upgrade head » échouerait : {tetes}"


async def test_refresh_from_zoom_lock_lets_registrations_through(
    client: AsyncClient, entete: dict[str, str], compte: int, session: AsyncSession
) -> None:
    fiche = await _programmer(client, entete, compte)
    requetes: list[str] = []
    connexion = (await session.connection()).sync_connection
    assert connexion is not None

    def noter(_c: Any, _cur: Any, requete: str, *_: Any) -> None:
        requetes.append(requete)

    event.listen(connexion, "before_cursor_execute", noter)
    try:
        await client.post(
            f"/api/v1/webinars/{fiche['id_webinars']}/refresh-from-zoom", headers=entete
        )
    finally:
        event.remove(connexion, "before_cursor_execute", noter)

    verrous = [r for r in requetes if "FROM webinars" in r and "UPDATE" in r.split("WHERE")[-1]]
    assert verrous
    assert all("FOR NO KEY UPDATE" in r for r in verrous)


# --- import et flyers -----------------------------------------------------


@pytest.mark.parametrize(
    "categories",
    [["Santé", "Sante"], ["AI-and-BIG-DATA"], ["数据", "人工"], ["x" * 200]],
)
async def test_import_colliding_category_codes_succeeds_and_replays(
    client: AsyncClient, entete: dict[str, str], categories: list[str]
) -> None:
    fiche = _fiche("c", categories=categories)

    premier = await _importer(client, entete, fiche)
    avant = (await client.get("/api/v1/webinars/reference", headers=entete)).json()
    second = await _importer(client, entete, fiche)
    apres = (await client.get("/api/v1/webinars/reference", headers=entete)).json()

    assert (premier.status_code, second.status_code) == (200, 200), premier.text
    assert avant["categories"] == apres["categories"]
    assert len((await _par_titre(client, entete))["c"]["categories"]) == len(categories)


async def test_import_negative_duration_is_refused_readably(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    reponse = await _importer(client, entete, _fiche("n", evenement={"duree_minutes": -1}))

    assert reponse.status_code == 422
    assert "duree_minutes" in reponse.json()["error"]["message"]


async def test_import_impossible_time_keeps_the_day(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    evenement = {"dates_detectees": [{"iso": "2024-07-18", "heure": "24:00"}]}

    reponse = await _importer(client, entete, _fiche("h", evenement=evenement))

    assert reponse.status_code == 200, reponse.text
    fiche = (await _par_titre(client, entete))["h"]
    assert fiche["starts_at"] == "2024-07-18T12:00:00Z"
    assert fiche["is_time_known"] is False


async def test_fetch_flyers_source_changed_meanwhile_keeps_it_pending(
    client: AsyncClient, entete: dict[str, str], session: AsyncSession, stockage_de_test: Any
) -> None:
    ancienne = "https://datumacademy.com/a.png"
    await _importer(client, entete, _fiche("f", flyer={"url_source": ancienne}))
    image = io.BytesIO()
    Image.new("RGB", (2, 2)).save(image, "PNG")

    async def pendant_le_telechargement(_: httpx.Request) -> httpx.Response:
        await session.execute(
            text("UPDATE webinars SET flyer_source_url = 'https://datumacademy.com/b.png'")
        )
        return httpx.Response(200, content=image.getvalue())

    resultat = await flyers.fetch_pending_flyers(
        session,
        stockage_de_test,
        5,
        transport=httpx.MockTransport(pendant_le_telechargement),
    )

    assert (resultat.stored, resultat.failed, resultat.remaining) == (0, 0, 1)
    cle = (await session.execute(text("SELECT flyer_storage_key FROM webinars"))).scalar_one()
    assert cle is None


async def test_link_registration_page_moved_clears_the_previous_webinar(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    page = {"slug": "p", "url": "https://datumacademy.com/p"}
    await _importer(client, entete, _fiche("a", inscription={"pages": [page]}), _fiche("b"))
    fiches = await _par_titre(client, entete)
    connue = (await client.get("/api/v1/webinars/registration-pages", headers=entete)).json()[0]

    await client.patch(
        f"/api/v1/webinars/registration-pages/{connue['id_webinar_registration_pages']}",
        json={"id_webinars": fiches["b"]["id_webinars"]},
        headers=entete,
    )

    apres = await _par_titre(client, entete)
    assert (apres["a"]["registration_mode"], apres["a"]["registration_url"]) == ("none", None)
    assert apres["b"]["registration_url"] == page["url"]


# --- inscriptions ---------------------------------------------------------


async def test_sync_registrants_erased_address_is_not_restored(
    client: AsyncClient,
    entete: dict[str, str],
    compte: int,
    faux_zoom: FauxZoom,
    session: AsyncSession,
) -> None:
    fiche = await _programmer(client, entete, compte, registration_mode="iagora_form")
    base = f"/api/v1/webinars/{fiche['id_webinars']}/registrations"
    cree = await client.post(
        base,
        json={"email": "x@example.com", "first_name": "Xavier", "last_name": "Yves"},
        headers=entete,
    )
    await client.delete(f"{base}/{cree.json()['id_webinar_registrations']}", headers=entete)
    faux_zoom.inscrits[fiche["external_zoom_meeting_id"]].append(
        {"id": "autre", "email": "neuf@example.com", "status": "approved"}
    )

    reponse = await client.post(f"{base}/zoom-sync", headers=entete)

    assert reponse.json()["created"] == 1
    emails = [i["email"] for i in (await client.get(base, headers=entete)).json()["items"]]
    assert sorted(e for e in emails if e) == ["neuf@example.com"]
    conserve = (
        await session.execute(text("SELECT string_agg(r::text, ' ') FROM webinar_registrations r"))
    ).scalar_one()
    assert "x@example.com" not in conserve
    assert "Xavier" not in conserve


async def test_public_registration_zoom_refusal_promises_nothing_false(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    fiche = await _programmer(client, entete, compte, registration_mode="iagora_form")
    faux_zoom.refus[("POST", f"/meetings/{fiche['external_zoom_meeting_id']}/registrants")] = (
        400,
        {"code": 200, "message": "Only available for paid users."},
    )

    reponse = await client.post(
        f"/api/v1/public/registration-pages/{fiche['form_slug']}/registrations",
        json={"email": "z@example.com", "first_name": "Zo", "last_name": "Ra"},
    )

    assert "est envoyé" not in reponse.json()["message"]
    assert "contactez" in reponse.json()["message"]


async def test_add_registration_concurrent_duplicate_is_a_conflict(
    client: AsyncClient, entete: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.webinars import registration_service

    fiche = await _brouillon(client, entete)
    base = f"/api/v1/webinars/{fiche['id_webinars']}/registrations"
    personne = {"email": "d@example.com", "first_name": "Do", "last_name": "Ra"}
    await client.post(base, json=personne, headers=entete)
    vraie = registration_service._trouver
    appels = {"n": 0}

    async def aveugle_une_fois(*arguments: Any) -> Any:
        # La recherche préalable ne voit rien, comme lors de deux envois simultanés.
        appels["n"] += 1
        return None if appels["n"] == 1 else await vraie(*arguments)

    monkeypatch.setattr(registration_service, "_trouver", aveugle_une_fois)

    reponse = await client.post(base, json=personne, headers=entete)

    assert reponse.status_code == 409


# --- fiches et Zoom -------------------------------------------------------


async def test_update_webinar_scheduled_to_zoom_is_refused(
    client: AsyncClient, entete: dict[str, str], compte: int
) -> None:
    fiche = await _brouillon(
        client,
        entete,
        category_codes=["ai_and_big_data"],
        starts_at=FUTUR.isoformat(),
        link_mode="manual",
        join_url="https://meet.example.com/x",
    )
    adresse = f"/api/v1/webinars/{fiche['id_webinars']}"
    await client.post(f"{adresse}/schedule", headers=entete)

    reponse = await client.patch(
        adresse, json={"link_mode": "zoom_auto", "id_zoom_accounts": compte}, headers=entete
    )

    assert reponse.status_code == 409
    relue = (await client.get(adresse, headers=entete)).json()
    assert relue["join_url"] == "https://meet.example.com/x"


async def test_update_webinar_draft_can_still_switch_to_zoom(
    client: AsyncClient, entete: dict[str, str], compte: int
) -> None:
    fiche = await _brouillon(client, entete, link_mode="manual")

    reponse = await client.patch(
        f"/api/v1/webinars/{fiche['id_webinars']}",
        json={"link_mode": "zoom_auto", "id_zoom_accounts": compte},
        headers=entete,
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["id_zoom_accounts"] == compte


def _perdre_la_premiere_reponse(faux_zoom: FauxZoom) -> None:
    normal = faux_zoom.repondre
    perdu = {"deja": False}

    def repondre(requete: httpx.Request) -> httpx.Response:
        reponse = normal(requete)
        creation = requete.method == "POST" and requete.url.path.endswith("/meetings")
        if creation and not perdu["deja"]:
            perdu["deja"] = True
            raise httpx.ReadTimeout("réponse perdue", request=requete)
        return reponse

    faux_zoom.repondre = repondre  # type: ignore[method-assign]


async def test_schedule_webinar_after_a_lost_response_reuses_the_meeting(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    fiche = await _brouillon(client, entete, **_complet(compte))
    _perdre_la_premiere_reponse(faux_zoom)
    adresse = f"/api/v1/webinars/{fiche['id_webinars']}/schedule"

    premier = await client.post(adresse, headers=entete)
    second = await client.post(adresse, headers=entete)

    assert (premier.status_code, second.status_code) == (502, 200), second.text
    assert len(faux_zoom.reunions) == 1
    assert second.json()["external_zoom_meeting_id"] in faux_zoom.reunions


async def test_schedule_webinar_identical_meeting_without_registration_conflicts(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    faux_zoom.ajouter_reunion(topic="Atelier", start_time=f"{FUTUR:%Y-%m-%dT%H:%M:%SZ}")
    fiche = await _brouillon(client, entete, **_complet(compte, registration_mode="iagora_form"))

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)

    assert reponse.status_code == 409
    assert len(faux_zoom.reunions) == 1


@pytest.mark.parametrize("nouvel_ordre", ["Ordre du jour", ""])
async def test_refresh_from_zoom_takes_a_shortened_agenda(
    client: AsyncClient,
    entete: dict[str, str],
    compte: int,
    faux_zoom: FauxZoom,
    nouvel_ordre: str,
) -> None:
    reunion = faux_zoom.ajouter_reunion(agenda="Ordre du jour complet")
    fiche = await client.post(
        "/api/v1/webinars/zoom-meetings",
        json={"id_zoom_accounts": compte, "meeting_id": str(reunion["id"])},
        headers=entete,
    )
    reunion["agenda"] = nouvel_ordre

    relue = await client.post(
        f"/api/v1/webinars/{fiche.json()['id_webinars']}/refresh-from-zoom", headers=entete
    )

    assert relue.json()["description"] == (nouvel_ordre or None)


@pytest.mark.parametrize("numero", [" " * 9, "1 2 3", "12345678 "])
async def test_import_meeting_without_enough_digits_is_invalid(
    client: AsyncClient, entete: dict[str, str], compte: int, numero: str
) -> None:
    reponse = await client.post(
        "/api/v1/webinars/zoom-meetings",
        json={"id_zoom_accounts": compte, "meeting_id": numero},
        headers=entete,
    )

    assert reponse.status_code == 422


async def test_fetch_token_credentials_changed_meanwhile_is_discarded(
    compte: int, session: AsyncSession, faux_zoom: FauxZoom
) -> None:
    async def pendant_la_demande(requete: httpx.Request) -> httpx.Response:
        await session.execute(
            text("UPDATE zoom_accounts SET client_id = 'autre', access_token_encrypted = NULL")
        )
        return faux_zoom.repondre(requete)

    client = ZoomClient(OAUTH_URL, API_URL, httpx.MockTransport(pendant_la_demande))
    ligne = await session.get(ZoomAccount, compte)
    assert ligne is not None

    with pytest.raises(ApiError) as refus:
        await zoom_accounts_service._obtenir_jeton(session, client, ligne)

    assert refus.value.code == "zoom_credentials_changed"
    jeton = (
        await session.execute(text("SELECT access_token_encrypted FROM zoom_accounts"))
    ).scalar_one()
    assert jeton is None


def _client_qui_repond(reponse: httpx.Response) -> ZoomClient:
    return ZoomClient(OAUTH_URL, API_URL, httpx.MockTransport(lambda _: reponse))


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(200, text="<html>portail captif</html>"),
        httpx.Response(200, json=["pas", "un", "objet"]),
        httpx.Response(400, json={"message": "Refus", "errors": 1}),
    ],
)
async def test_request_malformed_zoom_response_raises_zoom_error(
    reponse: httpx.Response,
) -> None:
    with pytest.raises(ZoomError):
        await _client_qui_repond(reponse).request("GET", "/x", "jeton")


@pytest.mark.parametrize("duree", ["abc", 0, -5, {"valeur": 1}])
async def test_fetch_token_unreadable_expiry_raises_zoom_error(duree: Any) -> None:
    reponse = httpx.Response(200, json={"access_token": "t", "expires_in": duree})

    with pytest.raises(ZoomError):
        await _client_qui_repond(reponse).fetch_token("a", "b", "c")


async def test_request_no_content_is_a_success() -> None:
    assert await _client_qui_repond(httpx.Response(204)).request("PATCH", "/x", "jeton") == {}
