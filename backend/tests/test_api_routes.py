"""Vérifie que l'API expose les bons chemins et qu'ils sont protégés.

Aucune base n'est nécessaire : les refus d'authentification interviennent avant
toute requête SQL.
"""

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app, raise_server_exceptions=False)


def test_les_chemins_attendus_existent() -> None:
    # On lit le schéma OpenAPI plutôt que app.routes : sa forme ne dépend pas de la
    # version de FastAPI, et c'est aussi ce que voit le front.
    chemins = set(main.app.openapi()["paths"])

    assert {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/users",
        "/api/v1/users/{id_users}",
        "/api/v1/permissions",
    } <= chemins


@pytest.mark.parametrize(
    ("methode", "chemin"),
    [
        ("get", "/api/v1/auth/me"),
        ("get", "/api/v1/users"),
        ("post", "/api/v1/users"),
        ("get", "/api/v1/permissions"),
    ],
)
def test_sans_jeton_l_api_repond_401(client: TestClient, methode: str, chemin: str) -> None:
    reponse = getattr(client, methode)(chemin)

    assert reponse.status_code == 401
    assert reponse.json()["error"]["code"] == "not_authenticated"


def test_un_jeton_de_pacotille_est_refuse(client: TestClient) -> None:
    reponse = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nimporte-quoi"})

    assert reponse.status_code == 401


def test_la_connexion_valide_le_format_avant_de_toucher_la_base(client: TestClient) -> None:
    # Email invalide : Pydantic refuse, aucune requête SQL n'est tentée.
    reponse = client.post("/api/v1/auth/login", json={"email": "pas-un-email", "password": "x"})

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "validation_error"


def test_un_champ_inattendu_est_refuse(client: TestClient) -> None:
    reponse = client.post(
        "/api/v1/auth/login",
        json={"email": "marie@datum.mg", "password": "secret", "is_admin": True},
    )

    assert reponse.status_code == 422
