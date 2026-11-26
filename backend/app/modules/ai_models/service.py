"""Règles métier du module Modèles IA (OpenRouter).

Points clés de sécurité :
- Les clés Management et Standard sont chiffrées via `encrypt_token` (Fernet)
  avant toute écriture en base, exactement comme `social_account_tokens`.
- Le déchiffrement (`decrypt_token`) n'a lieu qu'en mémoire, au moment exact
  d'un appel sortant vers OpenRouter.
- Aucune réponse API ne renvoie jamais une clé en clair : seul `key_masked`
  (ex: `sk-or-v1-••••abcd`) est exposé.
"""

import asyncio
import base64
from datetime import UTC, datetime
from decimal import Decimal
import io
import json
import logging
import re
import time
from typing import Any
import uuid

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.security import decrypt_token, encrypt_token
from app.core.storage import Stockage
from app.modules.ai_models import openrouter_client
from app.modules.ai_models.constants import (
    KEY_KIND_MANAGEMENT,
    KEY_KIND_SANDBOX,
    KEY_KIND_STANDARD,
    PROMPT_KIND_SYSTEM,
    PROMPT_KIND_TEMPLATE,
    PROMPT_TASKS_META,
    TASK_CODES,
    TASK_IMAGE_GENERATION,
    TASK_LABELS,
    TASK_TEXT_GENERATION,
)
from app.modules.ai_models.models import (
    AiModel,
    AiPrompt,
    AiSandboxRun,
    AiTaskAssignment,
    AiWorkspace,
    OpenRouterApiKey,
)
from app.modules.ai_models.schemas import (
    AiModelRead,
    AiModelsSyncRead,
    AiPromptCreate,
    AiPromptRead,
    AiPromptTaskRead,
    AiPromptUpdate,
    AiTaskAssignmentRead,
    AiTaskAssignmentUpdate,
    AiWorkspaceCreate,
    AiWorkspaceRead,
    AiWorkspaceSyncRead,
    AiWorkspaceUpdate,
    OpenRouterActivityItemRead,
    OpenRouterCreditsRead,
    OpenRouterDailyPointRead,
    OpenRouterDashboardRead,
    OpenRouterKeyRead,
    OpenRouterKeySave,
    OpenRouterKeyVerifyRead,
    OpenRouterModelCostRead,
    OpenRouterOverviewRead,
    OpenRouterRemoteKeyRead,
    OpenRouterWorkspaceCostRead,
    SandboxCompareRequest,
    SandboxCompareResponse,
    SandboxRunHistoryRead,
    SandboxVariantInput,
    SandboxVariantResult,
    ActivePromptSummaryRead,
    ActiveTaskModelSummaryRead,
    PublicationGenerationContextRead,
    PublicationTextGenerationRequest,
    PublicationTextGenerationResponse,
    PublicationTextProposalRead,
    PublicationVisualGenerationRequest,
    PublicationVisualGenerationResponse,
)
from app.modules.media.models import Media, MediaReference, MediaReferenceNature
from app.modules.users.models import User


def mask_api_key(clair: str) -> str:
    """Produit un aperçu masqué sans jamais révéler le secret."""
    nettoye = clair.strip()
    if len(nettoye) <= 12:
        return "••••••••" + nettoye[-2:] if len(nettoye) >= 4 else "••••••••"
    prefixe = nettoye[:10] if nettoye.startswith("sk-or-") else nettoye[:6]
    suffixe = nettoye[-4:]
    return f"{prefixe}••••{suffixe}"


def _nom_utilisateur(utilisateur: User | None) -> str | None:
    if utilisateur is None:
        return None
    return f"{utilisateur.first_name} {utilisateur.last_name}".strip() or utilisateur.email


def _key_to_read(cle: OpenRouterApiKey, auteur: User | None = None) -> OpenRouterKeyRead:
    return OpenRouterKeyRead(
        id_openrouter_api_keys=cle.id_openrouter_api_keys,
        key_kind=cle.key_kind,  # type: ignore[arg-type]
        label=cle.label,
        key_masked=cle.key_masked,
        is_active=cle.superseded_at is None and cle.revoked_at is None,
        last_verified_at=cle.last_verified_at,
        last_verify_ok=cle.last_verify_ok,
        last_verify_message=cle.last_verify_message,
        obtained_at=cle.obtained_at,
        superseded_at=cle.superseded_at,
        revoked_at=cle.revoked_at,
        created_by_name=_nom_utilisateur(auteur),
        created_at=cle.created_at,
    )


