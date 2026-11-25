"""Ajout du type de clé `sandbox` sur `openrouter_api_keys`.

Permet d'enregistrer une clé API OpenRouter dédiée au Bac à sable IA
(chiffrée par Fernet en base) afin d'isoler les tests des statistiques
de production.

Révision : 0007
Révision précédente : 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY_KINDS = ("management", "standard", "sandbox")
OLD_KEY_KINDS = ("management", "standard")


def upgrade() -> None:
    op.drop_constraint(
        "ck_openrouter_api_keys_key_kind",
        "openrouter_api_keys",
        type_="check",
    )
    op.create_check_constraint(
        "ck_openrouter_api_keys_key_kind",
        "openrouter_api_keys",
        "key_kind IN ('" + "', '".join(KEY_KINDS) + "')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM openrouter_api_keys WHERE key_kind = 'sandbox'")
    op.drop_constraint(
        "ck_openrouter_api_keys_key_kind",
        "openrouter_api_keys",
        type_="check",
    )
    op.create_check_constraint(
        "ck_openrouter_api_keys_key_kind",
        "openrouter_api_keys",
        "key_kind IN ('" + "', '".join(OLD_KEY_KINDS) + "')",
    )
