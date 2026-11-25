"""Schémas Pydantic du module Modèles IA (OpenRouter)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KeyKind = Literal["management", "standard"]
ProviderSort = Literal["price", "throughput", "latency", "exacto"]
TaskCode = Literal[
    "text-generation",
    "image-description",
    "image-generation",
    "rag-embedding",
]


# ---------------------------------------------------------------------------
# Clés API OpenRouter (chiffrées par Fernet en base, jamais renvoyées en clair)
# ---------------------------------------------------------------------------


class OpenRouterKeySave(BaseModel):
    """Enregistrement ou rotation d'une clé OpenRouter (Management ou Standard)."""

    key_kind: KeyKind
    api_key: str = Field(..., min_length=8, max_length=512)
    label: str | None = Field(default=None, max_length=120)
    verify_immediately: bool = True


class OpenRouterKeyRead(BaseModel):
    """Représentation sûre d'une clé stockée (sans jamais exposer la clé en clair)."""

    model_config = ConfigDict(from_attributes=True)

    id_openrouter_api_keys: int
    key_kind: KeyKind
    label: str | None
    key_masked: str
    is_active: bool
    last_verified_at: datetime | None
    last_verify_ok: bool | None
    last_verify_message: str | None
    obtained_at: datetime
    superseded_at: datetime | None
    revoked_at: datetime | None
    created_by_name: str | None = None
    created_at: datetime


class OpenRouterKeyVerifyRead(BaseModel):
    """Résultat d'une vérification en direct auprès d'OpenRouter."""

    verified: bool
    message: str
    key: OpenRouterKeyRead
    total_credits: float | None = None
    total_usage: float | None = None
    remaining_credits: float | None = None
    key_label: str | None = None
    limit_remaining: float | None = None
    is_free_tier: bool | None = None


class OpenRouterCreditsRead(BaseModel):
    """Solde des crédits OpenRouter (lu via Management API Key)."""

    available: bool
    total_credits: float | None = None
    total_usage: float | None = None
    remaining_credits: float | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Workspaces OpenRouter
# ---------------------------------------------------------------------------


class AiWorkspaceCreate(BaseModel):
    """Création d'un workspace OpenRouter via Management API."""

    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    default_text_model: str | None = Field(default=None, max_length=180)
    default_image_model: str | None = Field(default=None, max_length=180)
    default_provider_sort: ProviderSort | None = None
    monthly_budget_usd: Decimal | None = Field(default=None, ge=0)


class AiWorkspaceUpdate(BaseModel):
    """Modification d'un workspace (métadonnées OpenRouter et/ou sélection locale)."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    default_text_model: str | None = Field(default=None, max_length=180)
    default_image_model: str | None = Field(default=None, max_length=180)
    default_provider_sort: ProviderSort | None = None
    monthly_budget_usd: Decimal | None = Field(default=None, ge=0)
    is_selected: bool | None = None


class AiWorkspaceRead(BaseModel):
    """Fiche d'un workspace OpenRouter."""

    model_config = ConfigDict(from_attributes=True)

    id_ai_workspaces: int
    openrouter_workspace_id: str
    name: str
    slug: str | None
    description: str | None
    default_text_model: str | None
    default_image_model: str | None
    default_provider_sort: str | None
    monthly_budget_usd: float | None
    is_default: bool
    is_selected: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AiWorkspaceSyncRead(BaseModel):
    """Résultat d'une synchronisation des workspaces depuis OpenRouter."""

    synced_count: int
    message: str
    workspaces: list[AiWorkspaceRead]


# ---------------------------------------------------------------------------
# Modèles IA & Affectations
# ---------------------------------------------------------------------------


class AiModelRead(BaseModel):
    """Modèle OpenRouter du catalogue local."""

    model_config = ConfigDict(from_attributes=True)

    id_ai_models: int
    openrouter_model_id: str
    name: str
    provider_slug: str
    description: str | None
    context_length: int | None
    pricing_prompt: str | None
    pricing_completion: str | None
    input_modalities: list[str]
    output_modalities: list[str]
    is_enabled: bool
    last_synced_at: datetime | None


class AiModelToggle(BaseModel):
    """Activation ou désactivation d'un modèle pour IAGORA."""

    is_enabled: bool


class AiModelsSyncRead(BaseModel):
    """Résultat de la synchronisation du catalogue OpenRouter."""

    synced_count: int
    enabled_count: int
    message: str


class AiTaskAssignmentUpdate(BaseModel):
    """Affectation d'un modèle (et optionnellement d'un workspace) à une tâche métier."""

    id_ai_models: int | None = None
    id_ai_workspaces: int | None = None


class AiTaskAssignmentRead(BaseModel):
    """Affectation active d'une tâche métier IAGORA."""

    task_code: str
    task_label: str
    id_ai_models: int | None
    model_name: str | None = None
    openrouter_model_id: str | None = None
    id_ai_workspaces: int | None
    workspace_name: str | None = None
    updated_at: datetime


class OpenRouterOverviewRead(BaseModel):
    """Synthèse globale pour le bandeau de /modeles-ia_v2."""

    management_key: OpenRouterKeyRead | None
    standard_key: OpenRouterKeyRead | None
    credits: OpenRouterCreditsRead
    workspaces_count: int
    selected_workspace_name: str | None
    models_total_count: int
    models_enabled_count: int


# ---------------------------------------------------------------------------
# Tableau de bord FinOps & Observabilité OpenRouter
# ---------------------------------------------------------------------------


class OpenRouterActivityItemRead(BaseModel):
    """Une entrée d'activité retournée par `GET /api/v1/activity`."""

    date: str
    model: str
    provider_name: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None
    usage_usd: float = 0.0
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0


class OpenRouterWorkspaceCostRead(BaseModel):
    """Agrégation des dépenses et volumes par workspace OpenRouter."""

    workspace_id: str
    workspace_name: str
    cost_usd: float
    requests: int
    tokens: int


class OpenRouterDailyPointRead(BaseModel):
    """Point agrégé par date pour le graphique d'évolution quotidienne."""

    date: str
    cost_usd: float
    tokens: int
    requests: int


class OpenRouterModelCostRead(BaseModel):
    """Agrégation par modèle pour les graphiques de répartition."""

    model: str
    cost_usd: float
    requests: int
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int


class OpenRouterRemoteKeyRead(BaseModel):
    """Clé API distante retournée par `GET /api/v1/keys` (jamais de secret)."""

    hash: str
    label: str
    limit: float | None = None
    limit_remaining: float | None = None
    usage: float = 0.0
    usage_daily: float | None = None
    usage_weekly: float | None = None
    usage_monthly: float | None = None
    disabled: bool = False
    expires_at: str | None = None
    created_at: str | None = None


class OpenRouterDashboardRead(BaseModel):
    """Données agrégées du tableau de bord FinOps OpenRouter."""

    scope_workspace_id: str | None = None
    scope_label: str = "Tous les workspaces (cumulé)"
    credits: OpenRouterCreditsRead
    total_cost_usd: float
    total_requests: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_reasoning_tokens: int
    avg_cost_per_request_usd: float
    active_remote_keys_count: int
    total_remote_keys_count: int
    daily_series: list[OpenRouterDailyPointRead]
    by_model: list[OpenRouterModelCostRead]
    by_workspace: list[OpenRouterWorkspaceCostRead]
    activity: list[OpenRouterActivityItemRead]
    remote_keys: list[OpenRouterRemoteKeyRead]
    warnings: list[str]
