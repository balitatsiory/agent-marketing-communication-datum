"""Tests du point de contrôle /health et du format des erreurs."""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import get_settings
from app.core.errors import ConflictError


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app, raise_server_exceptions=False)


def test_health_repond_ok_quand_la_base_repond(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def base_disponible() -> bool:
        return True

    monkeypatch.setattr(main, "check_database", base_disponible)

    reponse = client.get("/health")

    assert reponse.status_code == 200
    # `environment` vaut ce que dit la configuration : « test » ici, « local » dans
    # le conteneur qui lit .env. Le test vérifie le comportement, pas ce réglage.
    assert reponse.json() == {
        "status": "ok",
        "environment": get_settings().ENVIRONMENT,
        "database": "ok",
    }


def test_health_repond_503_quand_la_base_est_injoignable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def base_indisponible() -> bool:
        return False

    monkeypatch.setattr(main, "check_database", base_indisponible)

    reponse = client.get("/health")

    assert reponse.status_code == 503
    assert reponse.json()["database"] == "unreachable"


def test_la_racine_mene_a_la_documentation(client: TestClient) -> None:
    # Sans cette redirection, ouvrir http://localhost:8000 renvoie 404 et laisse
    # croire que l'API n'a pas démarré.
    reponse = client.get("/", follow_redirects=False)

    assert reponse.status_code in (307, 302)
    assert reponse.headers["location"] == "/docs"


def test_une_erreur_metier_est_traduite_au_format_unique(client: TestClient) -> None:
    @main.app.get("/_essai_conflit")
    async def _essai() -> None:
        raise ConflictError("Cette publication est déjà publiée.")

    reponse = client.get("/_essai_conflit")

    assert reponse.status_code == 409
    assert reponse.json() == {
        "error": {"code": "conflict", "message": "Cette publication est déjà publiée."}
    }


def test_une_erreur_inattendue_ne_fuite_pas_la_trace(client: TestClient) -> None:
    @main.app.get("/_essai_bug")
    async def _essai() -> None:
        raise RuntimeError("mot de passe = secret")

    reponse = client.get("/_essai_bug")

    assert reponse.status_code == 500
    assert reponse.json()["error"]["code"] == "internal_error"
    assert "secret" not in reponse.text
