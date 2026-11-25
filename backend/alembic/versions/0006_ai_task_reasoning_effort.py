"""Ajout de l'effort de raisonnement (`reasoning_effort`) sur `ai_task_assignments`.

Permet de choisir le niveau de raisonnement OpenRouter (`reasoning.effort`)
par spécialité métier IAGORA : none, minimal, low, medium, high, xhigh (ou NULL
pour conserver le comportement par défaut du modèle).

Révision : 0006
Révision précédente : 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


def upgrade() -> None:
    op.add_column(
        "ai_task_assignments",
        sa.Column(
            "reasoning_effort",
            sa.String(20),
            nullable=True,
            comment=(
                "Effort de raisonnement OpenRouter (none, minimal, low, medium, high, xhigh). "
                "Nul = comportement par defaut du modele."
            ),
        ),
    )
    op.create_check_constraint(
        "reasoning_effort",
        "ai_task_assignments",
        "reasoning_effort IS NULL OR reasoning_effort IN ('" + "', '".join(REASONING_EFFORTS) + "')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ai_task_assignments "
        "DROP CONSTRAINT IF EXISTS ck_ai_task_assignments_reasoning_effort"
    )
    op.drop_column("ai_task_assignments", "reasoning_effort")
