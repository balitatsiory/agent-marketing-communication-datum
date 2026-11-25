"""Module 07 Newsletter — comptes d'envoi SMTP (identifiants chiffrés en base).

Trois tables :
- `email_accounts` : serveur, port, mode de chiffrement, identifiant, expéditeur ;
- `email_account_credentials` : mots de passe chiffrés par Fernet, en ajout seul ;
- `email_account_checks` : historique des vérifications, en ajout seul.

Insère également le droit `manage_email_accounts` (module 07, sort_order 700).

Révision : 0009
Révision précédente : 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECURITIES = ("ssl_tls", "starttls")
CHECK_KINDS = ("connection", "test_message")


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column(
            "id_email_accounts",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant du compte d'envoi.",
        ),
        sa.Column(
            "label",
            sa.String(120),
            nullable=False,
            comment="Nom lisible du compte, affiche dans l'interface.",
        ),
        sa.Column(
            "host",
            sa.String(255),
            nullable=False,
            comment="Serveur SMTP sortant (ex: smtp.ionos.fr).",
        ),
        sa.Column(
            "port",
            sa.Integer,
            nullable=False,
            comment="465 en SSL/TLS implicite, 587 en STARTTLS.",
        ),
        sa.Column(
            "security",
            sa.String(20),
            nullable=False,
            comment=(
                "ssl_tls (chiffre des l'ouverture) | starttls (passage en TLS apres ouverture)."
            ),
        ),
        sa.Column(
            "username",
            sa.String(255),
            nullable=False,
            comment=(
                "Identifiant SMTP, toujours en minuscules. Chez IONOS, l'adresse de la boite."
            ),
        ),
        sa.Column(
            "from_email",
            sa.String(255),
            nullable=False,
            comment=(
                "Adresse d'expedition, en minuscules. Le serveur la refuse si la boite "
                "ne la porte pas."
            ),
        ),
        sa.Column(
            "from_name",
            sa.String(120),
            nullable=True,
            comment="Nom affiche devant l'adresse d'expedition.",
        ),
        sa.Column(
            "reply_to_email",
            sa.String(255),
            nullable=True,
            comment="Adresse de reponse, quand elle differe de l'expediteur.",
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("20"),
            comment="Delai d'attente d'une operation SMTP, en secondes.",
        ),
        sa.Column(
            "is_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
            comment="Compte utilise par defaut pour les envois. Un seul a la fois.",
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date de la derniere verification (UTC), reussie ou non.",
        ),
        sa.Column(
            "last_verify_ok",
            sa.Boolean,
            nullable=True,
            comment="Resultat de la derniere verification. Vide si aucune n'a eu lieu.",
        ),
        sa.Column(
            "last_verify_message",
            sa.Text,
            nullable=True,
            comment="Compte rendu de la derniere verification, affiche tel quel.",
        ),
        sa.Column(
            "id_users_created_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a enregistre le compte.",
        ),
        sa.Column(
            "id_users_changed_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur de la derniere modification.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de derniere modification (UTC).",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Archivage du compte : il n'est plus propose aux envois.",
        ),
        sa.PrimaryKeyConstraint("id_email_accounts", name="pk_email_accounts"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_email_accounts_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_email_accounts_id_users_changed_by_users",
        ),
        sa.CheckConstraint(
            "security IN ('" + "', '".join(SECURITIES) + "')",
            name="ck_email_accounts_security",
        ),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_email_accounts_port"),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 120", name="ck_email_accounts_timeout_seconds"
        ),
        comment=(
            "Comptes d'envoi SMTP (IONOS et autres). Le mot de passe n'est pas ici : "
            "il vit chiffre dans email_account_credentials."
        ),
    )
    # Deux fois le même compte sur le même serveur n'aurait aucun sens, mais un
    # compte archivé ne doit pas empêcher d'en recréer un identique.
    op.create_index(
        "uq_email_accounts_identifiant",
        "email_accounts",
        ["host", "port", "username"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # « Un seul compte par défaut » tenu par la base, et non par le service :
    # c'est la seule façon qu'une requête concurrente ne puisse pas en créer deux.
    op.create_index(
        "uq_email_accounts_defaut",
        "email_accounts",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )

    op.create_table(
        "email_account_credentials",
        sa.Column(
            "id_email_account_credentials",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de la delivrance de mot de passe.",
        ),
        sa.Column(
            "id_email_accounts",
            sa.Integer,
            nullable=False,
            comment="Compte d'envoi concerne. Ses mots de passe disparaissent avec lui.",
        ),
        sa.Column(
            "password_encrypted",
            sa.Text,
            nullable=False,
            comment=(
                "Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). Le mot de passe en clair "
                "ne touche jamais le disque."
            ),
        ),
        sa.Column(
            "password_masked",
            sa.String(40),
            nullable=False,
            comment="Apercu masque sans secret, pour que l'interface montre qu'il existe.",
        ),
        sa.Column(
            "obtained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de saisie du mot de passe (UTC).",
        ),
        sa.Column(
            "superseded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Remplacement par un mot de passe plus recent.",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Retrait sans remplacement : le compte ne peut plus envoyer.",
        ),
        sa.Column(
            "id_users_created_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a saisi le mot de passe.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Date de creation (UTC).",
        ),
        sa.PrimaryKeyConstraint(
            "id_email_account_credentials", name="pk_email_account_credentials"
        ),
        sa.ForeignKeyConstraint(
            ["id_email_accounts"],
            ["email_accounts.id_email_accounts"],
            name="fk_email_account_credentials_id_email_accounts_email_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_email_account_credentials_id_users_created_by_users",
        ),
        comment=(
            "Mots de passe des comptes d'envoi, chiffres par Fernet. Un changement "
            "cree une nouvelle ligne et marque la precedente remplacee."
        ),
    )
    op.create_index(
        "uq_email_account_credentials_actif",
        "email_account_credentials",
        ["id_email_accounts"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "email_account_checks",
        sa.Column(
            "id_email_account_checks",
            sa.Integer,
            sa.Identity(always=False),
            nullable=False,
            comment="Identifiant de la verification.",
        ),
        sa.Column(
            "id_email_accounts",
            sa.Integer,
            nullable=False,
            comment="Compte verifie. Ses verifications disparaissent avec lui.",
        ),
        sa.Column(
            "kind",
            sa.String(20),
            nullable=False,
            comment=(
                "connection (connexion + authentification) | test_message "
                "(message reellement envoye)."
            ),
        ),
        sa.Column(
            "is_ok",
            sa.Boolean,
            nullable=False,
            comment="Vrai si le serveur a accepte l'operation.",
        ),
        sa.Column(
            "message",
            sa.Text,
            nullable=True,
            comment="Compte rendu en francais, affiche tel quel dans l'interface.",
        ),
        sa.Column(
            "recipient_email",
            sa.String(255),
            nullable=True,
            comment="Destinataire du message de test. Vide pour un simple test de connexion.",
        ),
        sa.Column(
            "latency_ms",
            sa.Integer,
            nullable=True,
            comment="Duree de l'echange avec le serveur, en millisecondes.",
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Moment de la verification (UTC).",
        ),
        sa.Column(
            "id_users_checked_by",
            sa.Integer,
            nullable=True,
            comment="Utilisateur qui a declenche la verification.",
        ),
        sa.PrimaryKeyConstraint("id_email_account_checks", name="pk_email_account_checks"),
        sa.ForeignKeyConstraint(
            ["id_email_accounts"],
            ["email_accounts.id_email_accounts"],
            name="fk_email_account_checks_id_email_accounts_email_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_checked_by"],
            ["users.id_users"],
            name="fk_email_account_checks_id_users_checked_by_users",
        ),
        sa.CheckConstraint(
            "kind IN ('" + "', '".join(CHECK_KINDS) + "')",
            name="ck_email_account_checks_kind",
        ),
        comment=(
            "Historique des verifications d'un compte d'envoi : connexion authentifiee "
            "ou message de test. En ajout seul."
        ),
    )

    op.execute(
        "CREATE TRIGGER trg_email_accounts_updated_at BEFORE UPDATE ON email_accounts "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # Les deux historiques sont en AJOUT SEUL : le rôle applicatif ne doit pas
    # pouvoir réécrire une vérification passée. Le remplacement d'un mot de
    # passe est la seule exception, et il porte sur les colonnes de dates.
    op.execute("REVOKE UPDATE, DELETE ON email_account_checks FROM PUBLIC")
    op.execute("REVOKE DELETE ON email_account_credentials FROM PUBLIC")

    op.execute(
        """
        INSERT INTO permissions (code, label, description, sort_order)
        VALUES (
            'manage_email_accounts',
            'Gerer les comptes d''envoi',
            'Configurer les comptes SMTP d''envoi, leurs identifiants '
            'chiffres et les tests de connexion.',
            700
        )
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    # Les attributions d'abord : une permission deja accordee a un utilisateur
    # est referencee par user_permissions, et la supprimer sans cela echoue sur
    # la cle etrangere.
    op.execute(
        """
        DELETE FROM user_permissions
        WHERE id_permissions IN (
            SELECT id_permissions FROM permissions WHERE code = 'manage_email_accounts'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'manage_email_accounts'")
    op.execute("DROP TRIGGER IF EXISTS trg_email_accounts_updated_at ON email_accounts")
    op.drop_table("email_account_checks")
    op.drop_index("uq_email_account_credentials_actif", table_name="email_account_credentials")
    op.drop_table("email_account_credentials")
    op.drop_index("uq_email_accounts_defaut", table_name="email_accounts")
    op.drop_index("uq_email_accounts_identifiant", table_name="email_accounts")
    op.drop_table("email_accounts")