def _workspace_to_read(ws: AiWorkspace) -> AiWorkspaceRead:
    return AiWorkspaceRead(
        id_ai_workspaces=ws.id_ai_workspaces,
        openrouter_workspace_id=ws.openrouter_workspace_id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        default_text_model=ws.default_text_model,
        default_image_model=ws.default_image_model,
        default_provider_sort=ws.default_provider_sort,
        monthly_budget_usd=(
            float(ws.monthly_budget_usd) if ws.monthly_budget_usd is not None else None
        ),
        is_default=ws.is_default,
        is_selected=ws.is_selected,
        last_synced_at=ws.last_synced_at,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


def _model_to_read(m: AiModel) -> AiModelRead:
    return AiModelRead(
        id_ai_models=m.id_ai_models,
        openrouter_model_id=m.openrouter_model_id,
        name=m.name,
        provider_slug=m.provider_slug,
        description=m.description,
        context_length=m.context_length,
        pricing_prompt=m.pricing_prompt,
        pricing_completion=m.pricing_completion,
        input_modalities=list(m.input_modalities_json or []),
        output_modalities=list(m.output_modalities_json or []),
        is_enabled=m.is_enabled,
        last_synced_at=m.last_synced_at,
    )


async def _get_active_key_row(
    session: AsyncSession, key_kind: str
) -> OpenRouterApiKey | None:
    return (
        await session.execute(
            select(OpenRouterApiKey).where(
                OpenRouterApiKey.key_kind == key_kind,
                OpenRouterApiKey.superseded_at.is_(None),
                OpenRouterApiKey.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _require_decrypted_key(session: AsyncSession, key_kind: str) -> str:
    row = await _get_active_key_row(session, key_kind)
    if row is None:
        libelle = "Management API Key" if key_kind == KEY_KIND_MANAGEMENT else "API Standard Key"
        raise ApiError(
            "openrouter_key_missing",
            f"Aucune {libelle} OpenRouter active n'est configurée. "
            "Enregistrez-la d'abord dans l'onglet Clés OpenRouter.",
            400,
        )
    return decrypt_token(row.api_key_encrypted)


# ---------------------------------------------------------------------------
# Gestion des clés API chiffrées
# ---------------------------------------------------------------------------


async def lister_cles(session: AsyncSession) -> list[OpenRouterKeyRead]:
    """Renvoie toutes les clés OpenRouter (actives puis historique), masquées."""
    lignes = (
        await session.execute(
            select(OpenRouterApiKey, User)
            .outerjoin(User, User.id_users == OpenRouterApiKey.id_users_created_by)
            .order_by(OpenRouterApiKey.created_at.desc(), OpenRouterApiKey.id_openrouter_api_keys.desc())
        )
    ).all()
    return [_key_to_read(cle, auteur) for cle, auteur in lignes]


async def enregistrer_cle(
    session: AsyncSession,
    donnees: OpenRouterKeySave,
    par: User,
) -> OpenRouterKeyVerifyRead:
    """Chiffre et enregistre une clé OpenRouter, en remplaçant la précédente active."""
    clair = donnees.api_key.strip()
    if len(clair) < 8:
        raise ApiError("invalid_api_key", "La clé API saisie est trop courte.", 422)

    maintenant = datetime.now(UTC)

    # Marquer l'éventuelle clé active précédente du même type comme remplacée
    await session.execute(
        update(OpenRouterApiKey)
        .where(
            OpenRouterApiKey.key_kind == donnees.key_kind,
            OpenRouterApiKey.superseded_at.is_(None),
            OpenRouterApiKey.revoked_at.is_(None),
        )
        .values(superseded_at=maintenant)
    )
    await session.flush()

    nouvelle = OpenRouterApiKey(
        key_kind=donnees.key_kind,
        label=(donnees.label or "").strip() or None,
        api_key_encrypted=encrypt_token(clair),
        key_masked=mask_api_key(clair),
        obtained_at=maintenant,
        id_users_created_by=par.id_users,
    )
    session.add(nouvelle)
    await session.flush()

    res_verif: openrouter_client.VerifyKeyResult | None = None
    if donnees.verify_immediately:
        if donnees.key_kind == KEY_KIND_MANAGEMENT:
            res_verif = await openrouter_client.verify_management_key(clair)
        else:
            res_verif = await openrouter_client.verify_standard_key(clair)
        nouvelle.last_verified_at = datetime.now(UTC)
        nouvelle.last_verify_ok = res_verif.ok
        nouvelle.last_verify_message = res_verif.message

    await session.commit()
    await session.refresh(nouvelle)

    return OpenRouterKeyVerifyRead(
        verified=res_verif.ok if res_verif is not None else False,
        message=(
            res_verif.message
            if res_verif is not None
            else "Clé chiffrée et enregistrée en base de données."
        ),
        key=_key_to_read(nouvelle, par),
        total_credits=res_verif.total_credits if res_verif else None,
        total_usage=res_verif.total_usage if res_verif else None,
        remaining_credits=res_verif.remaining_credits if res_verif else None,
        key_label=res_verif.key_label if res_verif else None,
        limit_remaining=res_verif.limit_remaining if res_verif else None,
        is_free_tier=res_verif.is_free_tier if res_verif else None,
    )


async def verifier_cle(
    session: AsyncSession, id_key: int
) -> OpenRouterKeyVerifyRead:
    """Déchiffre la clé en mémoire et teste sa validité auprès d'OpenRouter."""
    ligne = (
        await session.execute(
            select(OpenRouterApiKey, User)
            .outerjoin(User, User.id_users == OpenRouterApiKey.id_users_created_by)
            .where(OpenRouterApiKey.id_openrouter_api_keys == id_key)
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Clé OpenRouter introuvable.")
    cle, auteur = ligne

    if cle.revoked_at is not None or cle.superseded_at is not None:
        raise ApiError("key_not_active", "Impossible de vérifier une clé remplacée ou révoquée.", 400)

    clair = decrypt_token(cle.api_key_encrypted)
    if cle.key_kind == KEY_KIND_MANAGEMENT:
        res = await openrouter_client.verify_management_key(clair)
    else:
        res = await openrouter_client.verify_standard_key(clair)

    cle.last_verified_at = datetime.now(UTC)
    cle.last_verify_ok = res.ok
    cle.last_verify_message = res.message
    await session.commit()
    await session.refresh(cle)

    return OpenRouterKeyVerifyRead(
        verified=res.ok,
        message=res.message,
        key=_key_to_read(cle, auteur),
        total_credits=res.total_credits,
        total_usage=res.total_usage,
        remaining_credits=res.remaining_credits,
        key_label=res.key_label,
        limit_remaining=res.limit_remaining,
        is_free_tier=res.is_free_tier,
    )


async def revoquer_cle(session: AsyncSession, id_key: int) -> OpenRouterKeyRead:
    """Révoque une clé active."""
    ligne = (
        await session.execute(
            select(OpenRouterApiKey, User)
            .outerjoin(User, User.id_users == OpenRouterApiKey.id_users_created_by)
            .where(OpenRouterApiKey.id_openrouter_api_keys == id_key)
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Clé OpenRouter introuvable.")
    cle, auteur = ligne

    if cle.revoked_at is None:
        cle.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(cle)

    return _key_to_read(cle, auteur)


# ---------------------------------------------------------------------------
# Synthèse globale
# ---------------------------------------------------------------------------


async def obtenir_synthese(session: AsyncSession) -> OpenRouterOverviewRead:
    """Renvoie l'état global des clés, crédits, workspaces et modèles."""
    mgmt = await _get_active_key_row(session, KEY_KIND_MANAGEMENT)
    std = await _get_active_key_row(session, KEY_KIND_STANDARD)

    credits = OpenRouterCreditsRead(available=False)
    if mgmt is not None:
        try:
            solde = await openrouter_client.get_credits(decrypt_token(mgmt.api_key_encrypted))
            credits = OpenRouterCreditsRead(
                available=True,
                total_credits=solde["total_credits"],
                total_usage=solde["total_usage"],
                remaining_credits=solde["remaining_credits"],
            )
        except ApiError as err:
            credits = OpenRouterCreditsRead(available=False, error=err.message)

    ws_count = int(
        (
            await session.execute(
                select(func.count(AiWorkspace.id_ai_workspaces)).where(
                    AiWorkspace.deleted_at.is_(None)
                )
            )
        ).scalar_one()
    )
    selected_ws_name = (
        await session.execute(
            select(AiWorkspace.name)
            .where(AiWorkspace.deleted_at.is_(None), AiWorkspace.is_selected.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()

    models_total = int(
        (await session.execute(select(func.count(AiModel.id_ai_models)))).scalar_one()
    )
    models_enabled = int(
        (
            await session.execute(
                select(func.count(AiModel.id_ai_models)).where(AiModel.is_enabled.is_(True))
            )
        ).scalar_one()
    )

    return OpenRouterOverviewRead(
        management_key=_key_to_read(mgmt) if mgmt else None,
        standard_key=_key_to_read(std) if std else None,
        credits=credits,
        workspaces_count=ws_count,
        selected_workspace_name=selected_ws_name,
        models_total_count=models_total,
        models_enabled_count=models_enabled,
    )


# ---------------------------------------------------------------------------
# Tableau de bord FinOps & Observabilité OpenRouter
# ---------------------------------------------------------------------------


def _to_float(val: Any) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(val: Any) -> int:
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


async def obtenir_tableau_de_bord(
    session: AsyncSession, workspace_id: str | None = None
) -> OpenRouterDashboardRead:
    """Agrège en direct les données FinOps OpenRouter (/credits, /activity, /keys).

    - `workspace_id=None` : vue cumulée sur tous les workspaces (`group_by=workspace`).
    - `workspace_id=<uuid>` : vue filtrée sur ce workspace précis.
    """
    ws_filtre = (workspace_id or "").strip() or None

    # Correspondance locale openrouter_workspace_id -> nom lisible
    ws_rows = (
        await session.execute(
            select(AiWorkspace).where(AiWorkspace.deleted_at.is_(None))
        )
    ).scalars().all()
    ws_names = {ws.openrouter_workspace_id: ws.name for ws in ws_rows}

    scope_label = (
        f"Workspace : {ws_names.get(ws_filtre, ws_filtre)}"
        if ws_filtre
        else "Tous les workspaces (cumulé)"
    )

    mgmt = await _get_active_key_row(session, KEY_KIND_MANAGEMENT)
    warnings: list[str] = []

    if mgmt is None:
        return OpenRouterDashboardRead(
            scope_workspace_id=ws_filtre,
            scope_label=scope_label,
            credits=OpenRouterCreditsRead(
                available=False,
                error="Aucune Management API Key active n'est configurée.",
            ),
            total_cost_usd=0.0,
            total_requests=0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_reasoning_tokens=0,
            avg_cost_per_request_usd=0.0,
            active_remote_keys_count=0,
            total_remote_keys_count=0,
            daily_series=[],
            by_model=[],
            by_workspace=[],
            activity=[],
            remote_keys=[],
            warnings=[
                "Configurez une Management API Key dans l'onglet Clés OpenRouter pour alimenter le tableau de bord."
            ],
        )

    mgmt_key = decrypt_token(mgmt.api_key_encrypted)

    async def _fetch_credits() -> OpenRouterCreditsRead:
        try:
            solde = await openrouter_client.get_credits(mgmt_key)
            return OpenRouterCreditsRead(
                available=True,
                total_credits=solde["total_credits"],
                total_usage=solde["total_usage"],
                remaining_credits=solde["remaining_credits"],
            )
        except ApiError as err:
            warnings.append(f"Crédits indisponibles : {err.message}")
            return OpenRouterCreditsRead(available=False, error=err.message)

    async def _fetch_activity() -> list[dict[str, Any]]:
        try:
            if ws_filtre:
                return await openrouter_client.get_activity(mgmt_key, workspace_id=ws_filtre)
            try:
                return await openrouter_client.get_activity(mgmt_key, group_by="workspace")
            except ApiError:
                # Repli si la clé management est restreinte à un seul workspace ou si group_by est refusé
                return await openrouter_client.get_activity(mgmt_key)
        except ApiError as err:
            warnings.append(f"Activité (/api/v1/activity) indisponible : {err.message}")
            return []

    async def _fetch_remote_keys() -> list[dict[str, Any]]:
        try:
            return await openrouter_client.list_remote_keys(mgmt_key, workspace_id=ws_filtre)
        except ApiError as err:
            warnings.append(f"Clés distantes (/api/v1/keys) indisponibles : {err.message}")
            return []

    credits, raw_activity, raw_keys = await asyncio.gather(
        _fetch_credits(), _fetch_activity(), _fetch_remote_keys()
    )

    activity_items: list[OpenRouterActivityItemRead] = []
    by_date: dict[str, dict[str, float | int]] = {}
    by_model: dict[str, dict[str, float | int]] = {}
    by_workspace: dict[str, dict[str, float | int]] = {}

    total_cost = 0.0
    total_requests = 0
    total_prompt = 0
    total_completion = 0
    total_reasoning = 0

    for item in raw_activity:
        date_str = str(item.get("date") or "")[:10]
        model_id = str(item.get("model") or item.get("model_permaslug") or "inconnu")
        provider = item.get("provider_name")
        item_ws_id = str(item.get("workspace_id") or ws_filtre or "").strip() or None
        item_ws_name = ws_names.get(item_ws_id, item_ws_id) if item_ws_id else None
        cost = _to_float(item.get("usage"))
        reqs = _to_int(item.get("requests"))
        prompt_tok = _to_int(item.get("prompt_tokens"))
        comp_tok = _to_int(item.get("completion_tokens"))
        reason_tok = _to_int(item.get("reasoning_tokens"))

        activity_items.append(
            OpenRouterActivityItemRead(
                date=date_str,
                model=model_id,
                provider_name=str(provider) if provider is not None else None,
                workspace_id=item_ws_id,
                workspace_name=item_ws_name,
                usage_usd=round(cost, 7),
                requests=reqs,
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                reasoning_tokens=reason_tok,
            )
        )

        total_cost += cost
        total_requests += reqs
        total_prompt += prompt_tok
        total_completion += comp_tok
        total_reasoning += reason_tok

        if date_str:
            d = by_date.setdefault(date_str, {"cost": 0.0, "tokens": 0, "requests": 0})
            d["cost"] = float(d["cost"]) + cost
            d["tokens"] = int(d["tokens"]) + prompt_tok + comp_tok
            d["requests"] = int(d["requests"]) + reqs

        m = by_model.setdefault(
            model_id,
            {"cost": 0.0, "requests": 0, "prompt": 0, "completion": 0, "reasoning": 0},
        )
        m["cost"] = float(m["cost"]) + cost
        m["requests"] = int(m["requests"]) + reqs
        m["prompt"] = int(m["prompt"]) + prompt_tok
        m["completion"] = int(m["completion"]) + comp_tok
        m["reasoning"] = int(m["reasoning"]) + reason_tok

        if item_ws_id:
            w = by_workspace.setdefault(item_ws_id, {"cost": 0.0, "requests": 0, "tokens": 0})
            w["cost"] = float(w["cost"]) + cost
            w["requests"] = int(w["requests"]) + reqs
            w["tokens"] = int(w["tokens"]) + prompt_tok + comp_tok

    activity_items.sort(key=lambda x: (x.date, x.usage_usd), reverse=True)

    daily_series = [
        OpenRouterDailyPointRead(
            date=date_key,
            cost_usd=round(float(vals["cost"]), 6),
            tokens=int(vals["tokens"]),
            requests=int(vals["requests"]),
        )
        for date_key, vals in sorted(by_date.items())
    ]

    model_costs = [
        OpenRouterModelCostRead(
            model=model_key,
            cost_usd=round(float(vals["cost"]), 6),
            requests=int(vals["requests"]),
            prompt_tokens=int(vals["prompt"]),
            completion_tokens=int(vals["completion"]),
            reasoning_tokens=int(vals["reasoning"]),
        )
        for model_key, vals in sorted(
            by_model.items(), key=lambda kv: float(kv[1]["cost"]), reverse=True
        )
    ]

    workspace_costs = [
        OpenRouterWorkspaceCostRead(
            workspace_id=ws_key,
            workspace_name=ws_names.get(ws_key, ws_key),
            cost_usd=round(float(vals["cost"]), 6),
            requests=int(vals["requests"]),
            tokens=int(vals["tokens"]),
        )
        for ws_key, vals in sorted(
            by_workspace.items(), key=lambda kv: float(kv[1]["cost"]), reverse=True
        )
    ]

    remote_keys: list[OpenRouterRemoteKeyRead] = []
    for rk in raw_keys:
        remote_keys.append(
            OpenRouterRemoteKeyRead(
                hash=str(rk.get("hash") or ""),
                label=str(rk.get("name") or rk.get("label") or "Clé sans nom"),
                limit=_to_float(rk["limit"]) if rk.get("limit") is not None else None,
                limit_remaining=(
                    _to_float(rk["limit_remaining"])
                    if rk.get("limit_remaining") is not None
                    else None
                ),
                usage=round(_to_float(rk.get("usage")), 6),
                usage_daily=(
                    round(_to_float(rk["usage_daily"]), 6)
                    if rk.get("usage_daily") is not None
                    else None
                ),
                usage_weekly=(
                    round(_to_float(rk["usage_weekly"]), 6)
                    if rk.get("usage_weekly") is not None
                    else None
                ),
                usage_monthly=(
                    round(_to_float(rk["usage_monthly"]), 6)
                    if rk.get("usage_monthly") is not None
                    else None
                ),
                disabled=bool(rk.get("disabled", False)),
                expires_at=str(rk["expires_at"]) if rk.get("expires_at") else None,
                created_at=str(rk["created_at"]) if rk.get("created_at") else None,
            )
        )

    active_remote = sum(1 for k in remote_keys if not k.disabled)
    avg_cost = round(total_cost / total_requests, 6) if total_requests > 0 else 0.0

    return OpenRouterDashboardRead(
        scope_workspace_id=ws_filtre,
        scope_label=scope_label,
        credits=credits,
        total_cost_usd=round(total_cost, 6),
        total_requests=total_requests,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_reasoning_tokens=total_reasoning,
        avg_cost_per_request_usd=avg_cost,
        active_remote_keys_count=active_remote,
        total_remote_keys_count=len(remote_keys),
        daily_series=daily_series,
        by_model=model_costs,
        by_workspace=workspace_costs,
        activity=activity_items,
        remote_keys=remote_keys,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Workspaces OpenRouter
# ---------------------------------------------------------------------------


def _normaliser_workspace_openrouter(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise les champs d'un workspace renvoyé par l'API OpenRouter."""
    ext_id = str(item.get("id") or item.get("slug") or "")
    return {
        "openrouter_workspace_id": ext_id,
        "name": str(item.get("name") or ext_id or "Workspace sans nom"),
        "slug": item.get("slug"),
        "description": item.get("description"),
        "default_text_model": item.get("default_text_model") or item.get("DefaultTextModel"),
        "default_image_model": item.get("default_image_model") or item.get("DefaultImageModel"),
        "default_provider_sort": (
            item.get("default_provider_sort") or item.get("DefaultProviderSort")
        ),
        "is_default": bool(item.get("is_default", False)),
        "raw_metadata_json": item,
    }


async def lister_workspaces(session: AsyncSession) -> list[AiWorkspaceRead]:
    """Liste les workspaces actifs enregistrés en base."""
    rows = (
        await session.execute(
            select(AiWorkspace)
            .where(AiWorkspace.deleted_at.is_(None))
            .order_by(AiWorkspace.is_selected.desc(), AiWorkspace.is_default.desc(), AiWorkspace.name)
        )
    ).scalars().all()
    return [_workspace_to_read(ws) for ws in rows]


async def synchroniser_workspaces(
    session: AsyncSession, par: User
) -> AiWorkspaceSyncRead:
    """Synchronise les workspaces depuis OpenRouter via la Management API Key."""
    mgmt_key = await _require_decrypted_key(session, KEY_KIND_MANAGEMENT)
    items = await openrouter_client.list_workspaces(mgmt_key)
    maintenant = datetime.now(UTC)

    existants = {
        ws.openrouter_workspace_id: ws
        for ws in (
            await session.execute(
                select(AiWorkspace).where(AiWorkspace.deleted_at.is_(None))
            )
        ).scalars().all()
    }

    vus: set[str] = set()
    for raw in items:
        norm = _normaliser_workspace_openrouter(raw)
        ext_id = norm["openrouter_workspace_id"]
        if not ext_id:
            continue
        vus.add(ext_id)
        ws = existants.get(ext_id)
        if ws is None:
            ws = AiWorkspace(
                openrouter_workspace_id=ext_id,
                name=norm["name"],
                slug=norm["slug"],
                description=norm["description"],
                default_text_model=norm["default_text_model"],
                default_image_model=norm["default_image_model"],
                default_provider_sort=norm["default_provider_sort"],
                is_default=norm["is_default"],
                raw_metadata_json=norm["raw_metadata_json"],
                last_synced_at=maintenant,
                id_users_created_by=par.id_users,
                id_users_changed_by=par.id_users,
            )
            session.add(ws)
        else:
            ws.name = norm["name"]
            ws.slug = norm["slug"]
            ws.description = norm["description"]
            ws.default_text_model = norm["default_text_model"]
            ws.default_image_model = norm["default_image_model"]
            ws.default_provider_sort = norm["default_provider_sort"]
            ws.is_default = norm["is_default"]
            ws.raw_metadata_json = norm["raw_metadata_json"]
            ws.last_synced_at = maintenant
            ws.id_users_changed_by = par.id_users

    await session.commit()
    workspaces = await lister_workspaces(session)
    return AiWorkspaceSyncRead(
        synced_count=len(vus),
        message=f"{len(vus)} workspace(s) synchronisé(s) depuis OpenRouter.",
        workspaces=workspaces,
    )


async def creer_workspace(
    session: AsyncSession, donnees: AiWorkspaceCreate, par: User
) -> AiWorkspaceRead:
    """Crée un workspace sur OpenRouter puis l'enregistre en base."""
    mgmt_key = await _require_decrypted_key(session, KEY_KIND_MANAGEMENT)
    cree = await openrouter_client.create_workspace(
        mgmt_key,
        name=donnees.name.strip(),
        description=donnees.description,
        default_text_model=donnees.default_text_model,
        default_image_model=donnees.default_image_model,
        default_provider_sort=donnees.default_provider_sort,
    )
    norm = _normaliser_workspace_openrouter(cree)
    ext_id = norm["openrouter_workspace_id"] or donnees.name.strip().lower().replace(" ", "-")
    maintenant = datetime.now(UTC)

    ws = AiWorkspace(
        openrouter_workspace_id=ext_id,
        name=norm["name"] or donnees.name.strip(),
        slug=norm["slug"],
        description=norm["description"] if norm["description"] is not None else donnees.description,
        default_text_model=norm["default_text_model"] or donnees.default_text_model,
        default_image_model=norm["default_image_model"] or donnees.default_image_model,
        default_provider_sort=norm["default_provider_sort"] or donnees.default_provider_sort,
        monthly_budget_usd=donnees.monthly_budget_usd,
        is_default=norm["is_default"],
        raw_metadata_json=norm["raw_metadata_json"],
        last_synced_at=maintenant,
        id_users_created_by=par.id_users,
        id_users_changed_by=par.id_users,
    )
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return _workspace_to_read(ws)


async def modifier_workspace(
    session: AsyncSession, id_workspace: int, donnees: AiWorkspaceUpdate, par: User
) -> AiWorkspaceRead:
    """Met à jour un workspace sur OpenRouter et/ou change le workspace sélectionné IAGORA."""
    ws = (
        await session.execute(
            select(AiWorkspace).where(
                AiWorkspace.id_ai_workspaces == id_workspace,
                AiWorkspace.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("Workspace introuvable.")

    champs_distants = (
        donnees.name is not None
        or donnees.description is not None
        or donnees.default_text_model is not None
        or donnees.default_image_model is not None
        or donnees.default_provider_sort is not None
    )
    if champs_distants:
        mgmt_key = await _require_decrypted_key(session, KEY_KIND_MANAGEMENT)
        maj = await openrouter_client.update_workspace(
            mgmt_key,
            ws.openrouter_workspace_id,
            name=donnees.name.strip() if donnees.name is not None else None,
            description=donnees.description,
            default_text_model=donnees.default_text_model,
            default_image_model=donnees.default_image_model,
            default_provider_sort=donnees.default_provider_sort,
        )
        if maj:
            ws.raw_metadata_json = maj
            ws.last_synced_at = datetime.now(UTC)

    if donnees.name is not None:
        ws.name = donnees.name.strip()
    if donnees.description is not None:
        ws.description = donnees.description
    if donnees.default_text_model is not None:
        ws.default_text_model = donnees.default_text_model or None
    if donnees.default_image_model is not None:
        ws.default_image_model = donnees.default_image_model or None
    if donnees.default_provider_sort is not None:
        ws.default_provider_sort = donnees.default_provider_sort
    if donnees.monthly_budget_usd is not None:
        ws.monthly_budget_usd = Decimal(donnees.monthly_budget_usd)

    if donnees.is_selected is True:
        await session.execute(
            update(AiWorkspace)
            .where(AiWorkspace.deleted_at.is_(None))
            .values(is_selected=False)
        )
        ws.is_selected = True
    elif donnees.is_selected is False:
        ws.is_selected = False

    ws.id_users_changed_by = par.id_users
    await session.commit()
    await session.refresh(ws)
    return _workspace_to_read(ws)


async def supprimer_workspace(
    session: AsyncSession, id_workspace: int, par: User
) -> None:
    """Supprime un workspace sur OpenRouter puis l'archive localement."""
    ws = (
        await session.execute(
            select(AiWorkspace).where(
                AiWorkspace.id_ai_workspaces == id_workspace,
                AiWorkspace.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("Workspace introuvable.")

    mgmt_key = await _require_decrypted_key(session, KEY_KIND_MANAGEMENT)
    await openrouter_client.delete_workspace(mgmt_key, ws.openrouter_workspace_id)

    ws.deleted_at = datetime.now(UTC)
    ws.is_selected = False
    ws.id_users_changed_by = par.id_users
    await session.commit()


# ---------------------------------------------------------------------------
# Catalogue des modèles IA & Affectations
# ---------------------------------------------------------------------------


async def lister_modeles(
    session: AsyncSession,
    *,
    search: str | None = None,
    provider: str | None = None,
    enabled_only: bool = False,
) -> list[AiModelRead]:
    """Liste les modèles OpenRouter synchronisés, avec filtres facultatifs."""
    stmt = select(AiModel)
    if enabled_only:
        stmt = stmt.where(AiModel.is_enabled.is_(True))
    if provider:
        stmt = stmt.where(AiModel.provider_slug == provider.strip().lower())
    if search:
        terme = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(AiModel.name).like(terme)
            | func.lower(AiModel.openrouter_model_id).like(terme)
            | func.lower(AiModel.provider_slug).like(terme)
        )
    stmt = stmt.order_by(AiModel.is_enabled.desc(), AiModel.provider_slug, AiModel.name)
    rows = (await session.execute(stmt)).scalars().all()
    return [_model_to_read(m) for m in rows]


async def synchroniser_modeles(session: AsyncSession) -> AiModelsSyncRead:
    """Importe/met à jour le catalogue OpenRouter via la clé API Standard (ou Management)."""
    std = await _get_active_key_row(session, KEY_KIND_STANDARD)
    mgmt = await _get_active_key_row(session, KEY_KIND_MANAGEMENT)
    source = std or mgmt
    if source is None:
        raise ApiError(
            "openrouter_key_missing",
            "Aucune clé OpenRouter active n'est configurée pour synchroniser le catalogue.",
            400,
        )

    api_key = decrypt_token(source.api_key_encrypted)
    items = await openrouter_client.list_models(api_key)
    maintenant = datetime.now(UTC)

    existants = {
        m.openrouter_model_id: m
        for m in (await session.execute(select(AiModel))).scalars().all()
    }

    nb_traites = 0
    for raw in items:
        model_id = str(raw.get("id") or "").strip()
        if not model_id:
            continue
        provider_slug = model_id.split("/", 1)[0].lower() if "/" in model_id else "openrouter"
        name = str(raw.get("name") or model_id)[:200]
        pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
        arch = raw.get("architecture") if isinstance(raw.get("architecture"), dict) else {}
        in_mod = arch.get("input_modalities")
        out_mod = arch.get("output_modalities")
        ctx = raw.get("context_length")

        m = existants.get(model_id)
        if m is None:
            m = AiModel(
                openrouter_model_id=model_id[:180],
                name=name,
                provider_slug=provider_slug[:80],
                description=raw.get("description"),
                context_length=int(ctx) if isinstance(ctx, int) else None,
                pricing_prompt=(
                    str(pricing.get("prompt"))[:40] if pricing.get("prompt") is not None else None
                ),
                pricing_completion=(
                    str(pricing.get("completion"))[:40]
                    if pricing.get("completion") is not None
                    else None
                ),
                input_modalities_json=list(in_mod) if isinstance(in_mod, list) else ["text"],
                output_modalities_json=list(out_mod) if isinstance(out_mod, list) else ["text"],
                is_enabled=False,
                raw_metadata_json=raw,
                last_synced_at=maintenant,
            )
            session.add(m)
            existants[model_id] = m
        else:
            m.name = name
            m.provider_slug = provider_slug[:80]
            m.description = raw.get("description")
            m.context_length = int(ctx) if isinstance(ctx, int) else None
            m.pricing_prompt = (
                str(pricing.get("prompt"))[:40] if pricing.get("prompt") is not None else None
            )
            m.pricing_completion = (
                str(pricing.get("completion"))[:40]
                if pricing.get("completion") is not None
                else None
            )
            m.input_modalities_json = list(in_mod) if isinstance(in_mod, list) else ["text"]
            m.output_modalities_json = list(out_mod) if isinstance(out_mod, list) else ["text"]
            m.raw_metadata_json = raw
            m.last_synced_at = maintenant
        nb_traites += 1

    await session.commit()
    enabled_count = int(
        (
            await session.execute(
                select(func.count(AiModel.id_ai_models)).where(AiModel.is_enabled.is_(True))
            )
        ).scalar_one()
    )
    return AiModelsSyncRead(
        synced_count=nb_traites,
        enabled_count=enabled_count,
        message=f"{nb_traites} modèles synchronisés depuis OpenRouter.",
    )


async def basculer_modele(
    session: AsyncSession, id_model: int, is_enabled: bool
) -> AiModelRead:
    """Active ou désactive un modèle OpenRouter dans IAGORA."""
    m = (
        await session.execute(select(AiModel).where(AiModel.id_ai_models == id_model))
    ).scalar_one_or_none()
    if m is None:
        raise NotFoundError("Modèle IA introuvable.")
    m.is_enabled = is_enabled
    await session.commit()
    await session.refresh(m)
    return _model_to_read(m)


async def lister_affectations(session: AsyncSession) -> list[AiTaskAssignmentRead]:
    """Renvoie l'affectation des 4 tâches métier IAGORA."""
    lignes = (
        await session.execute(
            select(AiTaskAssignment, AiModel, AiWorkspace)
            .outerjoin(AiModel, AiModel.id_ai_models == AiTaskAssignment.id_ai_models)
            .outerjoin(
                AiWorkspace,
                (AiWorkspace.id_ai_workspaces == AiTaskAssignment.id_ai_workspaces)
                & (AiWorkspace.deleted_at.is_(None)),
            )
        )
    ).all()
    par_code = {a.task_code: (a, m, ws) for a, m, ws in lignes}
    result: list[AiTaskAssignmentRead] = []
    for code in TASK_CODES:
        item = par_code.get(code)
        if item is None:
            continue
        a, m, ws = item
        result.append(
            AiTaskAssignmentRead(
                task_code=a.task_code,
                task_label=TASK_LABELS.get(a.task_code, a.task_code),
                id_ai_models=a.id_ai_models,
                model_name=m.name if m else None,
                openrouter_model_id=m.openrouter_model_id if m else None,
                id_ai_workspaces=a.id_ai_workspaces if ws else None,
                workspace_name=ws.name if ws else None,
                reasoning_effort=a.reasoning_effort,  # type: ignore[arg-type]
                updated_at=a.updated_at,
            )
        )
    return result


async def modifier_affectation(
    session: AsyncSession,
    task_code: str,
    donnees: AiTaskAssignmentUpdate,
    par: User,
) -> AiTaskAssignmentRead:
    """Met à jour le modèle (et le workspace optionnel) affecté à une tâche métier."""
    if task_code not in TASK_CODES:
        raise NotFoundError("Tâche métier IA inconnue.")

    affectation = (
        await session.execute(
            select(AiTaskAssignment).where(AiTaskAssignment.task_code == task_code)
        )
    ).scalar_one_or_none()
    if affectation is None:
        affectation = AiTaskAssignment(task_code=task_code)
        session.add(affectation)

    modele: AiModel | None = None
    if donnees.id_ai_models is not None:
        modele = (
            await session.execute(
                select(AiModel).where(AiModel.id_ai_models == donnees.id_ai_models)
            )
        ).scalar_one_or_none()
        if modele is None:
            raise NotFoundError("Modèle IA introuvable.")
        if not modele.is_enabled:
            modele.is_enabled = True

    ws: AiWorkspace | None = None
    if donnees.id_ai_workspaces is not None:
        ws = (
            await session.execute(
                select(AiWorkspace).where(
                    AiWorkspace.id_ai_workspaces == donnees.id_ai_workspaces,
                    AiWorkspace.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if ws is None:
            raise NotFoundError("Workspace introuvable.")

    affectation.id_ai_models = donnees.id_ai_models
    affectation.id_ai_workspaces = donnees.id_ai_workspaces
    affectation.reasoning_effort = donnees.reasoning_effort
    affectation.id_users_changed_by = par.id_users
    affectation.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(affectation)

    return AiTaskAssignmentRead(
        task_code=affectation.task_code,
        task_label=TASK_LABELS.get(affectation.task_code, affectation.task_code),
        id_ai_models=affectation.id_ai_models,
        model_name=modele.name if modele else None,
        openrouter_model_id=modele.openrouter_model_id if modele else None,
        id_ai_workspaces=affectation.id_ai_workspaces,
        workspace_name=ws.name if ws else None,
        reasoning_effort=affectation.reasoning_effort,  # type: ignore[arg-type]
        updated_at=affectation.updated_at,
    )


# ---------------------------------------------------------------------------
# Bac à sable IA (comparateur multi-modèles côte à côte)
# ---------------------------------------------------------------------------


logger = logging.getLogger(__name__)

_DATA_URL_IMAGE_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp|gif));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _construire_messages_bac_a_sable(donnees: SandboxCompareRequest) -> list[dict[str, Any]]:
    """Assemble les messages system/user selon le cas d'utilisation strict."""
    blocs_systeme: list[str] = [donnees.system_prompt.strip()]

    if donnees.tone and donnees.tone.strip():
        blocs_systeme.append(f"Ton imposé : {donnees.tone.strip()}.")

    if donnees.use_case == "image_generation":
        mode_txt = (
            "Modification d'image existante à partir du/des visuels de référence fournis."
            if donnees.image_mode == "edit"
            else "Création d'un nouveau visuel original."
        )
        blocs_systeme.append(f"Mode visuel : {mode_txt}")
        if donnees.image_aspect_ratio:
            blocs_systeme.append(f"Format / ratio souhaité : {donnees.image_aspect_ratio}.")
        if donnees.reference_media_notes:
            notes = "\n".join(f"- {n.strip()}" for n in donnees.reference_media_notes if n.strip())
            if notes:
                blocs_systeme.append(f"Médias de référence fournis :\n{notes}")

    if donnees.knowledge_context and donnees.knowledge_context.strip():
        titre_ctx = (
            "Base de connaissances (réponds strictement à partir de ces extraits)"
            if donnees.use_case == "message_rag"
            else "Contexte & Brief éditorial"
        )
        blocs_systeme.append(f"{titre_ctx} :\n{donnees.knowledge_context.strip()}")

    if donnees.json_output_enabled and donnees.json_output_schema and donnees.json_output_schema.strip():
        blocs_systeme.append(
            "IMPORTANT : Réponds STRICTEMENT avec un objet JSON valide respectant cette structure :\n"
            f"{donnees.json_output_schema.strip()}"
        )
    elif donnees.json_output_enabled:
        blocs_systeme.append("IMPORTANT : Réponds STRICTEMENT avec un objet JSON valide.")

    system_content = "\n\n".join(blocs_systeme)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]

    # Collecter toutes les images de référence (médias de référence IAGORA + fichier/URL manuel)
    ref_urls: list[str] = []
    for u in donnees.reference_image_urls:
        nettoyee = (u or "").strip()
        if nettoyee and nettoyee not in ref_urls:
            ref_urls.append(nettoyee)
    if donnees.reference_image_url and donnees.reference_image_url.strip():
        u = donnees.reference_image_url.strip()
        if u not in ref_urls:
            ref_urls.append(u)

    if ref_urls:
        parts: list[dict[str, Any]] = [{"type": "text", "text": donnees.user_prompt.strip()}]
        for url in ref_urls:
            parts.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": parts})
    else:
        messages.append({"role": "user", "content": donnees.user_prompt.strip()})

    return messages


async def _stocker_image_bac_a_sable(
    stockage: Stockage | None,
    raw_src: str,
    slot_id: str,
) -> tuple[str, str | None]:
    """Dépose une image générée (data URL base64 ou URL distante) dans R2 sous `bac-a-sable/`."""
    if stockage is None:
        return raw_src, None

    octets: bytes | None = None
    mime = "image/png"

    match = _DATA_URL_IMAGE_RE.match(raw_src.strip())
    if match:
        mime = match.group(1).lower()
        try:
            octets = base64.b64decode(match.group(2))
        except Exception:
            logger.warning("Décodage base64 impossible pour une image du bac à sable.")
            return raw_src, None
    elif raw_src.startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                rep = await client.get(raw_src)
                if rep.status_code == 200 and rep.content:
                    octets = rep.content
                    ct = rep.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ct in _MIME_TO_EXT:
                        mime = ct
        except Exception:
            logger.warning("Téléchargement impossible pour l'image générée %s", raw_src[:120])
            return raw_src, None

    if not octets:
        return raw_src, None

    ext = _MIME_TO_EXT.get(mime, "png")
    maintenant = datetime.now(UTC)
    slug_slot = re.sub(r"[^a-z0-9_-]", "", slot_id.lower()) or "var"
    cle = f"bac-a-sable/{maintenant:%Y}/{maintenant:%m}/{uuid.uuid4().hex}_{slug_slot}.{ext}"

    try:
        await stockage.deposer(cle, io.BytesIO(octets), mime)
        return stockage.url_publique(cle), cle
    except Exception:
        logger.exception("Échec du dépôt R2 de l'image générée sous %s", cle)
        return raw_src, None


def _nettoyer_json_brut(corps: dict[str, Any], urls_r2: list[str]) -> dict[str, object]:
    """Remplace les gros blobs base64 par les URLs R2 pour garder le JSON inspectable léger."""
    import copy

    copie = copy.deepcopy(corps)
    choices = copie.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict) and urls_r2 and isinstance(msg.get("images"), list):
            msg["images"] = [{"url": u} for u in urls_r2]
    return copie


def _extraire_images_reponse(message: dict[str, Any]) -> list[str]:
    """Extrait les URLs ou data URLs d'images renvoyées par OpenRouter."""
    images: list[str] = []
    raw_images = message.get("images")
    if isinstance(raw_images, list):
        for item in raw_images:
            if isinstance(item, str) and item.strip():
                images.append(item.strip())
            elif isinstance(item, dict):
                url = item.get("url")
                if not url and isinstance(item.get("image_url"), dict):
                    url = item["image_url"].get("url")
                if isinstance(url, str) and url.strip():
                    images.append(url.strip())

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                img_obj = part.get("image_url")
                if isinstance(img_obj, dict) and isinstance(img_obj.get("url"), str):
                    images.append(img_obj["url"].strip())

    return images


def _extraire_texte_reponse(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        morceaux: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                morceaux.append(part["text"])
        return "\n".join(morceaux)
    return ""


async def comparer_bac_a_sable(
    session: AsyncSession,
    donnees: SandboxCompareRequest,
    par: User,
    stockage: Stockage | None = None,
) -> SandboxCompareResponse:
    """Exécute en parallèle les variantes choisies sur OpenRouter via la clé Sandbox (ou Standard)."""
    sandbox_key = await _get_active_key_row(session, KEY_KIND_SANDBOX)
    if sandbox_key is not None:
        source_row = sandbox_key
        key_source = "sandbox"
    else:
        std_key = await _get_active_key_row(session, KEY_KIND_STANDARD)
        if std_key is None:
            raise ApiError(
                "openrouter_key_missing",
                "Aucune clé OpenRouter (Sandbox ni Standard) n'est configurée. "
                "Enregistrez une clé Sandbox isolée ou une clé Standard.",
                400,
            )
        source_row = std_key
        key_source = "standard"

    api_key = decrypt_token(source_row.api_key_encrypted)
    messages = _construire_messages_bac_a_sable(donnees)

    # Charger les tarifs & modalités locaux pour estimation de repli et détection image-output
    model_ids = [v.model_id for v in donnees.variants]
    catalogue_rows = (
        await session.execute(
            select(AiModel).where(AiModel.openrouter_model_id.in_(model_ids))
        )
    ).scalars().all()
    catalogue_map = {m.openrouter_model_id: m for m in catalogue_rows}

    async def _executer_variante(v: Any) -> SandboxVariantResult:
        debut = time.perf_counter()
        info_locale = catalogue_map.get(v.model_id)
        output_mods = list(info_locale.output_modalities_json or []) if info_locale else []
        want_image_out = donnees.use_case == "image_generation" and (
            "image" in output_mods
            or any(
                mot in v.model_id.lower()
                for mot in ("image", "flux", "dall-e", "ideogram", "imagen", "sdxl", "recraft")
            )
        )

        try:
            corps = await openrouter_client.run_chat_completion(
                api_key,
                model=v.model_id,
                messages=messages,
                temperature=v.temperature,
                max_tokens=donnees.max_tokens,
                reasoning_effort=v.reasoning_effort,
                json_object=donnees.json_output_enabled and not want_image_out,
                request_image_output=want_image_out,
                image_aspect_ratio=donnees.image_aspect_ratio if want_image_out else None,
            )
        except ApiError as err:
            latence = int((time.perf_counter() - debut) * 1000)
            return SandboxVariantResult(
                slot_id=v.slot_id,
                model_id=v.model_id,
                reasoning_effort=v.reasoning_effort,
                temperature=v.temperature,
                ok=False,
                error=err.message,
                latency_ms=latence,
            )

        latence = int((time.perf_counter() - debut) * 1000)
        choices = corps.get("choices")
        message = (
            choices[0].get("message", {})
            if isinstance(choices, list) and choices and isinstance(choices[0], dict)
            else {}
        )
        if not isinstance(message, dict):
            message = {}

        texte = _extraire_texte_reponse(message)
        raw_images = _extraire_images_reponse(message)
        stored_urls: list[str] = []
        stored_keys: list[str] = []
        for img_src in raw_images:
            url_finale, cle_r2 = await _stocker_image_bac_a_sable(stockage, img_src, v.slot_id)
            stored_urls.append(url_finale)
            if cle_r2:
                stored_keys.append(cle_r2)

        reasoning_trace = message.get("reasoning")
        if not isinstance(reasoning_trace, str):
            reasoning_trace = None

        usage = corps.get("usage") if isinstance(corps.get("usage"), dict) else {}
        prompt_tok = _to_int(usage.get("prompt_tokens"))
        comp_tok = _to_int(usage.get("completion_tokens"))
        comp_details = (
            usage.get("completion_tokens_details")
            if isinstance(usage.get("completion_tokens_details"), dict)
            else {}
        )
        prompt_details = (
            usage.get("prompt_tokens_details")
            if isinstance(usage.get("prompt_tokens_details"), dict)
            else {}
        )
        reason_tok = _to_int(comp_details.get("reasoning_tokens"))
        cached_tok = _to_int(prompt_details.get("cached_tokens"))
        visible_tok = max(0, comp_tok - reason_tok)
        total_tok = _to_int(usage.get("total_tokens")) or (prompt_tok + comp_tok)

        # Coût réel retourné par OpenRouter (`usage.cost`), sinon estimation tarif catalogue
        raw_cost = usage.get("cost")
        if isinstance(raw_cost, (int, float)):
            cost_usd = float(raw_cost)
        else:
            p_in = _to_float(info_locale.pricing_prompt) if info_locale else 0.0
            p_out = _to_float(info_locale.pricing_completion) if info_locale else 0.0
            cost_usd = prompt_tok * p_in + comp_tok * p_out

        cost_usd = round(cost_usd, 7)
        raw_5k = cost_usd * 5000.0
        fee_5k = max(0.80, raw_5k * 0.055) if raw_5k > 0 else 0.0
        projected_5k = round(raw_5k + fee_5k, 2)

        raw_usage_json: dict[str, object] = {
            "id": corps.get("id"),
            "model": corps.get("model") or v.model_id,
            "provider": corps.get("provider"),
            "reasoning_effort": v.reasoning_effort,
            "temperature": v.temperature,
            "max_tokens": donnees.max_tokens,
            "stored_image_keys": stored_keys,
            "usage": usage,
        }
        raw_response_json = _nettoyer_json_brut(corps, stored_urls)

        return SandboxVariantResult(
            slot_id=v.slot_id,
            model_id=v.model_id,
            reasoning_effort=v.reasoning_effort,
            temperature=v.temperature,
            ok=True,
            text=texte,
            images=stored_urls,
            stored_image_keys=stored_keys,
            reasoning_trace=reasoning_trace,
            prompt_tokens=prompt_tok,
            completion_tokens=comp_tok,
            visible_tokens=visible_tok,
            reasoning_tokens=reason_tok,
            cached_tokens=cached_tok,
            total_tokens=total_tok,
            cost_usd=cost_usd,
            projected_monthly_5k_usd=projected_5k,
            latency_ms=latence,
            raw_usage_json=raw_usage_json,
            raw_response_json=raw_response_json,
        )

    results = list(await asyncio.gather(*(_executer_variante(v) for v in donnees.variants)))
    total_batch = round(sum(r.cost_usd for r in results), 7)

    run_row = AiSandboxRun(
        use_case=donnees.use_case,
        system_prompt=donnees.system_prompt.strip(),
        user_prompt=donnees.user_prompt.strip(),
        tone=(donnees.tone or "").strip() or None,
        json_output_enabled=donnees.json_output_enabled,
        json_output_schema=(donnees.json_output_schema or "").strip() or None,
        knowledge_context=(donnees.knowledge_context or "").strip() or None,
        image_mode=donnees.image_mode if donnees.use_case == "image_generation" else None,
        image_aspect_ratio=(
            donnees.image_aspect_ratio if donnees.use_case == "image_generation" else None
        ),
        key_source=key_source,
        key_masked=source_row.key_masked,
        total_batch_cost_usd=Decimal(str(total_batch)),
        variants_json=[v.model_dump(mode="json") for v in donnees.variants],
        results_json=[r.model_dump(mode="json") for r in results],
        id_users_created_by=par.id_users,
    )
    session.add(run_row)
    await session.commit()
    await session.refresh(run_row)

    return SandboxCompareResponse(
        id_ai_sandbox_runs=run_row.id_ai_sandbox_runs,
        use_case=donnees.use_case,
        key_source=key_source,  # type: ignore[arg-type]
        key_masked=source_row.key_masked,
        total_batch_cost_usd=total_batch,
        results=results,
        created_at=run_row.created_at,
    )


async def lister_historique_bac_a_sable(
    session: AsyncSession,
    *,
    use_case: str | None = None,
    limit: int = 50,
) -> list[SandboxRunHistoryRead]:
    """Renvoie l'historique des exécutions du Bac à sable IA (les plus récentes en premier)."""
    stmt = (
        select(AiSandboxRun, User)
        .outerjoin(User, User.id_users == AiSandboxRun.id_users_created_by)
        .order_by(AiSandboxRun.created_at.desc(), AiSandboxRun.id_ai_sandbox_runs.desc())
        .limit(min(max(limit, 1), 200))
    )
    if use_case:
        stmt = stmt.where(AiSandboxRun.use_case == use_case)

    lignes = (await session.execute(stmt)).all()
    items: list[SandboxRunHistoryRead] = []
    for run, auteur in lignes:
        items.append(
            SandboxRunHistoryRead(
                id_ai_sandbox_runs=run.id_ai_sandbox_runs,
                use_case=run.use_case,  # type: ignore[arg-type]
                system_prompt=run.system_prompt,
                user_prompt=run.user_prompt,
                tone=run.tone,
                json_output_enabled=run.json_output_enabled,
                json_output_schema=run.json_output_schema,
                knowledge_context=run.knowledge_context,
                image_mode=run.image_mode,
                image_aspect_ratio=run.image_aspect_ratio,
                key_source=run.key_source,  # type: ignore[arg-type]
                key_masked=run.key_masked,
                total_batch_cost_usd=float(run.total_batch_cost_usd),
                variants=[SandboxVariantInput.model_validate(v) for v in (run.variants_json or [])],
                results=[SandboxVariantResult.model_validate(r) for r in (run.results_json or [])],
                created_by_name=_nom_utilisateur(auteur),
                created_at=run.created_at,
            )
        )
    return items


async def supprimer_historique_bac_a_sable(session: AsyncSession, id_run: int) -> None:
    """Supprime une entrée de l'historique du Bac à sable IA."""
    run = (
        await session.execute(
            select(AiSandboxRun).where(AiSandboxRun.id_ai_sandbox_runs == id_run)
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Exécution Bac à sable introuvable.")
    await session.delete(run)
    await session.commit()


# ---------------------------------------------------------------------------
# Prompts système & Prompt templates
# ---------------------------------------------------------------------------


def _prompt_to_read(p: AiPrompt, auteur: User | None = None) -> AiPromptRead:
    return AiPromptRead(
        id_ai_prompts=p.id_ai_prompts,
        prompt_kind=p.prompt_kind,  # type: ignore[arg-type]
        task_code=p.task_code,  # type: ignore[arg-type]
        title=p.title,
        version_number=p.version_number,
        content=p.content,
        char_count=len(p.content),
        description=p.description,
        is_default=p.is_default,
        created_by_name=_nom_utilisateur(auteur),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def lister_taches_prompts(
    session: AsyncSession, prompt_kind: str
) -> list[AiPromptTaskRead]:
    """Renvoie la liste des tâches métier avec le compteur de gabarits et l'état par défaut."""
    rows = (
        await session.execute(
            select(AiPrompt.task_code, AiPrompt.is_default).where(
                AiPrompt.prompt_kind == prompt_kind,
                AiPrompt.deleted_at.is_(None),
            )
        )
    ).all()

    counts: dict[str, int] = {}
    has_default: dict[str, bool] = {}
    for tc, is_def in rows:
        counts[tc] = counts.get(tc, 0) + 1
        if is_def:
            has_default[tc] = True

    return [
        AiPromptTaskRead(
            code=meta["code"],  # type: ignore[arg-type]
            label=meta["label"],
            description=meta["description"],
            count=counts.get(meta["code"], 0),
            has_default=has_default.get(meta["code"], False),
        )
        for meta in PROMPT_TASKS_META
    ]


async def lister_prompts(
    session: AsyncSession,
    *,
    prompt_kind: str,
    task_code: str | None = None,
) -> list[AiPromptRead]:
    """Liste les prompts/gabarits non supprimés (actif par défaut d'abord, puis versions récentes)."""
    stmt = (
        select(AiPrompt, User)
        .outerjoin(User, User.id_users == AiPrompt.id_users_created_by)
        .where(
            AiPrompt.prompt_kind == prompt_kind,
            AiPrompt.deleted_at.is_(None),
        )
        .order_by(
            AiPrompt.is_default.desc(),
            AiPrompt.version_number.desc(),
            AiPrompt.id_ai_prompts.desc(),
        )
    )
    if task_code:
        stmt = stmt.where(AiPrompt.task_code == task_code)

    lignes = (await session.execute(stmt)).all()
    return [_prompt_to_read(p, auteur) for p, auteur in lignes]


async def creer_prompt(
    session: AsyncSession, donnees: AiPromptCreate, par: User
) -> AiPromptRead:
    """Crée une nouvelle version de prompt système ou gabarit."""
    titre = donnees.title.strip()
    contenu = donnees.content.strip()
    if len(titre) < 2:
        raise ApiError(
            "validation_error",
            "Le titre du prompt doit contenir au moins 2 caractères.",
            status_code=422,
        )
    if not contenu:
        raise ApiError(
            "validation_error",
            "Le contenu du prompt ne peut pas être vide.",
            status_code=422,
        )
    description = (donnees.description or "").strip() or None

    for tentative in range(3):
        max_ver = (
            await session.execute(
                select(func.coalesce(func.max(AiPrompt.version_number), 0)).where(
                    AiPrompt.prompt_kind == donnees.prompt_kind,
                    AiPrompt.task_code == donnees.task_code,
                )
            )
        ).scalar_one()
        next_version = int(max_ver) + 1

        if donnees.is_default:
            await session.execute(
                update(AiPrompt)
                .where(
                    AiPrompt.prompt_kind == donnees.prompt_kind,
                    AiPrompt.task_code == donnees.task_code,
                    AiPrompt.deleted_at.is_(None),
                    AiPrompt.is_default.is_(True),
                )
                .values(is_default=False, id_users_changed_by=par.id_users)
            )
            await session.flush()

        nouveau = AiPrompt(
            prompt_kind=donnees.prompt_kind,
            task_code=donnees.task_code,
            title=titre,
            version_number=next_version,
            content=contenu,
            description=description,
            is_default=donnees.is_default,
            id_users_created_by=par.id_users,
            id_users_changed_by=par.id_users,
        )
        session.add(nouveau)
        try:
            await session.commit()
            await session.refresh(nouveau)
            return _prompt_to_read(nouveau, par)
        except IntegrityError as exc:
            await session.rollback()
            if tentative == 2:
                raise ConflictError(
                    "Conflit de version concurrente lors de la création du prompt. Veuillez réessayer."
                ) from exc

    raise ConflictError("Impossible d'allouer un numéro de version unique.")


async def modifier_prompt(
    session: AsyncSession, id_prompt: int, donnees: AiPromptUpdate, par: User
) -> AiPromptRead:
    """Met à jour le titre, la description ou le contenu d'un prompt existant."""
    ligne = (
        await session.execute(
            select(AiPrompt, User)
            .outerjoin(User, User.id_users == AiPrompt.id_users_created_by)
            .where(AiPrompt.id_ai_prompts == id_prompt, AiPrompt.deleted_at.is_(None))
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Prompt introuvable.")
    prompt, auteur = ligne

    if donnees.title is not None:
        titre = donnees.title.strip()
        if len(titre) < 2:
            raise ApiError(
                "validation_error",
                "Le titre du prompt doit contenir au moins 2 caractères.",
                status_code=422,
            )
        prompt.title = titre
    if donnees.content is not None:
        contenu = donnees.content.strip()
        if not contenu:
            raise ApiError(
                "validation_error",
                "Le contenu du prompt ne peut pas être vide.",
                status_code=422,
            )
        prompt.content = contenu
    if donnees.description is not None:
        prompt.description = donnees.description.strip() or None
    prompt.id_users_changed_by = par.id_users

    await session.commit()
    await session.refresh(prompt)
    return _prompt_to_read(prompt, auteur)


async def activer_prompt_par_defaut(
    session: AsyncSession, id_prompt: int, par: User
) -> AiPromptRead:
    """Définit ce prompt/gabarit comme actif par défaut pour son couple (kind, task_code)."""
    ligne = (
        await session.execute(
            select(AiPrompt, User)
            .outerjoin(User, User.id_users == AiPrompt.id_users_created_by)
            .where(AiPrompt.id_ai_prompts == id_prompt, AiPrompt.deleted_at.is_(None))
        )
    ).first()
    if ligne is None:
        raise NotFoundError("Prompt introuvable.")
    prompt, auteur = ligne

    await session.execute(
        update(AiPrompt)
        .where(
            AiPrompt.prompt_kind == prompt.prompt_kind,
            AiPrompt.task_code == prompt.task_code,
            AiPrompt.deleted_at.is_(None),
            AiPrompt.id_ai_prompts != prompt.id_ai_prompts,
            AiPrompt.is_default.is_(True),
        )
        .values(is_default=False, id_users_changed_by=par.id_users)
    )
    await session.flush()

    prompt.is_default = True
    prompt.id_users_changed_by = par.id_users
    await session.commit()
    await session.refresh(prompt)
    return _prompt_to_read(prompt, auteur)


async def supprimer_prompt(
    session: AsyncSession, id_prompt: int, par: User
) -> None:
    """Archive (soft-delete) un prompt/gabarit."""
    prompt = (
        await session.execute(
            select(AiPrompt).where(
                AiPrompt.id_ai_prompts == id_prompt,
                AiPrompt.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise NotFoundError("Prompt introuvable.")

    prompt.deleted_at = datetime.now(UTC)
    prompt.is_default = False
    prompt.id_users_changed_by = par.id_users
    await session.commit()


# ---------------------------------------------------------------------------
# Génération de publications v2 (relie Modèles IA, Prompts actifs, Médias & R2)
# ---------------------------------------------------------------------------

_TONE_LABELS_FR: dict[str, str] = {
    "inspiring": "Inspirant",
    "direct": "Direct et percutant",
    "funny": "Décalé / drôle mais maîtrisé",
    "professional": "Professionnel, accessible et concret",
}

_NETWORK_LABELS_FR: dict[str, str] = {
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "x": "X (Twitter)",
}


async def _get_active_generation_key(
    session: AsyncSession,
) -> tuple[OpenRouterApiKey | None, str | None]:
    """Privilégie la clé Standard pour la production, avec repli sur Sandbox si seule celle-ci existe."""
    std = await _get_active_key_row(session, KEY_KIND_STANDARD)
    if std is not None:
        return std, "standard"
    sbx = await _get_active_key_row(session, KEY_KIND_SANDBOX)
    if sbx is not None:
        return sbx, "sandbox"
    return None, None


async def _get_task_assignment_with_model(
    session: AsyncSession, task_code: str
) -> tuple[AiTaskAssignment | None, AiModel | None]:
    ligne = (
        await session.execute(
            select(AiTaskAssignment, AiModel)
            .outerjoin(AiModel, AiModel.id_ai_models == AiTaskAssignment.id_ai_models)
            .where(AiTaskAssignment.task_code == task_code)
        )
    ).first()
    if ligne is None:
        return None, None
    return ligne[0], ligne[1]


async def _get_default_prompt(
    session: AsyncSession, prompt_kind: str, task_code: str
) -> AiPrompt | None:
    return (
        await session.execute(
            select(AiPrompt).where(
                AiPrompt.prompt_kind == prompt_kind,
                AiPrompt.task_code == task_code,
                AiPrompt.is_default.is_(True),
                AiPrompt.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


def _prompt_summary(p: AiPrompt | None) -> ActivePromptSummaryRead | None:
    if p is None:
        return None
    return ActivePromptSummaryRead(
        id_ai_prompts=p.id_ai_prompts,
        title=p.title,
        version_number=p.version_number,
    )


def _prompt_label(p: AiPrompt | None) -> str | None:
    if p is None:
        return None
    return f"v{p.version_number} · {p.title}"


def _interpoler_gabarit(template: str, variables: dict[str, str]) -> str:
    """Remplace les placeholders `{{cle}}` présents dans un gabarit sans échouer sur les inconnus."""
    resultat = template
    for cle, valeur in variables.items():
        resultat = resultat.replace(f"{{{{{cle}}}}}", valeur)
    return resultat


def _extraire_json_bloc(texte: str) -> dict[str, Any]:
    """Parse le JSON retourné par un LLM même s'il est entouré de fences Markdown."""
    nettoye = texte.strip()
    if nettoye.startswith("```"):
        nettoye = re.sub(r"^```(?:json)?\s*", "", nettoye, flags=re.IGNORECASE)
        nettoye = re.sub(r"\s*```$", "", nettoye)
    try:
        data = json.loads(nettoye)
        return data if isinstance(data, dict) else {}
    except ValueError:
        debut = nettoye.find("{")
        fin = nettoye.rfind("}")
        if debut != -1 and fin > debut:
            try:
                data = json.loads(nettoye[debut : fin + 1])
                return data if isinstance(data, dict) else {}
            except ValueError:
                return {}
        return {}


async def obtenir_contexte_generation_publication(
    session: AsyncSession,
) -> PublicationGenerationContextRead:
    """Renvoie la configuration IA active (modèles affectés, effort, prompts par défaut, clé)."""
    key_row, key_source = await _get_active_generation_key(session)
    text_assign, text_model = await _get_task_assignment_with_model(session, TASK_TEXT_GENERATION)
    img_assign, img_model = await _get_task_assignment_with_model(session, TASK_IMAGE_GENERATION)

    text_sys = await _get_default_prompt(session, PROMPT_KIND_SYSTEM, "publication_description")
    text_tpl = await _get_default_prompt(session, PROMPT_KIND_TEMPLATE, "publication_description")
    img_sys = await _get_default_prompt(session, PROMPT_KIND_SYSTEM, "image_generation")
    img_tpl = await _get_default_prompt(session, PROMPT_KIND_TEMPLATE, "image_generation")

    return PublicationGenerationContextRead(
        has_api_key=key_row is not None,
        key_source=key_source,  # type: ignore[arg-type]
        text_model=ActiveTaskModelSummaryRead(
            task_code=TASK_TEXT_GENERATION,  # type: ignore[arg-type]
            model_id=text_model.openrouter_model_id if text_model else None,
            model_name=text_model.name if text_model else None,
            reasoning_effort=text_assign.reasoning_effort if text_assign else None,  # type: ignore[arg-type]
        ),
        image_model=ActiveTaskModelSummaryRead(
            task_code=TASK_IMAGE_GENERATION,  # type: ignore[arg-type]
            model_id=img_model.openrouter_model_id if img_model else None,
            model_name=img_model.name if img_model else None,
            reasoning_effort=img_assign.reasoning_effort if img_assign else None,  # type: ignore[arg-type]
        ),
        text_system_prompt=_prompt_summary(text_sys),
        text_template_prompt=_prompt_summary(text_tpl),
        image_system_prompt=_prompt_summary(img_sys),
        image_template_prompt=_prompt_summary(img_tpl),
    )


async def generer_textes_publication(
    session: AsyncSession,
    donnees: PublicationTextGenerationRequest,
    par: User,
) -> PublicationTextGenerationResponse:
    """Génère un lot de propositions de textes par réseau et par angle via OpenRouter."""
    del par  # réservé pour le futur journal d'audit / module 08
    key_row, key_source = await _get_active_generation_key(session)
    if key_row is None or key_source is None:
        raise ApiError(
            "openrouter_key_missing",
            "Aucune clé OpenRouter active n'est configurée. Rendez-vous dans Modèles IA v2 pour enregistrer une clé Standard.",
            400,
        )

    assign, modele = await _get_task_assignment_with_model(session, TASK_TEXT_GENERATION)
    if modele is None:
        raise ApiError(
            "ai_model_not_assigned",
            "Aucun modèle IA n'est affecté à la tâche « Génération de texte ». Configurez-le dans Modèles IA v2.",
            400,
        )

    sys_prompt = await _get_default_prompt(session, PROMPT_KIND_SYSTEM, "publication_description")
    tpl_prompt = await _get_default_prompt(session, PROMPT_KIND_TEMPLATE, "publication_description")

    reseaux = [n.strip().lower() for n in donnees.networks if n.strip()]
    angles = [a.strip() for a in donnees.angles if a.strip()] or ["Annonce", "Bénéfice", "Question"]
    ton_fr = _TONE_LABELS_FR.get(donnees.tone, donnees.tone)
    h_min = min(donnees.hashtags_min, donnees.hashtags_max)
    h_max = max(donnees.hashtags_min, donnees.hashtags_max)

    system_base = (
        sys_prompt.content
        if sys_prompt is not None
        else (
            "Tu es le responsable éditorial de DATUM Academy. Rédige des publications engageantes, "
            "structurées et calibrées pour chaque réseau social demandé."
        )
    )
    consigne_json = (
        "Réponds STRICTEMENT avec un objet JSON valide respectant exactement cette structure :\n"
        "{\n"
        '  "proposals_by_network": {\n'
        '    "<network_code>": [\n'
        "      {\n"
        '        "angle": "Annonce | Bénéfice | Question",\n'
        '        "title": "Titre court interne",\n'
        '        "paragraphs": ["Paragraphe 1", "Paragraphe 2", "Appel à l\'action"],\n'
        '        "hashtags": ["#Tag1", "#Tag2"]\n'
        "      }\n"
        "    ]\n"
        "  }\n"
        "}\n"
        f"Réseaux attendus comme clés exactes : {', '.join(reseaux)}.\n"
        f"Pour CHAQUE réseau, produis exactement {len(angles)} propositions dans l'ordre des angles : "
        f"{', '.join(angles)}.\n"
        f"Ton imposé : {ton_fr}. Langue : {donnees.language}. Format : {donnees.format}.\n"
        + (
            "Ne produis aucun hashtag (liste vide [])."
            if h_max == 0
            else f"Produis entre {h_min} et {h_max} hashtags pertinents commençant par #."
        )
    )
    if donnees.run_number > 1:
        consigne_json += (
            f"\nCeci est le lot de régénération n°{donnees.run_number} : propose des accroches, "
            "formulations et angles frais différents des formulations habituelles."
        )

    variables_tpl = {
        "sujet": donnees.subject,
        "theme": donnees.subject,
        "ton": ton_fr,
        "langue": donnees.language,
        "format": donnees.format,
        "reseaux": ", ".join(_NETWORK_LABELS_FR.get(r, r) for r in reseaux),
        "hashtags_min": str(h_min),
        "hashtags_max": str(h_max),
    }
    if tpl_prompt is not None:
        user_content = (
            _interpoler_gabarit(tpl_prompt.content, variables_tpl)
            + f"\n\nBrief de la publication :\n- Sujet : {donnees.subject}\n"
            + f"- Réseaux visés : {', '.join(reseaux)}\n"
            + f"- Ton : {ton_fr}\n"
            + f"- Langue : {donnees.language}"
        )
    else:
        user_content = (
            f"Sujet de la publication : {donnees.subject}\n"
            f"Format : {donnees.format}\n"
            f"Réseaux visés : {', '.join(reseaux)}\n"
            f"Ton : {ton_fr}\n"
            f"Langue : {donnees.language}\n"
            f"Angles à couvrir : {', '.join(angles)}\n"
            f"Hashtags demandés : entre {h_min} et {h_max}."
        )

    messages = [
        {"role": "system", "content": f"{system_base}\n\n{consigne_json}"},
        {"role": "user", "content": user_content},
    ]

    api_key = decrypt_token(key_row.api_key_encrypted)
    debut = time.perf_counter()
    corps = await openrouter_client.run_chat_completion(
        api_key,
        model=modele.openrouter_model_id,
        messages=messages,
        temperature=0.7 if donnees.run_number > 1 else 0.5,
        reasoning_effort=assign.reasoning_effort if assign else None,
        json_object=True,
    )
    latence = int((time.perf_counter() - debut) * 1000)

    choices = corps.get("choices")
    message = (
        choices[0].get("message", {})
        if isinstance(choices, list) and choices and isinstance(choices[0], dict)
        else {}
    )
    texte_brut = _extraire_texte_reponse(message if isinstance(message, dict) else {})
    parsed = _extraire_json_bloc(texte_brut)
    raw_by_net = parsed.get("proposals_by_network")
    if not isinstance(raw_by_net, dict):
        raw_by_net = parsed

    proposals_by_network: dict[str, list[PublicationTextProposalRead]] = {}
    for net in reseaux:
        items_net = raw_by_net.get(net) if isinstance(raw_by_net, dict) else None
        if not isinstance(items_net, list) or not items_net:
            # Repli propre si le modèle a utilisé la casse d'affichage (ex. "LinkedIn")
            if isinstance(raw_by_net, dict):
                for k, v in raw_by_net.items():
                    if isinstance(k, str) and k.strip().lower() == net and isinstance(v, list):
                        items_net = v
                        break
        liste_propre: list[PublicationTextProposalRead] = []
        if isinstance(items_net, list) and items_net:
            for idx, item in enumerate(items_net):
                if not isinstance(item, dict):
                    continue
                angle = str(item.get("angle") or (angles[idx] if idx < len(angles) else "Proposition")).strip()
                titre = str(item.get("title") or f"{angle} — {donnees.subject[:50]}").strip()
                raw_p = item.get("paragraphs")
                if isinstance(raw_p, list):
                    paragraphes = [str(p).strip() for p in raw_p if str(p).strip()]
                elif isinstance(item.get("text"), str) and item["text"].strip():
                    paragraphes = [p.strip() for p in item["text"].split("\n\n") if p.strip()]
                else:
                    paragraphes = []
                if not paragraphes:
                    continue
                raw_tags = item.get("hashtags") if isinstance(item.get("hashtags"), list) else []
                tags: list[str] = []
                if h_max > 0:
                    for t in raw_tags:
                        s = str(t).strip()
                        if not s:
                            continue
                        if not s.startswith("#"):
                            s = "#" + s.lstrip("#")
                        if s not in tags:
                            tags.append(s)
                liste_propre.append(
                    PublicationTextProposalRead(
                        id=f"r{donnees.run_number}-{net}-{idx + 1}-{uuid.uuid4().hex[:6]}",
                        network=net,
                        angle=angle,
                        run_number=donnees.run_number,
                        title=titre,
                        paragraphs=paragraphes,
                        hashtags=tags[: max(h_max, len(tags))] if h_max > 0 else [],
                        extra_hashtag_count=0,
                    )
                )

        if not liste_propre:
            # Secours si la réponse du modèle n'était pas structurée comme attendu
            fallback_text = texte_brut.strip() or f"Proposition pour {donnees.subject}"
            liste_propre.append(
                PublicationTextProposalRead(
                    id=f"r{donnees.run_number}-{net}-1-{uuid.uuid4().hex[:6]}",
                    network=net,
                    angle=angles[0],
                    run_number=donnees.run_number,
                    title=donnees.subject[:60],
                    paragraphs=[p.strip() for p in fallback_text.split("\n\n") if p.strip()] or [fallback_text],
                    hashtags=[],
                    extra_hashtag_count=0,
                )
            )
        proposals_by_network[net] = liste_propre

    usage = corps.get("usage") if isinstance(corps.get("usage"), dict) else {}
    prompt_tok = _to_int(usage.get("prompt_tokens"))
    comp_tok = _to_int(usage.get("completion_tokens"))
    total_tok = _to_int(usage.get("total_tokens")) or (prompt_tok + comp_tok)
    raw_cost = usage.get("cost")
    if isinstance(raw_cost, (int, float)):
        cost_usd = round(float(raw_cost), 7)
    else:
        cost_usd = round(
            prompt_tok * _to_float(modele.pricing_prompt)
            + comp_tok * _to_float(modele.pricing_completion),
            7,
        )

    return PublicationTextGenerationResponse(
        run_number=donnees.run_number,
        model_id=modele.openrouter_model_id,
        model_name=modele.name,
        reasoning_effort=assign.reasoning_effort if assign else None,  # type: ignore[arg-type]
        system_prompt_label=_prompt_label(sys_prompt),
        template_prompt_label=_prompt_label(tpl_prompt),
        key_source=key_source,  # type: ignore[arg-type]
        latency_ms=latence,
        total_tokens=total_tok,
        cost_usd=cost_usd,
        proposals_by_network=proposals_by_network,
    )


async def _stocker_image_publication(
    session: AsyncSession,
    stockage: Stockage | None,
    raw_src: str,
    display_name: str,
    par: User,
) -> tuple[str, str | None, int | None]:
    """Dépose l'image générée dans R2 sous `publications-generees/` et crée son entrée `Media`."""
    if stockage is None:
        return raw_src, None, None

    octets: bytes | None = None
    mime = "image/png"

    match = _DATA_URL_IMAGE_RE.match(raw_src.strip())
    if match:
        mime = match.group(1).lower()
        try:
            octets = base64.b64decode(match.group(2))
        except Exception:
            logger.warning("Décodage base64 impossible pour l'image générée.")
            return raw_src, None, None
    elif raw_src.startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                rep = await client.get(raw_src)
                if rep.status_code == 200 and rep.content:
                    octets = rep.content
                    ct = rep.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ct in _MIME_TO_EXT:
                        mime = ct
        except Exception:
            logger.warning("Téléchargement impossible pour l'image générée %s", raw_src[:120])
            return raw_src, None, None

    if not octets:
        return raw_src, None, None

    ext = _MIME_TO_EXT.get(mime, "png")
    maintenant = datetime.now(UTC)
    cle = f"publications-generees/{maintenant:%Y}/{maintenant:%m}/{uuid.uuid4().hex}.{ext}"

    try:
        await stockage.deposer(cle, io.BytesIO(octets), mime)
        url_pub = stockage.url_publique(cle)
    except Exception:
        logger.exception("Échec du dépôt R2 de l'image générée sous %s", cle)
        return raw_src, None, None

    media = Media(
        storage_key=cle,
        file_type=mime,
        source="generated",
        display_name=display_name[:255],
        size_bytes=len(octets),
        width=None,
        height=None,
        id_users_created_by=par.id_users,
    )
    session.add(media)
    await session.commit()
    await session.refresh(media)
    return url_pub, cle, media.id_media


async def generer_visuel_publication(
    session: AsyncSession,
    donnees: PublicationVisualGenerationRequest,
    par: User,
    stockage: Stockage | None = None,
) -> PublicationVisualGenerationResponse:
    """Génère ou retouche un visuel de publication via OpenRouter + stockage R2 + table Media."""
    key_row, key_source = await _get_active_generation_key(session)
    if key_row is None or key_source is None:
        raise ApiError(
            "openrouter_key_missing",
            "Aucune clé OpenRouter active n'est configurée. Rendez-vous dans Modèles IA v2.",
            400,
        )

    assign, modele = await _get_task_assignment_with_model(session, TASK_IMAGE_GENERATION)
    if modele is None:
        raise ApiError(
            "ai_model_not_assigned",
            "Aucun modèle IA n'est affecté à la tâche « Génération d'image ». Configurez-le dans Modèles IA v2.",
            400,
        )

    if donnees.mode == "retouch" and not (donnees.retouch_instruction or "").strip():
        raise ApiError(
            "validation_error",
            "Veuillez saisir une consigne de retouche.",
            422,
        )

    sys_prompt = await _get_default_prompt(session, PROMPT_KIND_SYSTEM, "image_generation")
    tpl_prompt = await _get_default_prompt(session, PROMPT_KIND_TEMPLATE, "image_generation")

    # Résoudre les médias de référence IAGORA (URLs R2 + descriptions)
    ref_urls: list[str] = []
    ref_notes: list[str] = []
    if donnees.reference_media_ids:
        lignes_ref = (
            await session.execute(
                select(MediaReference, Media, MediaReferenceNature)
                .join(Media, Media.id_media == MediaReference.id_media)
                .outerjoin(
                    MediaReferenceNature,
                    MediaReferenceNature.id_media_reference_natures
                    == MediaReference.id_media_reference_natures,
                )
                .where(
                    MediaReference.id_media_references.in_(donnees.reference_media_ids),
                    MediaReference.deleted_at.is_(None),
                    Media.deleted_at.is_(None),
                )
            )
        ).all()
        for ref, media, nature in lignes_ref:
            nature_lbl = nature.label if nature else "Référence"
            desc = f" — {ref.description}" if ref.description else ""
            ref_notes.append(f"- [{nature_lbl}] {ref.label}{desc}")
            if stockage is not None:
                url = stockage.url_publique(media.storage_key)
                if url and url not in ref_urls:
                    ref_urls.append(url)

    system_blocks: list[str] = [
        sys_prompt.content
        if sys_prompt is not None
        else (
            "Tu es directeur artistique pour DATUM Academy. Conçois des visuels professionnels, "
            "lisibles sur mobile, cohérents avec la charte graphique et les médias de référence fournis."
        ),
        f"Format cible : {donnees.format} (ratio {donnees.aspect_ratio}).",
    ]
    if ref_notes:
        system_blocks.append("Médias de référence à respecter :\n" + "\n".join(ref_notes))

    if donnees.mode == "retouch":
        user_text = (
            f"Retouche le visuel source fourni selon cette consigne précise : "
            f"{(donnees.retouch_instruction or '').strip()}\n"
            f"Sujet de la publication : {donnees.subject}\n"
            + (
                f"Direction artistique initiale : {donnees.visual_description}\n"
                if donnees.visual_description
                else ""
            )
            + f"Conserve la cohérence de la marque et le ratio {donnees.aspect_ratio}."
        )
    else:
        tpl_vars = {
            "ratio": donnees.aspect_ratio,
            "titre_evenement": donnees.subject,
            "sujet": donnees.subject,
            "style_visuel": donnees.visual_description or "moderne et professionnel",
            "format": donnees.format,
        }
        base_user = (
            _interpoler_gabarit(tpl_prompt.content, tpl_vars)
            if tpl_prompt is not None
            else f"Crée un visuel {donnees.aspect_ratio} pour la publication : {donnees.subject}."
        )
        parties_texte = [base_user, f"Sujet : {donnees.subject}"]
        if donnees.visual_description:
            parties_texte.append(f"Direction visuelle souhaitée : {donnees.visual_description}")
        if donnees.selected_caption:
            parties_texte.append(
                f"Légende retenue (pour cohérence du message) : {donnees.selected_caption[:500]}"
            )
        user_text = "\n\n".join(parties_texte)

    image_inputs: list[str] = []
    if donnees.mode == "retouch" and donnees.source_image_url and donnees.source_image_url.strip():
        image_inputs.append(donnees.source_image_url.strip())
    for u in ref_urls:
        if u not in image_inputs:
            image_inputs.append(u)

    if image_inputs:
        content_parts: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for img_url in image_inputs:
            content_parts.append({"type": "image_url", "image_url": {"url": img_url}})
        user_msg: dict[str, Any] = {"role": "user", "content": content_parts}
    else:
        user_msg = {"role": "user", "content": user_text}

    messages = [
        {"role": "system", "content": "\n\n".join(system_blocks)},
        user_msg,
    ]

    api_key = decrypt_token(key_row.api_key_encrypted)
    debut = time.perf_counter()
    corps = await openrouter_client.run_chat_completion(
        api_key,
        model=modele.openrouter_model_id,
        messages=messages,
        temperature=0.6,
        reasoning_effort=assign.reasoning_effort if assign else None,
        request_image_output=True,
        image_aspect_ratio=donnees.aspect_ratio,
    )
    latence = int((time.perf_counter() - debut) * 1000)

    choices = corps.get("choices")
    message = (
        choices[0].get("message", {})
        if isinstance(choices, list) and choices and isinstance(choices[0], dict)
        else {}
    )
    if not isinstance(message, dict):
        message = {}

    raw_images = _extraire_images_reponse(message)
    if not raw_images:
        raise ApiError(
            "image_generation_empty",
            f"Le modèle {modele.openrouter_model_id} n'a retourné aucune image. "
            "Vérifiez qu'un modèle compatible génération d'image est affecté dans Modèles IA v2.",
            502,
        )

    prefix_nom = "Retouche" if donnees.mode == "retouch" else "Visuel"
    display_name = f"{prefix_nom} IA — {donnees.subject[:80]}"
    image_url, storage_key, id_media = await _stocker_image_publication(
        session, stockage, raw_images[0], display_name, par
    )

    texte_assistant = _extraire_texte_reponse(message).strip()
    if not texte_assistant:
        texte_assistant = (
            f"Nouvelle version retouchée selon votre consigne : « {(donnees.retouch_instruction or '').strip()} »."
            if donnees.mode == "retouch"
            else f"Visuel généré avec {modele.name} ({donnees.aspect_ratio})."
        )

    usage = corps.get("usage") if isinstance(corps.get("usage"), dict) else {}
    raw_cost = usage.get("cost")
    if isinstance(raw_cost, (int, float)):
        cost_usd = round(float(raw_cost), 7)
    else:
        prompt_tok = _to_int(usage.get("prompt_tokens"))
        comp_tok = _to_int(usage.get("completion_tokens"))
        cost_usd = round(
            prompt_tok * _to_float(modele.pricing_prompt)
            + comp_tok * _to_float(modele.pricing_completion),
            7,
        )

    return PublicationVisualGenerationResponse(
        image_url=image_url,
        storage_key=storage_key,
        id_media=id_media,
        assistant_message=texte_assistant,
        model_id=modele.openrouter_model_id,
        model_name=modele.name,
        reasoning_effort=assign.reasoning_effort if assign else None,  # type: ignore[arg-type]
        system_prompt_label=_prompt_label(sys_prompt),
        template_prompt_label=_prompt_label(tpl_prompt),
        key_source=key_source,  # type: ignore[arg-type]
        latency_ms=latence,
        cost_usd=cost_usd,
    )
