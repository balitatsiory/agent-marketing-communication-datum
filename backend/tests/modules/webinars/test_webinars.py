"""Webinaires : brouillons, réunions Zoom, listes, statistiques, inscriptions."""

import csv
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import StockageLocal
from app.modules.webinars import flyers
from app.modules.webinars.models import Webinar, WebinarRegistration
from tests.faux_zoom import CLIENT_ID, CLIENT_SECRET, HOTE, FauxZoom

TOUS = ("manage_webinars", "create_zoom_meetings", "manage_zoom_accounts")
FUTUR = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0, second=0)


@pytest.fixture
def ouvrir(fabrique_utilisateur, connexion):  # type: ignore[no-untyped-def]
    async def entete_de(*droits: str) -> dict[str, str]:
        utilisateur = await fabrique_utilisateur(droits=list(droits))
        jetons = await connexion(utilisateur.email)
        return {"Authorization": f"Bearer {jetons['access_token']}"}

    return entete_de


@pytest.fixture
async def entete(ouvrir: Any) -> dict[str, str]:
    return dict(await ouvrir(*TOUS))


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
    assert reponse.status_code == 201, reponse.text
    return int(reponse.json()["account"]["id_zoom_accounts"])


async def _brouillon(client: AsyncClient, entete: dict[str, str], **champs: Any) -> dict[str, Any]:
    corps = {"title": "Le RAG en pratique", **champs}
    reponse = await client.post("/api/v1/webinars", json=corps, headers=entete)
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


def _complet(compte: int, **champs: Any) -> dict[str, Any]:
    return {
        "category_codes": ["ai_and_big_data"],
        "starts_at": FUTUR.isoformat(),
        "duration_minutes": 90,
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


# --- création -------------------------------------------------------------


async def test_create_webinar_title_only_makes_a_draft(
    client: AsyncClient, entete: dict[str, str], faux_zoom: FauxZoom
) -> None:
    fiche = await _brouillon(client, entete)

    assert fiche["status_code"] == "draft"
    assert fiche["registration_count"] == 0
    assert faux_zoom.appels == []


async def test_schedule_webinar_creates_the_zoom_meeting(
    client: AsyncClient,
    entete: dict[str, str],
    compte: int,
    faux_zoom: FauxZoom,
    session: AsyncSession,
) -> None:
    fiche = await _programmer(
        client,
        entete,
        compte,
        registration_mode="iagora_form",
        meeting_settings={"passcode": "datum1", "waiting_room": False},
    )

    assert fiche["status_code"] == "scheduled"
    assert fiche["external_zoom_meeting_id"] is not None
    assert fiche["form_slug"].startswith("le-rag-en-pratique-")
    demande = faux_zoom.corps[-1]
    assert demande["start_time"] == f"{FUTUR:%Y-%m-%dT%H:%M:%SZ}"
    assert demande["duration"] == 90
    assert demande["password"] == "datum1"
    assert demande["settings"]["approval_type"] == 0
    assert demande["settings"]["waiting_room"] is False
    assert ("POST", f"/users/{HOTE}/meetings") in faux_zoom.appels

    ligne = (await session.execute(select(Webinar))).scalar_one()
    assert "start_url" not in str(ligne.zoom_snapshot_json)
    assert "motdepasse" not in str(ligne.zoom_snapshot_json)
    assert ligne.meeting_settings_json is not None
    assert ligne.meeting_settings_json["passcode"] is None


async def test_schedule_webinar_without_zoom_right_is_forbidden(
    client: AsyncClient, ouvrir: Any, compte: int, faux_zoom: FauxZoom
) -> None:
    limite = await ouvrir("manage_webinars")
    fiche = await _brouillon(client, limite, **_complet(compte))
    faux_zoom.appels.clear()

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=limite)

    assert reponse.status_code == 403
    assert faux_zoom.appels == []


