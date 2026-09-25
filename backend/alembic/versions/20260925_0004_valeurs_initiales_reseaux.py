"""Valeurs initiales : réseaux et statuts de compte.

Facebook et Instagram sont activés. LinkedIn, TikTok et YouTube figurent au périmètre
du cahier des charges (F-05) mais restent désactivés tant qu'aucun connecteur n'existe.

Revision ID: 0004_reseaux_valeurs
Revises: 0003_reseaux
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.modules.social_accounts.constants import PLATFORMS, SOCIAL_ACCOUNT_STATUSES

revision: str = "0004_reseaux_valeurs"
down_revision: str | None = "0003_reseaux"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    platforms = sa.table(
        "platforms",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("is_enabled", sa.Boolean),
        sa.column("api_base_url", sa.String),
        sa.column("api_version", sa.String),
        sa.column("max_caption_length", sa.Integer),
        sa.column("sort_order", sa.SmallInteger),
    )
    op.bulk_insert(platforms, PLATFORMS)

    statuses = sa.table(
        "social_account_statuses",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("sort_order", sa.SmallInteger),
    )
    op.bulk_insert(statuses, SOCIAL_ACCOUNT_STATUSES)


def downgrade() -> None:
    op.execute("DELETE FROM social_account_statuses")
    op.execute("DELETE FROM platforms")
