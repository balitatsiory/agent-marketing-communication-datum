"""Tables du module Comptes d'envoi (SMTP).

Trois tables :
- `email_accounts` : le compte d'envoi lui-même — serveur, port, mode de
  chiffrement, identifiant et adresse d'expédition. Aucun secret ici.
- `email_account_credentials` : les mots de passe de boîte, chiffrés par Fernet,
  avec la même mécanique de remplacement que `openrouter_api_keys`.
- `email_account_checks` : l'historique des vérifications, en ajout seul.

Pourquoi le mot de passe vit dans une table à part et non dans une colonne de
`email_accounts` : un mot de passe de boîte se change sans que le compte change.
Une colonne obligerait à écraser l'ancien, et on perdrait la date à laquelle le
compte a cessé de fonctionner — précisément ce qu'on cherche quand les envois
s'arrêtent du jour au lendemain.

Les contraintes, index et commentaires sont déclarés ici À L'IDENTIQUE de la
migration 0009 : `alembic check` échoue sur le moindre écart.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.email_accounts.constants import (
    CHECK_KINDS,
    SECURITIES,
    TIMEOUT_SECONDS_MAX,
    TIMEOUT_SECONDS_MIN,
)


class EmailAccount(Base):
    """Un compte d'envoi SMTP : où se connecter, avec quel identifiant, pour quelle adresse."""

    __tablename__ = "email_accounts"
    __table_args__ = (
        CheckConstraint(
            "security IN ('" + "', '".join(SECURITIES) + "')",
            name="security",
        ),
        CheckConstraint("port BETWEEN 1 AND 65535", name="port"),
        CheckConstraint(
            f"timeout_seconds BETWEEN {TIMEOUT_SECONDS_MIN} AND {TIMEOUT_SECONDS_MAX}",
            name="timeout_seconds",
        ),
        Index(
            "uq_email_accounts_identifiant",
            "host",
            "port",
            "username",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_email_accounts_defaut",
            "is_default",
            unique=True,
            postgresql_where=text("is_default AND deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Comptes d'envoi SMTP (IONOS et autres). Le mot de passe n'est pas ici : "
                "il vit chiffre dans email_account_credentials."
            )
        },
    )

    id_email_accounts: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du compte d'envoi."
    )
    label: Mapped[str] = mapped_column(
        String(120), comment="Nom lisible du compte, affiche dans l'interface."
    )
    host: Mapped[str] = mapped_column(
        String(255), comment="Serveur SMTP sortant (ex: smtp.ionos.fr)."
    )
    port: Mapped[int] = mapped_column(Integer, comment="465 en SSL/TLS implicite, 587 en STARTTLS.")
    security: Mapped[str] = mapped_column(
        String(20),
        comment="ssl_tls (chiffre des l'ouverture) | starttls (passage en TLS apres ouverture).",
    )
    username: Mapped[str] = mapped_column(
        String(255),
        comment="Identifiant SMTP, toujours en minuscules. Chez IONOS, l'adresse de la boite.",
    )
    from_email: Mapped[str] = mapped_column(
        String(255),
        comment=(
            "Adresse d'expedition, en minuscules. Le serveur la refuse si la boite ne la porte pas."
        ),
    )
    from_name: Mapped[str | None] = mapped_column(
        String(120), comment="Nom affiche devant l'adresse d'expedition."
    )
    reply_to_email: Mapped[str | None] = mapped_column(
        String(255), comment="Adresse de reponse, quand elle differe de l'expediteur."
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        server_default=text("20"),
        comment="Delai d'attente d'une operation SMTP, en secondes.",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="Compte utilise par defaut pour les envois. Un seul a la fois.",
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Date de la derniere verification (UTC), reussie ou non.",
    )
    last_verify_ok: Mapped[bool | None] = mapped_column(
        Boolean, comment="Resultat de la derniere verification. Vide si aucune n'a eu lieu."
    )
    last_verify_message: Mapped[str | None] = mapped_column(
        Text, comment="Compte rendu de la derniere verification, affiche tel quel."
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_email_accounts_id_users_created_by_users"),
        comment="Utilisateur qui a enregistre le compte.",
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_email_accounts_id_users_changed_by_users"),
        comment="Utilisateur de la derniere modification.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de derniere modification (UTC).",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Archivage du compte : il n'est plus propose aux envois.",
    )


class EmailAccountCredential(Base):
    """Un mot de passe de boîte, chiffré par Fernet. Historique en ajout seul."""

    __tablename__ = "email_account_credentials"
    __table_args__ = (
        Index(
            "uq_email_account_credentials_actif",
            "id_email_accounts",
            unique=True,
            postgresql_where=text("superseded_at IS NULL AND revoked_at IS NULL"),
        ),
        {
            "comment": (
                "Mots de passe des comptes d'envoi, chiffres par Fernet. Un changement "
                "cree une nouvelle ligne et marque la precedente remplacee."
            )
        },
    )

    id_email_account_credentials: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la delivrance de mot de passe."
    )
    id_email_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "email_accounts.id_email_accounts",
            name="fk_email_account_credentials_id_email_accounts_email_accounts",
            ondelete="CASCADE",
        ),
        comment="Compte d'envoi concerne. Ses mots de passe disparaissent avec lui.",
    )
    password_encrypted: Mapped[str] = mapped_column(
        Text,
        comment=(
            "Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). Le mot de passe en clair "
            "ne touche jamais le disque."
        ),
    )
    password_masked: Mapped[str] = mapped_column(
        String(40),
        comment="Apercu masque sans secret, pour que l'interface montre qu'il existe.",
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de saisie du mot de passe (UTC).",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Remplacement par un mot de passe plus recent."
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Retrait sans remplacement : le compte ne peut plus envoyer.",
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_email_account_credentials_id_users_created_by_users"),
        comment="Utilisateur qui a saisi le mot de passe.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )


class EmailAccountCheck(Base):
    """Une vérification du compte : connexion seule, ou message de test. Ajout seul."""

    __tablename__ = "email_account_checks"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('" + "', '".join(CHECK_KINDS) + "')",
            name="kind",
        ),
        {
            "comment": (
                "Historique des verifications d'un compte d'envoi : connexion authentifiee "
                "ou message de test. En ajout seul."
            )
        },
    )

    id_email_account_checks: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la verification."
    )
    id_email_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "email_accounts.id_email_accounts",
            name="fk_email_account_checks_id_email_accounts_email_accounts",
            ondelete="CASCADE",
        ),
        comment="Compte verifie. Ses verifications disparaissent avec lui.",
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        comment=(
            "connection (connexion + authentification) | test_message (message reellement envoye)."
        ),
    )
    is_ok: Mapped[bool] = mapped_column(
        Boolean, comment="Vrai si le serveur a accepte l'operation."
    )
    message: Mapped[str | None] = mapped_column(
        Text, comment="Compte rendu en francais, affiche tel quel dans l'interface."
    )
    recipient_email: Mapped[str | None] = mapped_column(
        String(255),
        comment="Destinataire du message de test. Vide pour un simple test de connexion.",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer, comment="Duree de l'echange avec le serveur, en millisecondes."
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Moment de la verification (UTC).",
    )
    id_users_checked_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_email_account_checks_id_users_checked_by_users"),
        comment="Utilisateur qui a declenche la verification.",
    )