async def test_schedule_webinar_manual_link_needs_no_zoom_right(
    client: AsyncClient, ouvrir: Any, faux_zoom: FauxZoom
) -> None:
    limite = await ouvrir("manage_webinars")
    fiche = await _brouillon(
        client,
        limite,
        category_codes=["programs_presentation"],
        starts_at=FUTUR.isoformat(),
        link_mode="manual",
        join_url="https://meet.example.com/salle",
    )

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=limite)

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["status_code"] == "scheduled"
    assert faux_zoom.appels == []


async def test_schedule_webinar_incomplete_lists_what_is_missing(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(client, entete)

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)

    assert reponse.status_code == 409
    message = reponse.json()["error"]["message"]
    for attendu in ("catégorie", "date", "compte Zoom"):
        assert attendu in message


async def test_schedule_webinar_twice_creates_one_meeting(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    fiche = await _programmer(client, entete, compte)

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)

    assert reponse.status_code == 409
    assert len(faux_zoom.reunions) == 1


async def test_schedule_webinar_zoom_refusal_keeps_the_draft(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    faux_zoom.refus[("POST", f"/users/{HOTE}/meetings")] = (
        400,
        {"code": 300, "message": "Invalid meeting duration."},
    )
    fiche = await _brouillon(client, entete, **_complet(compte))

    reponse = await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "zoom_rejected"
    relue = await client.get(f"/api/v1/webinars/{fiche['id_webinars']}", headers=entete)
    assert relue.json()["status_code"] == "draft"


async def test_update_webinar_zoom_owned_field_is_refused(
    client: AsyncClient, entete: dict[str, str], compte: int
) -> None:
    fiche = await _programmer(client, entete, compte)
    adresse = f"/api/v1/webinars/{fiche['id_webinars']}"

    refus = await client.patch(adresse, json={"title": "Autre titre"}, headers=entete)
    accepte = await client.patch(
        adresse,
        json={"category_codes": ["programs_presentation"], "title": fiche["title"]},
        headers=entete,
    )

    assert refus.status_code == 409
    assert refus.json()["error"]["code"] == "managed_by_zoom"
    assert accepte.status_code == 200, accepte.text
    assert [c["code"] for c in accepte.json()["categories"]] == ["programs_presentation"]


# --- synchronisation ------------------------------------------------------


async def test_sync_meetings_is_idempotent_and_keeps_full_description(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    reunion = faux_zoom.ajouter_reunion(topic="Comité", agenda="Ordre du jour complet")

    premier = await client.post("/api/v1/webinars/zoom-sync", json={}, headers=entete)
    reunion["agenda"] = "Ordre du jour"  # la liste de Zoom tronque
    second = await client.post("/api/v1/webinars/zoom-sync", json={}, headers=entete)

    assert premier.json()["accounts"][0]["created"] == 1
    assert second.json()["accounts"][0] | {"message": ""} == {
        "id_zoom_accounts": compte,
        "label": "Datum",
        "ok": True,
        "message": "",
        "found": 1,
        "created": 0,
        "updated": 1,
    }
    liste = (await client.get("/api/v1/webinars", headers=entete)).json()
    assert liste["total"] == 1
    fiche = await client.get(f"/api/v1/webinars/{liste['items'][0]['id_webinars']}", headers=entete)
    assert fiche.json()["description"] == "Ordre du jour complet"


async def test_sync_meetings_expired_token_is_renewed_once(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    faux_zoom.refuser_le_prochain_jeton = True

    reponse = await client.post("/api/v1/webinars/zoom-sync", json={}, headers=entete)

    assert reponse.json()["accounts"][0]["ok"] is True
    assert faux_zoom.jetons_delivres == 2


async def test_import_meeting_by_number_reads_its_detail(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    faux_zoom.ajouter_reunion(id=85058225147, topic="Atelier", settings={"approval_type": 0})

    reponse = await client.post(
        "/api/v1/webinars/zoom-meetings",
        json={"id_zoom_accounts": compte, "meeting_id": "850 5822 5147"},
        headers=entete,
    )

    assert reponse.status_code == 200, reponse.text
    fiche = reponse.json()
    assert fiche["title"] == "Atelier"
    assert fiche["zoom_meeting"]["id"] == 85058225147
    assert "start_url" not in fiche["zoom_meeting"]
    assert ("GET", "/meetings/85058225147") in faux_zoom.appels


async def test_import_meeting_unknown_number_is_not_found(
    client: AsyncClient, entete: dict[str, str], compte: int
) -> None:
    reponse = await client.post(
        "/api/v1/webinars/zoom-meetings",
        json={"id_zoom_accounts": compte, "meeting_id": "999999999"},
        headers=entete,
    )

    assert reponse.status_code == 404


async def test_refresh_from_zoom_without_right_is_forbidden(
    client: AsyncClient, entete: dict[str, str], compte: int, ouvrir: Any
) -> None:
    fiche = await _programmer(client, entete, compte)

    reponse = await client.post(
        f"/api/v1/webinars/{fiche['id_webinars']}/refresh-from-zoom", headers=await ouvrir()
    )

    assert reponse.status_code == 403


# --- liste et statistiques ------------------------------------------------


async def test_list_webinars_filters_sorts_and_paginates(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    passe = datetime(2022, 3, 1, 10, tzinfo=UTC)
    await _brouillon(client, entete, title="Brouillon C")
    for titre, quand in (("Atelier A", FUTUR), ("Bilan B", passe)):
        fiche = await _brouillon(
            client,
            entete,
            title=titre,
            category_codes=["ai_and_big_data"],
            starts_at=FUTUR.isoformat(),
            link_mode="manual",
            join_url="https://meet.example.com/x",
        )
        await client.post(f"/api/v1/webinars/{fiche['id_webinars']}/schedule", headers=entete)
        await client.patch(
            f"/api/v1/webinars/{fiche['id_webinars']}",
            json={"starts_at": quand.isoformat()},
            headers=entete,
        )

    async def titres(parametres: str) -> list[str]:
        reponse = await client.get(f"/api/v1/webinars?{parametres}", headers=entete)
        assert reponse.status_code == 200, reponse.text
        return [item["title"] for item in reponse.json()["items"]]

    assert await titres("sort=title&direction=asc") == ["Atelier A", "Bilan B", "Brouillon C"]
    assert await titres("status=past") == ["Bilan B"]
    assert await titres("status=scheduled") == ["Atelier A"]
    assert await titres("status=draft") == ["Brouillon C"]
    assert await titres("sort=title&direction=asc&size=2&page=2") == ["Brouillon C"]
    assert await titres("category=ai_and_big_data&q=bil") == ["Bilan B"]
    assert await titres("q=%25") == []
    assert await titres("type=zoom_meeting") == ["Brouillon C"]
    for tri in ("date", "registrations", "created"):
        assert len(await titres(f"sort={tri}&direction=asc")) == 3

    stats = (await client.get("/api/v1/webinars/stats", headers=entete)).json()
    assert (stats["total"], stats["past"], stats["scheduled"], stats["draft"]) == (3, 1, 1, 1)
    assert stats["next_webinar"]["title"] == "Atelier A"
    assert stats["accounts"][0]["label"] == "Sans compte Zoom"


# --- inscriptions ---------------------------------------------------------


async def test_public_registration_draft_is_not_found(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(client, entete, registration_mode="iagora_form")

    reponse = await client.get(f"/api/v1/public/registration-pages/{fiche['form_slug']}")

    assert reponse.status_code == 404


async def test_public_registration_records_once_and_feeds_newsletter_audience(
    client: AsyncClient,
    entete: dict[str, str],
    compte: int,
    faux_zoom: FauxZoom,
    session: AsyncSession,
) -> None:
    fiche = await _programmer(client, entete, compte, registration_mode="iagora_form")
    adresse = f"/api/v1/public/registration-pages/{fiche['form_slug']}"
    personne = {
        "email": "Aina@Example.com",
        "first_name": "Aina",
        "last_name": "Rakoto",
        "has_newsletter_consent": True,
    }
    sans_accord = {"email": "b@example.com", "first_name": "Bao", "last_name": "Ra"}
    robot = personne | {"email": "robot@example.com", "website": "http://spam.example"}

    page = await client.get(adresse)
    reponses = [
        await client.post(f"{adresse}/registrations", json=corps)
        for corps in (personne, personne, sans_accord, robot)
    ]

    assert page.json()["is_open"] is True
    assert [r.status_code for r in reponses] == [201] * 4
    assert len({r.json()["message"] for r in reponses}) == 1
    assert "zoom.test" not in reponses[0].text
    lignes = (await session.execute(select(WebinarRegistration))).scalars().all()
    assert sorted(ligne.email or "" for ligne in lignes) == ["aina@example.com", "b@example.com"]
    assert len(faux_zoom.inscrits[fiche["external_zoom_meeting_id"]]) == 2

    public = await client.get(
        f"/api/v1/webinars/{fiche['id_webinars']}/newsletter-audience", headers=entete
    )
    assert public.json()["items"] == [{"email": "aina@example.com", "display_name": "Aina"}]
    assert public.json()["excluded_without_consent"] == 1


async def test_public_registration_zoom_refusal_keeps_the_registration(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    fiche = await _programmer(client, entete, compte, registration_mode="iagora_form")
    reunion = fiche["external_zoom_meeting_id"]
    faux_zoom.refus[("POST", f"/meetings/{reunion}/registrants")] = (
        400,
        {"code": 200, "message": "Only available for paid users."},
    )

    reponse = await client.post(
        f"/api/v1/public/registration-pages/{fiche['form_slug']}/registrations",
        json={"email": "c@example.com", "first_name": "Cia", "last_name": "Ra"},
    )

    assert reponse.status_code == 201
    inscrits = await client.get(
        f"/api/v1/webinars/{fiche['id_webinars']}/registrations", headers=entete
    )
    assert "paid users" in inscrits.json()["items"][0]["zoom_error"]


async def test_public_registration_past_webinar_is_closed(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(
        client,
        entete,
        category_codes=["ai_and_big_data"],
        starts_at=FUTUR.isoformat(),
        link_mode="manual",
        join_url="https://meet.example.com/x",
        registration_mode="iagora_form",
    )
    identifiant = fiche["id_webinars"]
    await client.post(f"/api/v1/webinars/{identifiant}/schedule", headers=entete)
    await client.patch(
        f"/api/v1/webinars/{identifiant}",
        json={"starts_at": "2022-01-01T10:00:00Z"},
        headers=entete,
    )

    reponse = await client.post(
        f"/api/v1/public/registration-pages/{fiche['form_slug']}/registrations",
        json={"email": "d@example.com", "first_name": "Dina", "last_name": "Ra"},
    )

    assert reponse.status_code == 409


async def test_sync_registrants_does_not_grant_newsletter_consent(
    client: AsyncClient, entete: dict[str, str], compte: int, faux_zoom: FauxZoom
) -> None:
    fiche = await _programmer(client, entete, compte, registration_mode="zoom_page")
    assert fiche["registration_url"].startswith("https://zoom.test/register/")
    faux_zoom.inscrits[fiche["external_zoom_meeting_id"]] = [
        {"id": "z1", "email": "e@example.com", "first_name": "Eva", "status": "approved"}
    ]

    reponse = await client.post(
        f"/api/v1/webinars/{fiche['id_webinars']}/registrations/zoom-sync", headers=entete
    )

    assert reponse.json() == {"found": 1, "created": 1, "updated": 0}
    inscrits = await client.get(
        f"/api/v1/webinars/{fiche['id_webinars']}/registrations", headers=entete
    )
    assert inscrits.json()["items"][0]["has_newsletter_consent"] is False


async def test_anonymize_registration_erases_personal_data(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(client, entete)
    base = f"/api/v1/webinars/{fiche['id_webinars']}/registrations"
    creee = await client.post(
        base,
        json={"email": "f@example.com", "first_name": "Fara", "last_name": "Ra"},
        headers=entete,
    )

    reponse = await client.delete(
        f"{base}/{creee.json()['id_webinar_registrations']}", headers=entete
    )

    assert reponse.status_code == 204
    ligne = (await client.get(base, headers=entete)).json()["items"][0]
    assert (ligne["email"], ligne["first_name"], ligne["last_name"]) == (None, None, None)


async def test_list_registrations_without_right_is_forbidden(
    client: AsyncClient, entete: dict[str, str], ouvrir: Any
) -> None:
    fiche = await _brouillon(client, entete)

    reponse = await client.get(
        f"/api/v1/webinars/{fiche['id_webinars']}/registrations", headers=await ouvrir()
    )

    assert reponse.status_code == 403


# --- export ---------------------------------------------------------------


async def test_export_registrations_writes_a_safe_csv(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(client, entete)
    base = f"/api/v1/webinars/{fiche['id_webinars']}/registrations"
    for personne in (
        {"email": "a@example.com", "first_name": "Aïna", "last_name": "Rakoto; Ra"},
        {"email": "f@example.com", "first_name": "=2+2", "last_name": "@SUM(A1)"},
        {"email": "e@example.com", "first_name": "Effacé", "last_name": "Parti"},
    ):
        cree = await client.post(
            base, json=personne | {"has_newsletter_consent": True}, headers=entete
        )
    await client.delete(f"{base}/{cree.json()['id_webinar_registrations']}", headers=entete)

    reponse = await client.get(f"{base}/export", headers=entete)

    assert reponse.status_code == 200, reponse.text
    assert reponse.headers["content-type"].startswith("text/csv")
    assert "attachment" in reponse.headers["content-disposition"]
    assert reponse.headers["cache-control"] == "no-store"
    assert reponse.content.startswith(b"\xef\xbb\xbf")
    lignes = list(csv.reader(io.StringIO(reponse.content.decode("utf-8-sig")), delimiter=";"))
    assert lignes[0][:4] == ["Prénom", "Nom de famille", "Adresse e-mail", "Origine"]
    assert [ligne[:4] for ligne in lignes[1:]] == [
        ["Aïna", "Rakoto; Ra", "a@example.com", "Équipe"],
        ["'=2+2", "'@SUM(A1)", "f@example.com", "Équipe"],
    ]
    assert lignes[1][5] == "oui"


async def test_export_registrations_without_right_is_forbidden(
    client: AsyncClient, entete: dict[str, str], ouvrir: Any
) -> None:
    fiche = await _brouillon(client, entete)

    reponse = await client.get(
        f"/api/v1/webinars/{fiche['id_webinars']}/registrations/export", headers=await ouvrir()
    )

    assert reponse.status_code == 403


async def test_export_registrations_unknown_webinar_is_not_found(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    reponse = await client.get("/api/v1/webinars/999999/registrations/export", headers=entete)

    assert reponse.status_code == 404


# --- publications liées ---------------------------------------------------


async def test_publication_links_follow_the_event_lifecycle(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    fiche = await _brouillon(client, entete, starts_at=FUTUR.isoformat())
    base = f"/api/v1/webinars/{fiche['id_webinars']}/publication-links"
    promo = {
        "type_code": "promotion",
        "url": "https://www.linkedin.com/posts/1",
        "platform_code": "linkedin",
    }

    ajoute = await client.post(base, json=promo, headers=entete)
    double = await client.post(base, json=promo, headers=entete)
    trop_tot = await client.post(
        base, json={"type_code": "replay", "url": "https://x.example/2"}, headers=entete
    )
    dangereux = await client.post(
        base, json={"type_code": "other", "url": "javascript:alert(1)"}, headers=entete
    )

    assert ajoute.status_code == 201, ajoute.text
    assert ajoute.json()[0]["platform_label"] == "LinkedIn"
    assert double.status_code == 409
    assert trop_tot.status_code == 409
    assert dangereux.status_code == 422
    retrait = await client.delete(
        f"{base}/{ajoute.json()[0]['id_webinar_publication_links']}", headers=entete
    )
    assert retrait.status_code == 204


# --- visuel ---------------------------------------------------------------


def _image(genre: str = "PNG", couleur: str = "red") -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (4, 4), couleur).save(tampon, genre)
    return tampon.getvalue()


async def _importer_visuel(
    client: AsyncClient, entete: dict[str, str], id_webinars: int, contenu: bytes
) -> Any:
    return await client.put(
        f"/api/v1/webinars/{id_webinars}/flyer",
        files={"file": ("affiche.png", contenu, "image/png")},
        headers=entete,
    )


async def test_upload_flyer_stores_the_image_under_its_real_type(
    client: AsyncClient, entete: dict[str, str], stockage_de_test: StockageLocal, tmp_path: Path
) -> None:
    fiche = await _brouillon(client, entete)
    contenu = _image("JPEG")

    reponse = await _importer_visuel(client, entete, fiche["id_webinars"], contenu)

    assert reponse.status_code == 200, reponse.text
    adresse = reponse.json()["flyer_url"]
    prefixe = f"https://medias.test/webinaires/{fiche['id_webinars']}/visuel-"
    # Le fichier est nommé « .png » par le navigateur, mais c'est un JPEG.
    assert adresse.startswith(prefixe) and adresse.endswith(".jpg")
    cle = adresse.removeprefix("https://medias.test/")
    assert (tmp_path / "medias" / cle).read_bytes() == contenu


@pytest.mark.parametrize("contenu", [b"<svg/>", _image("GIF")], ids=["texte", "gif"])
async def test_upload_flyer_refused_file_keeps_the_previous_one(
    client: AsyncClient, entete: dict[str, str], contenu: bytes
) -> None:
    fiche = await _brouillon(client, entete)
    avant = await _importer_visuel(client, entete, fiche["id_webinars"], _image())

    reponse = await _importer_visuel(client, entete, fiche["id_webinars"], contenu)

    assert reponse.status_code == 415
    assert reponse.json()["error"]["code"] == "invalid_image"
    apres = await client.get(f"/api/v1/webinars/{fiche['id_webinars']}", headers=entete)
    assert apres.json()["flyer_url"] == avant.json()["flyer_url"]


async def test_upload_flyer_too_heavy_is_refused(
    client: AsyncClient, entete: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(flyers, "FLYER_MAX_BYTES", 20)
    fiche = await _brouillon(client, entete)

    reponse = await _importer_visuel(client, entete, fiche["id_webinars"], _image())

    assert reponse.status_code == 413


async def test_upload_flyer_without_right_is_forbidden(
    client: AsyncClient, entete: dict[str, str], ouvrir: Any
) -> None:
    fiche = await _brouillon(client, entete)
    lecteur = await ouvrir()

    reponse = await _importer_visuel(client, lecteur, fiche["id_webinars"], _image())

    assert reponse.status_code == 403


async def test_upload_flyer_unknown_webinar_is_not_found(
    client: AsyncClient, entete: dict[str, str]
) -> None:
    reponse = await _importer_visuel(client, entete, 999999, _image())

    assert reponse.status_code == 404


async def test_remove_flyer_clears_the_visual(client: AsyncClient, entete: dict[str, str]) -> None:
    fiche = await _brouillon(client, entete)
    await _importer_visuel(client, entete, fiche["id_webinars"], _image())

    reponse = await client.delete(f"/api/v1/webinars/{fiche['id_webinars']}/flyer", headers=entete)

    assert reponse.status_code == 204, reponse.text
    apres = await client.get(f"/api/v1/webinars/{fiche['id_webinars']}", headers=entete)
    assert apres.json()["flyer_url"] is None
