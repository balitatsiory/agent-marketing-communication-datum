"""Module 06 Modèles IA — OpenRouter (clés chiffrées, workspaces, modèles et affectations).

Quatre tables :
- `openrouter_api_keys` : clés API Management et Standard chiffrées par Fernet ;
- `ai_workspaces` : workspaces OpenRouter ;
- `ai_models` : catalogue des modèles OpenRouter ;
- `ai_task_assignments` : affectation par tâche métier.

Insère également le droit `manage_ai_models` (module 06, sort_order 600).

Révision : 0005
Révision précédente : 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY_KINDS = ("management", "standard")
PROVIDER_SORTS = ("price", "throughput", "latency", "exacto")
TASK_CODES = ("text-generation", "image-description", "image-generation", "rag-embedding")


def upgrade() -> None:
    op.create_table(
        "openrouter_api_keys",
        sa.Column("id_openrouter_api_keys", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column(
            "key_kind",
            sa.String(20),
            nullable=False,
            comment="management (workspaces, credits, cles) | standard (inference, catalogue).",
        ),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column(
            "api_key_encrypted",
            sa.Text,
            nullable=False,
            comment="Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). La cle en clair ne touche jamais le disque.",
        ),
        sa.Column(
            "key_masked",
            sa.String(40),
            nullable=False,
            comment="Apercu masque sans secret (ex: sk-or-v1-...abcd) pour l'affichage.",
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verify_ok", sa.Boolean, nullable=True),
        sa.Column("last_verify_message", sa.Text, nullable=True),
        sa.Column(
            "obtained_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "superseded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Remplacement par une cle plus recente du meme type.",
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_openrouter_api_keys", name="pk_openrouter_api_keys"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_openrouter_api_keys_id_users_created_by_users",
        ),
        sa.CheckConstraint(
            "key_kind IN ('" + "', '".join(KEY_KINDS) + "')",
            name="key_kind",
        ),
        comment=(
            "Cles API OpenRouter (management et standard) chiffrees par Fernet, "
            "sur le meme modele que social_account_tokens. Un renouvellement "
            "cree une nouvelle ligne et marque la precedente remplacee."
        ),
    )
    op.create_index(
        "uq_openrouter_api_keys_actif",
        "openrouter_api_keys",
        ["key_kind"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "ai_workspaces",
        sa.Column("id_ai_workspaces", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column(
            "openrouter_workspace_id",
            sa.String(120),
            nullable=False,
            comment="Identifiant du workspace chez OpenRouter.",
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(160), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_text_model", sa.String(180), nullable=True),
        sa.Column("default_image_model", sa.String(180), nullable=True),
        sa.Column("default_provider_sort", sa.String(30), nullable=True),
        sa.Column("monthly_budget_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "is_selected",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
            comment="Workspace selectionne par defaut pour les operations IAGORA.",
        ),
        sa.Column("raw_metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_changed_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_ai_workspaces", name="pk_ai_workspaces"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_ai_workspaces_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_ai_workspaces_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "default_provider_sort IS NULL OR default_provider_sort IN ('"
            + "', '".join(PROVIDER_SORTS)
            + "')",
            name="default_provider_sort",
        ),
        comment=(
            "Workspaces OpenRouter geres via la Management API. "
            "deleted_at archive le workspace localement apres suppression."
        ),
    )
    op.create_index(
        "uq_ai_workspaces_externe_actif",
        "ai_workspaces",
        ["openrouter_workspace_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "ai_models",
        sa.Column("id_ai_models", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column(
            "openrouter_model_id",
            sa.String(180),
            nullable=False,
            comment="Identifiant canonique OpenRouter (ex: anthropic/claude-3.5-sonnet).",
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider_slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("context_length", sa.Integer, nullable=True),
        sa.Column("pricing_prompt", sa.String(40), nullable=True),
        sa.Column("pricing_completion", sa.String(40), nullable=True),
        sa.Column("input_modalities_json", postgresql.JSONB, nullable=True),
        sa.Column("output_modalities_json", postgresql.JSONB, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("raw_metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_ai_models", name="pk_ai_models"),
        sa.UniqueConstraint("openrouter_model_id", name="uq_ai_models_openrouter_model_id"),
        comment=(
            "Catalogue des modeles OpenRouter synchronises dans IAGORA. "
            "is_enabled determine si le modele est propose aux equipes."
        ),
    )

    op.create_table(
        "ai_task_assignments",
        sa.Column("id_ai_task_assignments", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("task_code", sa.String(40), nullable=False),
        sa.Column("id_ai_models", sa.Integer, nullable=True),
        sa.Column("id_ai_workspaces", sa.Integer, nullable=True),
        sa.Column("id_users_changed_by", sa.Integer, nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_ai_task_assignments", name="pk_ai_task_assignments"),
        sa.UniqueConstraint("task_code", name="uq_ai_task_assignments_task_code"),
        sa.ForeignKeyConstraint(
            ["id_ai_models"],
            ["ai_models.id_ai_models"],
            name="fk_ai_task_assignments_id_ai_models",
        ),
        sa.ForeignKeyConstraint(
            ["id_ai_workspaces"],
            ["ai_workspaces.id_ai_workspaces"],
            name="fk_ai_task_assignments_id_ai_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_ai_task_assignments_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "task_code IN ('" + "', '".join(TASK_CODES) + "')",
            name="task_code",
        ),
        comment=(
            "Affectation du modele OpenRouter actif pour chaque tache metier "
            "(text-generation, image-description, image-generation, rag-embedding)."
        ),
    )

    for table in ("ai_workspaces", "ai_models", "ai_task_assignments"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    op.execute(
        """
        INSERT INTO permissions (code, label, description, sort_order)
        VALUES (
            'manage_ai_models',
            'Gerer les modeles IA',
            'Configurer les cles OpenRouter chiffrees, gerer les workspaces et affecter les modeles IA.',
            600
        )
        ON CONFLICT (code) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO ai_task_assignments (task_code)
        VALUES
            ('text-generation'),
            ('image-description'),
            ('image-generation'),
            ('rag-embedding')
        ON CONFLICT (task_code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM user_permissions "
        "WHERE id_permissions IN (SELECT id_permissions FROM permissions WHERE code = 'manage_ai_models')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'manage_ai_models'")
    for table in ("ai_task_assignments", "ai_models", "ai_workspaces"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.drop_table("ai_task_assignments")
    op.drop_table("ai_models")
    op.drop_index("uq_ai_workspaces_externe_actif", table_name="ai_workspaces")
    op.drop_table("ai_workspaces")
    op.drop_index("uq_openrouter_api_keys_actif", table_name="openrouter_api_keys")
    op.drop_table("openrouter_api_keys")
