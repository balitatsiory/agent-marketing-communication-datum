"""Valeurs initiales des droits (F-22).

Les cinq droits sont posés par migration, pour que toutes les bases — poste,
test, production — contiennent exactement les mêmes codes.

Revision ID: 0002_droits
Revises: 0001_socle
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_droits"
down_revision: str | None = "0001_socle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DROITS = [
    {"code": "read", "label": "Consulter", "sort_order": 1},
    {"code": "create", "label": "Créer", "sort_order": 2},
    {"code": "review", "label": "Valider", "sort_order": 3},
    {"code": "publish", "label": "Publier", "sort_order": 4},
    {"code": "admin", "label": "Administrer", "sort_order": 5},
]


def upgrade() -> None:
    table = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("sort_order", sa.SmallInteger),
    )
    op.bulk_insert(table, DROITS)


def downgrade() -> None:
    codes = ", ".join(f"'{droit['code']}'" for droit in DROITS)
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")  # noqa: S608
