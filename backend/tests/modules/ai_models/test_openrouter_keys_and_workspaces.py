"""Tests du module Modèles IA (OpenRouter) : clés chiffrées, workspaces et modèles."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_token
from app.modules.ai_models.constants import MANAGE_AI_MODELS
from app.modules.ai_models.models import OpenRouterApiKey
from app.modules.ai_models.openrouter_client import VerifyKeyResult
from tests.conftest import entete

pytestmark = pytest.mark.asyncio


async def test_enregistrer_cles_chiffrees_en_base_et_rotation(
    client: AsyncClient,
    session: AsyncSession,
    fabrique_utilisateur,
    connexion,
) -> None:
    """Les clés Management et Standard sont chiffrées par Fernet en base et jamais renvoyées en clair."""
    admin = await fabrique_utilisateur(droits=[MANAGE_AI_MODELS])
    jetons = await connexion(admin.email)

    cle_mgmt_1 = "sk-or-v1-management-secret-key-111111"
    cle_mgmt_2 = "sk-or-v1-management-secret-key-222222"
    cle_std = "sk-or-v1-standard-secret-key-999999"

    with (
        patch(
            "app.modules.ai_models.openrouter_client.verify_management_key",
            new=AsyncMock(
                return_value=VerifyKeyResult(
                    ok=True,
                    message="Management API Key valide.",
                    total_credits=25.0,
                    total_usage=3.5,
                    remaining_credits=21.5,
                )
            ),
        ),
        patch(
            "app.modules.ai_models.openrouter_client.verify_standard_key",
            new=AsyncMock(
                return_value=VerifyKeyResult(
                    ok=True,
                    message="Clé API Standard valide.",
                    key_label="IAGORA Std",
                    limit_remaining=10.0,
                    is_free_tier=False,
                )
            ),
        ),
    ):
        # 1. Enregistrement de la 1ère Management API Key
        r1 = await client.post(
            "/api/v1/openrouter/keys",
            headers=entete(jetons),
            json={
                "key_kind": "management",
                "api_key": cle_mgmt_1,
                "label": "Mgmt v1",
                "verify_immediately": True,
            },
        )
        assert r1.status_code == 201, r1.text
        corps1 = r1.json()
        assert corps1["verified"] is True
        assert corps1["remaining_credits"] == 21.5
        assert cle_mgmt_1 not in r1.text
        assert corps1["key"]["is_active"] is True
        assert corps1["key"]["key_masked"].endswith("1111")

        # Vérification directe en base : stockée chiffrée (Fernet), jamais en clair
        lignes_db = (
            await session.execute(
                select(OpenRouterApiKey).where(OpenRouterApiKey.key_kind == "management")
            )
        ).scalars().all()
        assert len(lignes_db) == 1
        assert lignes_db[0].api_key_encrypted != cle_mgmt_1
        assert decrypt_token(lignes_db[0].api_key_encrypted) == cle_mgmt_1

        # 2. Rotation de la Management API Key -> remplace l'ancienne
        r2 = await client.post(
            "/api/v1/openrouter/keys",
            headers=entete(jetons),
            json={
                "key_kind": "management",
                "api_key": cle_mgmt_2,
                "label": "Mgmt v2",
                "verify_immediately": True,
            },
        )
        assert r2.status_code == 201, r2.text
        assert cle_mgmt_2 not in r2.text

        # 3. Enregistrement de la Standard API Key
        r3 = await client.post(
            "/api/v1/openrouter/keys",
            headers=entete(jetons),
            json={
                "key_kind": "standard",
                "api_key": cle_std,
                "label": "Std Prod",
                "verify_immediately": True,
            },
        )
        assert r3.status_code == 201, r3.text
        assert cle_std not in r3.text

        # 4. Liste des clés : 3 lignes dont 2 actives (1 management + 1 standard) et 1 remplacée
        r_list = await client.get("/api/v1/openrouter/keys", headers=entete(jetons))
        assert r_list.status_code == 200
        cles = r_list.json()
        assert len(cles) == 3
        actives = [c for c in cles if c["is_active"]]
        assert len(actives) == 2
        assert {c["key_kind"] for c in actives} == {"management", "standard"}


async def test_droits_requis_pour_gestion_cles(
    client: AsyncClient,
    fabrique_utilisateur,
    connexion,
) -> None:
    """Un utilisateur sans `manage_ai_models` reçoit 403 en écriture."""
    simple = await fabrique_utilisateur(droits=[])
    jetons = await connexion(simple.email)

    r = await client.post(
        "/api/v1/openrouter/keys",
        headers=entete(jetons),
        json={"key_kind": "standard", "api_key": "sk-or-v1-forbidden-test-key"},
    )
    assert r.status_code == 403


async def test_workspaces_et_modeles_openrouter(
    client: AsyncClient,
    fabrique_utilisateur,
    connexion,
) -> None:
    """Synchronisation, création et sélection de workspaces + synchro et affectation de modèles."""
    admin = await fabrique_utilisateur(droits=[MANAGE_AI_MODELS])
    jetons = await connexion(admin.email)

    # Enregistrer les deux clés sans appel réseau
    await client.post(
        "/api/v1/openrouter/keys",
        headers=entete(jetons),
        json={
            "key_kind": "management",
            "api_key": "sk-or-v1-mgmt-key-for-workspaces",
            "verify_immediately": False,
        },
    )
    await client.post(
        "/api/v1/openrouter/keys",
        headers=entete(jetons),
        json={
            "key_kind": "standard",
            "api_key": "sk-or-v1-std-key-for-models",
            "verify_immediately": False,
        },
    )

    with (
        patch(
            "app.modules.ai_models.openrouter_client.list_workspaces",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "ws_default_1",
                        "name": "Default Workspace",
                        "slug": "default",
                        "description": "Workspace principal",
                        "is_default": True,
                    }
                ]
            ),
        ),
        patch(
            "app.modules.ai_models.openrouter_client.create_workspace",
            new=AsyncMock(
                return_value={
                    "id": "ws_iagora_prod",
                    "name": "IAGORA Production",
                    "slug": "iagora-production",
                    "description": "Production DATUM",
                    "default_text_model": "anthropic/claude-3.5-sonnet",
                    "default_provider_sort": "latency",
                }
            ),
        ),
        patch(
            "app.modules.ai_models.openrouter_client.list_models",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "anthropic/claude-3.5-sonnet",
                        "name": "Claude 3.5 Sonnet",
                        "description": "Modèle rédactionnel",
                        "context_length": 200000,
                        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["text"],
                        },
                    }
                ]
            ),
        ),
    ):
        # Sync workspaces
        r_sync_ws = await client.post("/api/v1/openrouter/workspaces/sync", headers=entete(jetons))
        assert r_sync_ws.status_code == 200, r_sync_ws.text
        assert r_sync_ws.json()["synced_count"] == 1

        # Créer workspace
        r_create_ws = await client.post(
            "/api/v1/openrouter/workspaces",
            headers=entete(jetons),
            json={
                "name": "IAGORA Production",
                "description": "Production DATUM",
                "default_text_model": "anthropic/claude-3.5-sonnet",
                "default_provider_sort": "latency",
                "monthly_budget_usd": 120,
            },
        )
        assert r_create_ws.status_code == 201, r_create_ws.text
        ws_id = r_create_ws.json()["id_ai_workspaces"]

        # Définir comme workspace actif IAGORA
        r_sel = await client.patch(
            f"/api/v1/openrouter/workspaces/{ws_id}",
            headers=entete(jetons),
            json={"is_selected": True},
        )
        assert r_sel.status_code == 200
        assert r_sel.json()["is_selected"] is True

        # Synchroniser le catalogue de modèles
        r_sync_m = await client.post("/api/v1/openrouter/models/sync", headers=entete(jetons))
        assert r_sync_m.status_code == 200, r_sync_m.text
        assert r_sync_m.json()["synced_count"] == 1

        # Activer et affecter le modèle
        r_models = await client.get("/api/v1/openrouter/models", headers=entete(jetons))
        model_id = r_models.json()[0]["id_ai_models"]

        r_toggle = await client.patch(
            f"/api/v1/openrouter/models/{model_id}",
            headers=entete(jetons),
            json={"is_enabled": True},
        )
        assert r_toggle.status_code == 200
        assert r_toggle.json()["is_enabled"] is True

        r_assign = await client.put(
            "/api/v1/openrouter/assignments/text-generation",
            headers=entete(jetons),
            json={
                "id_ai_models": model_id,
                "id_ai_workspaces": ws_id,
                "reasoning_effort": "high",
            },
        )
        assert r_assign.status_code == 200, r_assign.text
        assert r_assign.json()["openrouter_model_id"] == "anthropic/claude-3.5-sonnet"
        assert r_assign.json()["workspace_name"] == "IAGORA Production"
        assert r_assign.json()["reasoning_effort"] == "high"


async def test_tableau_de_bord_finops_openrouter(
    client: AsyncClient,
    fabrique_utilisateur,
    connexion,
) -> None:
    """Agrégation du tableau de bord FinOps (/credits, /activity, /keys)."""
    admin = await fabrique_utilisateur(droits=[MANAGE_AI_MODELS])
    jetons = await connexion(admin.email)

    await client.post(
        "/api/v1/openrouter/keys",
        headers=entete(jetons),
        json={
            "key_kind": "management",
            "api_key": "sk-or-v1-mgmt-key-dashboard-test",
            "verify_immediately": False,
        },
    )

    with (
        patch(
            "app.modules.ai_models.openrouter_client.get_credits",
            new=AsyncMock(
                return_value={
                    "total_credits": 50.0,
                    "total_usage": 12.5,
                    "remaining_credits": 37.5,
                }
            ),
        ),
        patch(
            "app.modules.ai_models.openrouter_client.get_activity",
            new=AsyncMock(
                return_value=[
                    {
                        "date": "2026-11-24",
                        "model": "google/gemini-2.5-flash",
                        "provider_name": "google-vertex",
                        "usage": 0.13372,
                        "requests": 11,
                        "prompt_tokens": 17957,
                        "completion_tokens": 14238,
                        "reasoning_tokens": 12798,
                    },
                    {
                        "date": "2026-11-25",
                        "model": "anthropic/claude-3.5-sonnet",
                        "provider_name": "anthropic",
                        "usage": 0.25,
                        "requests": 5,
                        "prompt_tokens": 4000,
                        "completion_tokens": 1000,
                        "reasoning_tokens": 200,
                    },
                ]
            ),
        ),
        patch(
            "app.modules.ai_models.openrouter_client.list_remote_keys",
            new=AsyncMock(
                return_value=[
                    {
                        "hash": "hash_key_1",
                        "name": "iagora-prod",
                        "limit": 20.0,
                        "limit_remaining": 15.0,
                        "usage": 5.0,
                        "disabled": False,
                    }
                ]
            ),
        ),
    ):
        r = await client.get("/api/v1/openrouter/dashboard", headers=entete(jetons))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["scope_workspace_id"] is None
        assert "cumulé" in data["scope_label"]
        assert data["credits"]["remaining_credits"] == 37.5
        assert data["total_requests"] == 16
        assert data["total_prompt_tokens"] == 21957
        assert data["total_reasoning_tokens"] == 12998
        assert data["active_remote_keys_count"] == 1
        assert len(data["daily_series"]) == 2
        assert len(data["by_model"]) == 2
        assert data["by_model"][0]["model"] == "anthropic/claude-3.5-sonnet"

        # Vérification avec filtre workspace_id explicite
        r_ws = await client.get(
            "/api/v1/openrouter/dashboard?workspace_id=ws_test_123",
            headers=entete(jetons),
        )
        assert r_ws.status_code == 200, r_ws.text
        assert r_ws.json()["scope_workspace_id"] == "ws_test_123"


async def test_bac_a_sable_ia_comparaison_parallele(
    client: AsyncClient,
    fabrique_utilisateur,
    connexion,
) -> None:
    """Le Bac à sable exécute les variantes en parallèle avec la clé Sandbox chiffrée."""
    admin = await fabrique_utilisateur(droits=[MANAGE_AI_MODELS])
    jetons = await connexion(admin.email)

    # Enregistrer une clé Sandbox isolée (chiffrée Fernet)
    r_key = await client.post(
        "/api/v1/openrouter/keys",
        headers=entete(jetons),
        json={
            "key_kind": "sandbox",
            "api_key": "sk-or-v1-sandbox-isolated-key-7777",
            "label": "Sandbox DATUM",
            "verify_immediately": False,
        },
    )
    assert r_key.status_code == 201, r_key.text

    async def _fake_completion(*args, **kwargs):
        effort = kwargs.get("reasoning_effort")
        reason_tok = 1500 if effort == "high" else 40
        cost = 0.0145 if effort == "high" else 0.0018
        return {
            "id": f"gen-sbx-{effort}",
            "model": kwargs["model"],
            "provider": "google-vertex",
            "choices": [
                {
                    "message": {
                        "content": f"Post généré (effort={effort})",
                        "reasoning": "Analyse de la cible et structuration AIDA.",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 310,
                "completion_tokens": 180 + reason_tok,
                "total_tokens": 490 + reason_tok,
                "prompt_tokens_details": {"cached_tokens": 50},
                "completion_tokens_details": {"reasoning_tokens": reason_tok},
                "cost": cost,
            },
        }

    with patch(
        "app.modules.ai_models.openrouter_client.run_chat_completion",
        new=AsyncMock(side_effect=_fake_completion),
    ):
        r = await client.post(
            "/api/v1/openrouter/sandbox/compare",
            headers=entete(jetons),
            json={
                "use_case": "publication_text",
                "system_prompt": "Tu es le responsable éditorial de Datum Academy.",
                "user_prompt": "Rédige un post LinkedIn de lancement.",
                "tone": "Professionnel et concret",
                "json_output_enabled": False,
                "variants": [
                    {
                        "slot_id": "A",
                        "model_id": "google/gemini-2.5-flash",
                        "reasoning_effort": "low",
                        "temperature": 0.4,
                    },
                    {
                        "slot_id": "B",
                        "model_id": "google/gemini-2.5-flash",
                        "reasoning_effort": "high",
                        "temperature": 0.4,
                    },
                ],
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["key_source"] == "sandbox"
        assert len(data["results"]) == 2
        res_a, res_b = data["results"]
        assert res_a["ok"] is True
        assert res_a["cost_usd"] == 0.0018
        assert res_b["reasoning_tokens"] == 1500
        assert data["total_batch_cost_usd"] == round(0.0018 + 0.0145, 7)
