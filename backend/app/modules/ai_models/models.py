"""Tables du module Modèles IA (OpenRouter).

Quatre tables :
- `openrouter_api_keys` : clés API Management et Standard chiffrées par Fernet
  (même mécanisme et même historique de remplacement que `social_account_tokens`).
- `ai_workspaces` : workspaces OpenRouter synchronisés et workspace actif IAGORA.
- `ai_models` : catalogue des modèles OpenRouter synchronisés et activés.
- `ai_task_assignments` : affectation du modèle actif par tâche métier IAGORA.

Les contraintes, index et commentaires sont déclarés ici À L'IDENTIQUE de la
migration 0005 : `alembic check` échoue sur le moindre écart.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ai_models.constants import (
    KEY_KINDS,
    PROMPT_KINDS,
    PROMPT_TASK_CODES,
    PROVIDER_SORTS,
    REASONING_EFFORTS,
    SANDBOX_USE_CASES,
    TASK_CODES,
)


class OpenRouterApiKey(Base):
    """Une délivrance de clé OpenRouter (management ou standard), chiffrée par Fernet."""

    __tablename__ = "openrouter_api_keys"
    __table_args__ = (
        CheckConstraint(
            "key_kind IN ('" + "', '".join(KEY_KINDS) + "')",
            name="key_kind",
        ),
        Index(
            "uq_openrouter_api_keys_actif",
            "key_kind",
            unique=True,
            postgresql_where=text("superseded_at IS NULL AND revoked_at IS NULL"),
        ),
        {
            "comment": (
                "Cles API OpenRouter (management et standard) chiffrees par Fernet, "
                "sur le meme modele que social_account_tokens. Un renouvellement "
                "cree une nouvelle ligne et marque la precedente remplacee."
            )
        },
    )

    id_openrouter_api_keys: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_kind: Mapped[str] = mapped_column(
        String(20),
        comment="management (workspaces, credits, cles) | standard (inference, catalogue).",
    )
    label: Mapped[str | None] = mapped_column(String(120))
    api_key_encrypted: Mapped[str] = mapped_column(
        Text,
        comment="Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). La cle en clair ne touche jamais le disque.",
    )
    key_masked: Mapped[str] = mapped_column(
        String(40),
        comment="Apercu masque sans secret (ex: sk-or-v1-...abcd) pour l'affichage.",
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verify_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_verify_message: Mapped[str | None] = mapped_column(Text)
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Remplacement par une cle plus recente du meme type."
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_openrouter_api_keys_id_users_created_by_users")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiWorkspace(Base):
    """Workspace OpenRouter synchronisé et piloté depuis IAGORA."""

    __tablename__ = "ai_workspaces"
    __table_args__ = (
        Index(
            "uq_ai_workspaces_externe_actif",
            "openrouter_workspace_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "default_provider_sort IS NULL OR default_provider_sort IN ('"
            + "', '".join(PROVIDER_SORTS)
            + "')",
            name="default_provider_sort",
        ),
        {
            "comment": (
                "Workspaces OpenRouter geres via la Management API. "
                "deleted_at archive le workspace localement apres suppression."
            )
        },
    )

    id_ai_workspaces: Mapped[int] = mapped_column(Integer, primary_key=True)
    openrouter_workspace_id: Mapped[str] = mapped_column(
        String(120), comment="Identifiant du workspace chez OpenRouter."
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    default_text_model: Mapped[str | None] = mapped_column(String(180))
    default_image_model: Mapped[str | None] = mapped_column(String(180))
    default_provider_sort: Mapped[str | None] = mapped_column(String(30))
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="Workspace selectionne par defaut pour les operations IAGORA.",
    )
    raw_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_workspaces_id_users_created_by_users")
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_workspaces_id_users_changed_by_users")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiModel(Base):
    """Modèle IA synchronisé depuis le catalogue OpenRouter."""

    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("openrouter_model_id", name="uq_ai_models_openrouter_model_id"),
        {
            "comment": (
                "Catalogue des modeles OpenRouter synchronises dans IAGORA. "
                "is_enabled determine si le modele est propose aux equipes."
            )
        },
    )

    id_ai_models: Mapped[int] = mapped_column(Integer, primary_key=True)
    openrouter_model_id: Mapped[str] = mapped_column(
        String(180), comment="Identifiant canonique OpenRouter (ex: anthropic/claude-3.5-sonnet)."
    )
    name: Mapped[str] = mapped_column(String(200))
    provider_slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    context_length: Mapped[int | None] = mapped_column(Integer)
    pricing_prompt: Mapped[str | None] = mapped_column(String(40))
    pricing_completion: Mapped[str | None] = mapped_column(String(40))
    input_modalities_json: Mapped[list[str] | None] = mapped_column(JSONB)
    output_modalities_json: Mapped[list[str] | None] = mapped_column(JSONB)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    raw_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiTaskAssignment(Base):
    """Affectation du modèle IA actif par spécialité métier IAGORA."""

    __tablename__ = "ai_task_assignments"
    __table_args__ = (
        UniqueConstraint("task_code", name="uq_ai_task_assignments_task_code"),
        CheckConstraint(
            "task_code IN ('" + "', '".join(TASK_CODES) + "')",
            name="task_code",
        ),
        CheckConstraint(
            "reasoning_effort IS NULL OR reasoning_effort IN ('"
            + "', '".join(REASONING_EFFORTS)
            + "')",
            name="reasoning_effort",
        ),
        {
            "comment": (
                "Affectation du modele OpenRouter actif pour chaque tache metier "
                "(text-generation, image-description, image-generation, rag-embedding)."
            )
        },
    )

    id_ai_task_assignments: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_code: Mapped[str] = mapped_column(String(40))
    id_ai_models: Mapped[int | None] = mapped_column(
        ForeignKey("ai_models.id_ai_models", name="fk_ai_task_assignments_id_ai_models")
    )
    id_ai_workspaces: Mapped[int | None] = mapped_column(
        ForeignKey("ai_workspaces.id_ai_workspaces", name="fk_ai_task_assignments_id_ai_workspaces")
    )
    reasoning_effort: Mapped[str | None] = mapped_column(
        String(20),
        comment=(
            "Effort de raisonnement OpenRouter (none, minimal, low, medium, high, xhigh). "
            "Nul = comportement par defaut du modele."
        ),
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_task_assignments_id_users_changed_by_users")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiSandboxRun(Base):
    """Historique d'une exécution du Bac à sable IA."""

    __tablename__ = "ai_sandbox_runs"
    __table_args__ = (
        CheckConstraint(
            "use_case IN ('" + "', '".join(SANDBOX_USE_CASES) + "')",
            name="use_case",
        ),
        Index("ix_ai_sandbox_runs_created_at", text("created_at DESC")),
        {
            "comment": (
                "Historique des runs de comparaison multi-modeles executes dans le "
                "Bac a sable IA (/bac-a-sable-ia)."
            )
        },
    )

    id_ai_sandbox_runs: Mapped[int] = mapped_column(Integer, primary_key=True)
    use_case: Mapped[str] = mapped_column(String(40))
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)
    tone: Mapped[str | None] = mapped_column(String(160))
    json_output_enabled: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    json_output_schema: Mapped[str | None] = mapped_column(Text)
    knowledge_context: Mapped[str | None] = mapped_column(Text)
    image_mode: Mapped[str | None] = mapped_column(String(20))
    image_aspect_ratio: Mapped[str | None] = mapped_column(String(20))
    key_source: Mapped[str] = mapped_column(String(20))
    key_masked: Mapped[str] = mapped_column(String(40))
    total_batch_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 7), server_default=text("0")
    )
    variants_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    results_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_sandbox_runs_id_users_created_by_users")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiPrompt(Base):
    """Prompt système ou gabarit (template) versionné par tâche métier IA."""

    __tablename__ = "ai_prompts"
    __table_args__ = (
        CheckConstraint(
            "prompt_kind IN ('" + "', '".join(PROMPT_KINDS) + "')",
            name="prompt_kind",
        ),
        CheckConstraint(
            "task_code IN ('" + "', '".join(PROMPT_TASK_CODES) + "')",
            name="task_code",
        ),
        CheckConstraint("version_number >= 1", name="version_positive"),
        UniqueConstraint(
            "prompt_kind",
            "task_code",
            "version_number",
            name="uq_ai_prompts_kind_task_version",
        ),
        Index(
            "uq_ai_prompts_defaut_actif",
            "prompt_kind",
            "task_code",
            unique=True,
            postgresql_where=text("is_default IS TRUE AND deleted_at IS NULL"),
        ),
        Index("ix_ai_prompts_kind_task", "prompt_kind", "task_code"),
        {
            "comment": (
                "Prompts systeme et gabarits (templates) versionnes par tache metier IA. "
                "Au plus un gabarit actif par defaut par couple (prompt_kind, task_code)."
            )
        },
    )

    id_ai_prompts: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_kind: Mapped[str] = mapped_column(
        String(20),
        comment="system (prompt systeme) | template (gabarit reutilisable).",
    )
    task_code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(160))
    version_number: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    content: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(300))
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_prompts_id_users_created_by_users")
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_ai_prompts_id_users_changed_by_users")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
