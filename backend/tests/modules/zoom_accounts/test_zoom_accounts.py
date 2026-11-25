"""Comptes Zoom : raccordement, test de connexion, renouvellement du jeton, droits."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.zoom_accounts.models import ZoomAccount, ZoomAccountCredential
from tests.faux_zoom import CLIENT_ID, CLIENT_SECRET, HOTE, FauxZoom

COMPTE = {
    "label": "Datum principal",
    "host_email": HOTE,
    "external_zoom_account_id": "compte-essai",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
}


@pytest.fixture
def gestionnaire(fabrique_utilisateur, connexion):  # type: ignore[no-untyped-def]
    async def entete_de(*droits: str) -> dict[str, str]:
        utilisateur = await fabrique_utilisateur(droits=list(droits))
        jetons = await connexion(utilisateur.email)
        return {"Authorization": f"Bearer {jetons['access_token']}"}

    return entete_de


async def _creer(client: AsyncClient, entete: dict[str, str], **champs: Any) -> dict[str, Any]:
    reponse = await client.post("/api/v1/zoom-accounts", json=COMPTE | champs, headers=entete)
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


async def test_create_account_valid_credentials_verifies_without_leaking_secrets(
    client: AsyncClient, session: AsyncSession, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_zoom_accounts")

    resultat = await _creer(client, entete)

    assert resultat["verified"] is True
    assert HOTE in resultat["message"]
    compte = resultat["account"]
    assert compte["has_valid_token"] is True
    assert all(droit["is_granted"] for droit in compte["scopes"])
    reponse_brute = str(resultat)
    assert CLIENT_SECRET not in reponse_brute
    assert "jeton-1" not in reponse_brute

    secret = (await session.execute(select(ZoomAccountCredential))).scalar_one()
    assert secret.client_secret_encrypted != CLIENT_SECRET
    ligne = (await session.execute(select(ZoomAccount))).scalar_one()
    assert ligne.access_token_encrypted not in (None, "jeton-1")


async def test_create_account_wrong_secret_reports_failure_and_keeps_history(
    client: AsyncClient, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_zoom_accounts")

    resultat = await _creer(client, entete, client_secret="mauvais-secret")

    assert resultat["verified"] is False
    assert "Invalid client_id or client_secret" in resultat["message"]
    identifiant = resultat["account"]["id_zoom_accounts"]
    historique = await client.get(f"/api/v1/zoom-accounts/{identifiant}/checks", headers=entete)
    resume = [(ligne["kind"], ligne["is_ok"]) for ligne in historique.json()]
    assert resume == [("connection", False)]


async def test_verify_account_missing_scope_names_it(
    client: AsyncClient, faux_zoom: FauxZoom, gestionnaire: Any
) -> None:
    faux_zoom.scopes = "meeting:read:list_meetings:admin"
    entete = await gestionnaire("manage_zoom_accounts")

    resultat = await _creer(client, entete)

    assert resultat["verified"] is True
    assert "meeting:write:meeting:admin" in resultat["message"]


async def test_verify_account_unknown_host_fails(client: AsyncClient, gestionnaire: Any) -> None:
    entete = await gestionnaire("manage_zoom_accounts")

    resultat = await _creer(client, entete, host_email="inconnu@iagora.example.com")

    assert resultat["verified"] is False
    assert "User does not exist" in resultat["message"]


async def test_refresh_token_requests_a_new_token(
    client: AsyncClient, faux_zoom: FauxZoom, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_zoom_accounts")
    compte = await _creer(client, entete)
    identifiant = compte["account"]["id_zoom_accounts"]

    reponse = await client.post(
        f"/api/v1/zoom-accounts/{identifiant}/refresh-token", headers=entete
    )

    assert reponse.status_code == 200
    assert reponse.json()["verified"] is True
    assert faux_zoom.jetons_delivres == 2


async def test_replace_client_secret_keeps_previous_row(
    client: AsyncClient, session: AsyncSession, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_zoom_accounts")
    compte = await _creer(client, entete, client_secret="mauvais-secret")
    identifiant = compte["account"]["id_zoom_accounts"]

    reponse = await client.post(
        f"/api/v1/zoom-accounts/{identifiant}/client-secret",
        json={"client_secret": CLIENT_SECRET},
        headers=entete,
    )

    assert reponse.json()["verified"] is True
    lignes = (await session.execute(select(ZoomAccountCredential))).scalars().all()
    assert sorted(ligne.superseded_at is not None for ligne in lignes) == [False, True]


async def test_create_account_without_right_is_forbidden(
    client: AsyncClient, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_webinars")

    reponse = await client.post("/api/v1/zoom-accounts", json=COMPTE, headers=entete)

    assert reponse.status_code == 403


async def test_create_account_twice_is_a_conflict(client: AsyncClient, gestionnaire: Any) -> None:
    entete = await gestionnaire("manage_zoom_accounts")
    await _creer(client, entete)

    reponse = await client.post("/api/v1/zoom-accounts", json=COMPTE, headers=entete)

    assert reponse.status_code == 409


async def test_archive_account_removes_it_and_revokes_the_secret(
    client: AsyncClient, session: AsyncSession, gestionnaire: Any
) -> None:
    entete = await gestionnaire("manage_zoom_accounts")
    compte = await _creer(client, entete)
    identifiant = compte["account"]["id_zoom_accounts"]

    reponse = await client.delete(f"/api/v1/zoom-accounts/{identifiant}", headers=entete)

    assert reponse.status_code == 204
    assert (await client.get("/api/v1/zoom-accounts", headers=entete)).json() == []
    secret = (await session.execute(select(ZoomAccountCredential))).scalar_one()
    assert secret.revoked_at is not None


async def test_check_history_cannot_be_rewritten(
    client: AsyncClient, session: AsyncSession, gestionnaire: Any
) -> None:
    await _creer(client, await gestionnaire("manage_zoom_accounts"))

    with pytest.raises(DBAPIError, match="ajout seul"):
        await session.execute(text("UPDATE zoom_account_checks SET is_ok = false"))
