"""Comptes de réseaux sociaux et leurs statistiques.

Crée platforms, social_account_statuses, social_accounts et social_account_metrics.

Revision ID: 0003_reseaux
Revises: 0002_droits
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_reseaux"
down_revision: str | None = "0002_droits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platforms",
        sa.Column("id_platforms", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("api_base_url", sa.String(length=255), nullable=True),
        sa.Column("api_version", sa.String(length=10), nullable=True),
        sa.Column("max_caption_length", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id_platforms", name=op.f("pk_platforms")),
        sa.UniqueConstraint("code", name=op.f("uq_platforms_code")),
    )

    op.create_table(
        "social_account_statuses",
        sa.Column(
            "id_social_account_statuses",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint(
            "id_social_account_statuses", name=op.f("pk_social_account_statuses")
        ),
        sa.UniqueConstraint("code", name=op.f("uq_social_account_statuses_code")),
    )

    op.create_table(
        "social_accounts",
        sa.Column("id_social_accounts", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("id_platforms", sa.BigInteger(), nullable=False),
        sa.Column("id_social_account_statuses", sa.BigInteger(), nullable=False),
        sa.Column("id_social_accounts_parent", sa.BigInteger(), nullable=True),
        sa.Column("external_meta_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("handle", sa.String(length=100), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_kind", sa.String(length=20), nullable=False, server_default="page"),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_social_accounts", name=op.f("pk_social_accounts")),
        sa.ForeignKeyConstraint(
            ["id_platforms"],
            ["platforms.id_platforms"],
            name=op.f("fk_social_accounts_id_platforms_platforms"),
        ),
        # Nom raccourci à la main : la convention dépasserait les 63 caractères
        # admis par PostgreSQL.
        sa.ForeignKeyConstraint(
            ["id_social_account_statuses"],
            ["social_account_statuses.id_social_account_statuses"],
            name="fk_social_accounts_status",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_accounts_parent"],
            ["social_accounts.id_social_accounts"],
            name=op.f("fk_social_accounts_id_social_accounts_parent_social_accounts"),
        ),
        # Un compte ne peut être raccordé deux fois sur le même réseau.
        sa.UniqueConstraint(
            "id_platforms", "external_meta_id", name=op.f("uq_social_accounts_id_platforms")
        ),
    )
    op.create_index(
        op.f("ix_social_accounts_id_social_account_statuses"),
        "social_accounts",
        ["id_social_account_statuses"],
    )

    op.create_table(
        "social_account_metrics",
        sa.Column(
            "id_social_account_metrics", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("id_social_accounts", sa.BigInteger(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        # Toutes nullables : Meta renvoie un ensemble vide, pas un zéro.
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("profile_views", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("interactions", sa.Integer(), nullable=True),
        sa.Column("posts_count", sa.Integer(), nullable=True),
        sa.Column(
            "collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint(
            "id_social_account_metrics", name=op.f("pk_social_account_metrics")
        ),
        sa.ForeignKeyConstraint(
            ["id_social_accounts"],
            ["social_accounts.id_social_accounts"],
            name=op.f("fk_social_account_metrics_id_social_accounts_social_accounts"),
            ondelete="CASCADE",
        ),
        # Une seule ligne par compte et par jour : une nouvelle collecte met à jour.
        sa.UniqueConstraint(
            "id_social_accounts",
            "metric_date",
            name=op.f("uq_social_account_metrics_id_social_accounts"),
        ),
    )
    op.create_index(
        op.f("ix_social_account_metrics_id_social_accounts"),
        "social_account_metrics",
        ["id_social_accounts"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_social_account_metrics_id_social_accounts"), table_name="social_account_metrics"
    )
    op.drop_table("social_account_metrics")
    op.drop_index(
        op.f("ix_social_accounts_id_social_account_statuses"), table_name="social_accounts"
    )
    op.drop_table("social_accounts")
    op.drop_table("social_account_statuses")
    op.drop_table("platforms")
