"""Ajout de la table `ai_sandbox_runs` pour l'historique du Bac à sable IA.

Stocke chaque exécution de comparaison multi-modèles (prompts, cas d'utilisation,
variantes, résultats et coût réel) afin de pouvoir consulter et rejouer
l'historique depuis `/bac-a-sable-ia`.

Révision : 0008
Révision précédente : 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SANDBOX_USE_CASES = ("publication_text", "image_generation", "message_rag")


def upgrade() -> None:
    op.create_table(
        "ai_sandbox_runs",
        sa.Column("id_ai_sandbox_runs", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("use_case", sa.String(40), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt", sa.Text, nullable=False),
        sa.Column("tone", sa.String(160), nullable=True),
        sa.Column("json_output_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("json_output_schema", sa.Text, nullable=True),
        sa.Column("knowledge_context", sa.Text, nullable=True),
        sa.Column("image_mode", sa.String(20), nullable=True),
        sa.Column("image_aspect_ratio", sa.String(20), nullable=True),
        sa.Column("key_source", sa.String(20), nullable=False),
        sa.Column("key_masked", sa.String(40), nullable=False),
        sa.Column(
            "total_batch_cost_usd",
            sa.Numeric(12, 7),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("variants_json", postgresql.JSONB, nullable=False),
        sa.Column("results_json", postgresql.JSONB, nullable=False),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_ai_sandbox_runs", name="pk_ai_sandbox_runs"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_ai_sandbox_runs_id_users_created_by_users",
        ),
        sa.CheckConstraint(
            "use_case IN ('" + "', '".join(SANDBOX_USE_CASES) + "')",
            name="ck_ai_sandbox_runs_use_case",
        ),
        comment=(
            "Historique des runs de comparaison multi-modeles executes dans le "
            "Bac a sable IA (/bac-a-sable-ia)."
        ),
    )
    op.create_index(
        "ix_ai_sandbox_runs_created_at",
        "ai_sandbox_runs",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_sandbox_runs_created_at", table_name="ai_sandbox_runs")
    op.drop_table("ai_sandbox_runs")
