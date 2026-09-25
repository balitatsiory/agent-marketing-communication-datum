"""Socle : utilisateurs, droits et sessions.

Crée users, permissions, user_permissions et refresh_tokens.

Revision ID: 0001_socle
Revises:
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_socle"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id_permissions", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id_permissions", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )

    op.create_table(
        "users",
        sa.Column("id_users", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_users", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "user_permissions",
        sa.Column(
            "id_user_permissions", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("id_users", sa.BigInteger(), nullable=False),
        sa.Column("id_permissions", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id_user_permissions", name=op.f("pk_user_permissions")),
        sa.ForeignKeyConstraint(
            ["id_users"],
            ["users.id_users"],
            name=op.f("fk_user_permissions_id_users_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_permissions"],
            ["permissions.id_permissions"],
            name=op.f("fk_user_permissions_id_permissions_permissions"),
        ),
        # Un même droit ne peut être attribué deux fois à la même personne.
        sa.UniqueConstraint(
            "id_users", "id_permissions", name=op.f("uq_user_permissions_id_users")
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id_refresh_tokens", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("id_users", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id_refresh_tokens", name=op.f("pk_refresh_tokens")),
        sa.ForeignKeyConstraint(
            ["id_users"],
            ["users.id_users"],
            name=op.f("fk_refresh_tokens_id_users_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_id_users"), "refresh_tokens", ["id_users"])


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_id_users"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("user_permissions")
    op.drop_table("users")
    op.drop_table("permissions")
