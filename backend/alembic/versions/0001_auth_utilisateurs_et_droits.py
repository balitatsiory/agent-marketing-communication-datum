"""Modules 01 Authentification et 02 Utilisateurs et droits.

Quatre tables : users, permissions, user_permissions, refresh_tokens.
Revues colonne par colonne et validées les 17 et 18 novembre 2026.

Révision : 0001
Révision précédente : aucune
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Valeurs permises pour refresh_tokens.revoked_reason.
# Contrainte CHECK et non table de référence : la valeur n'est jamais affichée,
# jamais triée, et aucun comportement n'en dépend — elle sert à expliquer un
# incident après coup.
RAISONS_DE_REVOCATION = ("rotated", "logout", "user_archived", "replay_detected")

COMMENTAIRES: dict[str, dict[str, str]] = {
    "users": {
        "email": "Identifiant de connexion. Unique a la casse pres, parmi les comptes non archives.",
        "password_hash": (
            "Empreinte bcrypt. Dimensionnee large pour ne pas bloquer un passage "
            "ulterieur a argon2, qui produit des empreintes plus longues."
        ),
        "is_active": "Etat d'exploitation, reversible : acces suspendu sans archivage.",
        "last_login_at": "Derniere connexion reussie.",
        "deleted_at": (
            "Archivage, pose PAR-DESSUS l'etat et non a sa place. L'archivage "
            "revoque tous les jetons de l'utilisateur dans la meme transaction."
        ),
    },
    "permissions": {
        "code": "Identifiant stable du droit, en anglais, minuscules et tiret bas.",
        "label": "Libelle francais affiche dans l'ecran des habilitations.",
        "description": "Phrase expliquant ce que le droit autorise, affichee a l'administrateur.",
        "sort_order": "Ordre d'affichage : numero du module x 100, par pas de 10.",
    },
    "user_permissions": {
        "id_users_created_by": "Qui a attribue ce droit.",
        "deleted_at": "Revocation du droit. La ligne est conservee pour l'historique.",
    },
    "refresh_tokens": {
        "token_hash": "Empreinte SHA-256 du jeton, en hexadecimal. Le jeton n'est jamais stocke.",
        "family_id": "Lignee des jetons issus d'une meme connexion, pour revocation en bloc.",
        "revoked_reason": "rotated | logout | user_archived | replay_detected.",
        "user_agent": "Navigateur declare a la connexion. Sert au diagnostic.",
    },
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id_users", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column("id_users_changed_by", sa.Integer, nullable=True),
        sa.Column("id_users_deleted_by", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("id_users", name="pk_users"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_users_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_users_id_users_changed_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_deleted_by"],
            ["users.id_users"],
            name="fk_users_id_users_deleted_by_users",
        ),
        comment=(
            "Membres de l'equipe DATUM Academy qui utilisent IAGORA. Un compte "
            "archive (deleted_at) disparait des listes mais reste l'auteur de "
            "ses publications passees."
        ),
    )

    # PostgreSQL distingue Balita@... de balita@... : sans index sur lower(email),
    # deux comptes pourraient exister pour la meme personne. L'index est
    # PARTIEL, sinon un compte archive interdirait de recreer son adresse.
    op.create_index(
        "uq_users_email_actif",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "permissions",
        sa.Column("id_permissions", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_permissions", name="pk_permissions"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
        comment=(
            "Droits attribuables, alimentes par migration. Chaque module insere "
            "les siens, avec un sort_order valant son numero de module multiplie "
            "par 100, par pas de 10. Un droit se retire par migration : il ne "
            "s'archive pas."
        ),
    )

    op.create_table(
        "user_permissions",
        sa.Column("id_user_permissions", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_users", sa.Integer, nullable=False),
        sa.Column("id_permissions", sa.Integer, nullable=False),
        sa.Column("id_users_created_by", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_deleted_by", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("id_user_permissions", name="pk_user_permissions"),
        sa.ForeignKeyConstraint(
            ["id_users"], ["users.id_users"], name="fk_user_permissions_id_users_users"
        ),
        sa.ForeignKeyConstraint(
            ["id_permissions"],
            ["permissions.id_permissions"],
            name="fk_user_permissions_id_permissions_permissions",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_user_permissions_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_deleted_by"],
            ["users.id_users"],
            name="fk_user_permissions_id_users_deleted_by_users",
        ),
        comment=(
            "Quel utilisateur possede quel droit. Aucun role n'est fige : les "
            "droits se cumulent. Une revocation archive la ligne au lieu de la "
            "supprimer, pour garder la trace de qui a pu faire quoi et quand."
        ),
    )
    op.create_index(
        "uq_user_permissions_actif",
        "user_permissions",
        ["id_users", "id_permissions"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id_refresh_tokens", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_users", sa.Integer, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(20), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_refresh_tokens", name="pk_refresh_tokens"),
        sa.ForeignKeyConstraint(
            ["id_users"], ["users.id_users"], name="fk_refresh_tokens_id_users_users"
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        sa.CheckConstraint(
            "revoked_reason IN ('" + "', '".join(RAISONS_DE_REVOCATION) + "')",
            name="revoked_reason",
        ),
        # Une date de revocation sans raison, ou l'inverse, serait une ligne
        # qu'on ne saurait pas interpreter.
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)",
            name="revocation_complete",
        ),
        comment=(
            "Sessions ouvertes, une ligne par navigateur connecte. On y garde "
            "l'empreinte SHA-256 du jeton, jamais le jeton. family_id relie "
            "toute la lignee issue d'une meme connexion : rejouer un ancien "
            "jeton revoque la lignee entiere en une seule instruction. Pas "
            "d'adresse IP : donnee personnelle, et aucune exigence ne la "
            "demande. Pas d'updated_at : la ligne est ecrite une fois."
        ),
    )
    # La revocation d'une lignee et celle de toutes les sessions d'un
    # utilisateur archive sont les deux requetes chaudes de cette table.
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_id_users", "refresh_tokens", ["id_users"])

    # COMMENT ON COLUMN est du DDL : il n'accepte pas de parametre lie, le texte
    # doit donc etre place dans l'instruction, avec ses apostrophes doublees.
    for table, colonnes in COMMENTAIRES.items():
        for colonne, texte in colonnes.items():
            echappe = texte.replace("'", "''")
            op.execute(f"COMMENT ON COLUMN {table}.{colonne} IS '{echappe}'")

    # L'administrateur modifie certaines valeurs directement en base (decision
    # sur les mots de passe) : l'application ne peut donc pas etre seule
    # responsable d'updated_at. Le declencheur la garantit quelle que soit
    # l'origine de l'ecriture.
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("users", "permissions"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    # Seuls les droits de CE module. publish appartient au module 08,
    # manage_ai_models au module 06 : leurs migrations insereront les leurs.
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String),
            sa.column("label", sa.String),
            sa.column("description", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {
                "code": "manage_users",
                "label": "Gerer les utilisateurs",
                "description": (
                    "Creer, modifier et desactiver les comptes de l'equipe. "
                    "Ne permet pas d'attribuer des droits."
                ),
                "sort_order": 200,
            },
            {
                "code": "manage_permissions",
                "label": "Attribuer les droits",
                "description": (
                    "Attribuer et retirer les droits des utilisateurs, y compris "
                    "les siens. Droit le plus sensible du systeme."
                ),
                "sort_order": 210,
            },
        ],
    )


def downgrade() -> None:
    for table in ("permissions", "users"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.drop_table("refresh_tokens")
    op.drop_table("user_permissions")
    op.drop_table("permissions")
    op.drop_table("users")
