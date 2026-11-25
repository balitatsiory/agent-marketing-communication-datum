"""Schémas Pydantic du module Modèles IA (OpenRouter)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KeyKind = Literal["management", "standard", "sandbox"]
ProviderSort = Literal["price", "throughput", "latency", "exacto"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
SandboxUseCase = Literal["publication_text", "image_generation", "message_rag"]
PromptKind = Literal["system", "template"]
PromptTaskCode = Literal[
    "publication_description",
    "message_reply",
    "image_generation",
    "image_description",
    "rag_synthesis",
    "newsletter_content",
]
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
    """Affectation d'un modèle, d'un effort de raisonnement (et d'un workspace) à une tâche métier."""

    id_ai_models: int | None = None
    id_ai_workspaces: int | None = None
    reasoning_effort: ReasoningEffort | None = None


class AiTaskAssignmentRead(BaseModel):
    """Affectation active d'une tâche métier IAGORA."""

    task_code: str
    task_label: str
    id_ai_models: int | None
    model_name: str | None = None
    openrouter_model_id: str | None = None
    id_ai_workspaces: int | None
    workspace_name: str | None = None
    reasoning_effort: ReasoningEffort | None = None
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


# ---------------------------------------------------------------------------
# Bac à sable IA (comparateur multi-modèles côte à côte)
# ---------------------------------------------------------------------------


class SandboxVariantInput(BaseModel):
    """Configuration d'une colonne de test dans le Bac à sable IA."""

    slot_id: str = Field(..., min_length=1, max_length=20)
    model_id: str = Field(..., min_length=2, max_length=180)
    reasoning_effort: ReasoningEffort | None = None
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)


class SandboxCompareRequest(BaseModel):
    """Requête d'exécution parallèle sur 2 à 4 modèles dans le Bac à sable IA."""

    use_case: SandboxUseCase
    system_prompt: str = Field(..., min_length=1, max_length=12000)
    user_prompt: str = Field(..., min_length=1, max_length=12000)
    tone: str | None = Field(default=None, max_length=160)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    json_output_enabled: bool = False
    json_output_schema: str | None = Field(default=None, max_length=6000)
    knowledge_context: str | None = Field(default=None, max_length=20000)
    image_mode: Literal["create", "edit"] = "create"
    image_aspect_ratio: str | None = Field(default=None, max_length=20)
    reference_image_url: str | None = Field(default=None, max_length=10_000_000)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=8)
    reference_media_notes: list[str] = Field(default_factory=list, max_length=8)
    variants: list[SandboxVariantInput] = Field(..., min_length=1, max_length=4)


class SandboxVariantResult(BaseModel):
    """Résultat détaillé d'une variante exécutée sur OpenRouter."""

    slot_id: str
    model_id: str
    reasoning_effort: ReasoningEffort | None = None
    temperature: float
    ok: bool
    error: str | None = None
    text: str = ""
    images: list[str] = Field(default_factory=list)
    stored_image_keys: list[str] = Field(default_factory=list)
    reasoning_trace: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    visible_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    projected_monthly_5k_usd: float = 0.0
    latency_ms: int = 0
    raw_usage_json: dict[str, object] | None = None
    raw_response_json: dict[str, object] | None = None


class SandboxCompareResponse(BaseModel):
    """Réponse agrégée d'une exécution du Bac à sable IA."""

    id_ai_sandbox_runs: int | None = None
    use_case: SandboxUseCase
    key_source: Literal["sandbox", "standard"]
    key_masked: str
    total_batch_cost_usd: float
    results: list[SandboxVariantResult]
    created_at: datetime | None = None


class SandboxRunHistoryRead(BaseModel):
    """Une entrée enregistrée dans l'historique du Bac à sable IA."""

    id_ai_sandbox_runs: int
    use_case: SandboxUseCase
    system_prompt: str
    user_prompt: str
    tone: str | None
    json_output_enabled: bool
    json_output_schema: str | None
    knowledge_context: str | None
    image_mode: str | None
    image_aspect_ratio: str | None
    key_source: Literal["sandbox", "standard"]
    key_masked: str
    total_batch_cost_usd: float
    variants: list[SandboxVariantInput]
    results: list[SandboxVariantResult]
    created_by_name: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Prompts système & Prompt templates (versionnés par tâche)
# ---------------------------------------------------------------------------


class AiPromptTaskRead(BaseModel):
    """Tâche métier affichée dans l'aside des écrans Prompts."""

    code: PromptTaskCode
    label: str
    description: str
    count: int = 0
    has_default: bool = False


class AiPromptCreate(BaseModel):
    """Création d'un prompt système ou d'un gabarit (nouvelle version auto-incrémentée)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt_kind: PromptKind
    task_code: PromptTaskCode
    title: str = Field(..., min_length=2, max_length=160)
    content: str = Field(..., min_length=1, max_length=30000)
    description: str | None = Field(default=None, max_length=300)
    is_default: bool = False


class AiPromptUpdate(BaseModel):
    """Modification d'un prompt existant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=2, max_length=160)
    content: str | None = Field(default=None, min_length=1, max_length=30000)
    description: str | None = Field(default=None, max_length=300)


class AiPromptRead(BaseModel):
    """Fiche complète d'un prompt système ou gabarit."""

    id_ai_prompts: int
    prompt_kind: PromptKind
    task_code: PromptTaskCode
    title: str
    version_number: int
    content: str
    char_count: int
    description: str | None
    is_default: bool
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
