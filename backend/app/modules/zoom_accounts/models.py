"""Tables du module Comptes Zoom.

Trois tables :
- `zoom_accounts` : une application Zoom Server-to-Server et l'adresse de la
  personne hôte des réunions. Porte aussi le dernier jeton d'accès, chiffré.
- `zoom_account_credentials` : les « Client Secret », chiffrés par Fernet, avec
  la même mécanique de remplacement que `email_account_credentials`.
- `zoom_account_checks` : l'historique des vérifications, en ajout seul.

Les contraintes, index et commentaires sont déclarés ici À L'IDENTIQUE de la
migration 0011 : `alembic check` échoue sur le moindre écart. Seuls les
déclencheurs (`updated_at`, ajout seul) vivent uniquement dans la migration.
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.zoom_accounts.constants import CHECK_KINDS


class ZoomAccount(Base):
    """Un compte Zoom raccordé : l'application, l'hôte et le dernier jeton."""

    __tablename__ = "zoom_accounts"
    __table_args__ = (
        Index(
            "uq_zoom_accounts_identifiant",
            "external_zoom_account_id",
            "host_email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Comptes Zoom (applications Server-to-Server OAuth). Le Client Secret n'est "
                "pas ici : il vit chiffre dans zoom_account_credentials."
            )
        },
    )

    id_zoom_accounts: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du compte Zoom."
    )
    label: Mapped[str] = mapped_column(
        String(120), comment="Nom lisible du compte, affiche dans l'interface."
    )
    host_email: Mapped[str] = mapped_column(
        String(255),
        comment=(
            "Adresse Zoom de la personne hote, en minuscules. Les reunions sont listees "
            "et creees a son nom."
        ),
    )
    external_zoom_account_id: Mapped[str] = mapped_column(
        String(128), comment="Account ID de l'application, lu sur marketplace.zoom.us."
    )
    client_id: Mapped[str] = mapped_column(String(255), comment="Client ID de l'application.")
    granted_scopes_json: Mapped[list[str] | None] = mapped_column(
        JSONB, comment="Droits Zoom portes par le dernier jeton obtenu."
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(
        Text, comment="Dernier jeton d'acces, chiffre par Fernet. Valable une heure."
    )
    access_token_obtained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Date d'obtention du dernier jeton (UTC)."
    )
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Expiration du dernier jeton (UTC)."
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
        ForeignKey("users.id_users", name="fk_zoom_accounts_id_users_created_by_users"),
        comment="Utilisateur qui a enregistre le compte.",
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_zoom_accounts_id_users_changed_by_users"),
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
        comment="Archivage du compte : il n'est plus propose, ses webinaires restent.",
    )


class ZoomAccountCredential(Base):
    """Un Client Secret, chiffré par Fernet. Un remplacement ajoute une ligne."""

    __tablename__ = "zoom_account_credentials"
    __table_args__ = (
        Index(
            "uq_zoom_account_credentials_actif",
            "id_zoom_accounts",
            unique=True,
            postgresql_where=text("superseded_at IS NULL AND revoked_at IS NULL"),
        ),
        {
            "comment": (
                "Client Secret des comptes Zoom, chiffres par Fernet. Un changement cree "
                "une nouvelle ligne et marque la precedente remplacee."
            )
        },
    )

    id_zoom_account_credentials: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la delivrance du secret."
    )
    id_zoom_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "zoom_accounts.id_zoom_accounts",
            name="fk_zoom_account_credentials_id_zoom_accounts_zoom_accounts",
            ondelete="CASCADE",
        ),
        comment="Compte Zoom concerne.",
    )
    client_secret_encrypted: Mapped[str] = mapped_column(
        Text,
        comment=(
            "Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). Le secret en clair ne touche "
            "jamais le disque."
        ),
    )
    client_secret_masked: Mapped[str] = mapped_column(
        String(40),
        comment="Apercu masque sans secret, pour que l'interface montre qu'il existe.",
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de saisie du secret (UTC).",
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Remplacement par un secret plus recent."
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Retrait sans remplacement : le compte ne peut plus appeler Zoom.",
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_zoom_account_credentials_id_users_created_by_users"),
        comment="Utilisateur qui a saisi le secret.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )


class ZoomAccountCheck(Base):
    """Une vérification : test de connexion ou renouvellement du jeton. Ajout seul."""

    __tablename__ = "zoom_account_checks"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('" + "', '".join(CHECK_KINDS) + "')",
            name="kind",
        ),
        {
            "comment": (
                "Historique des verifications d'un compte Zoom : test de connexion ou "
                "renouvellement du jeton. En ajout seul."
            )
        },
    )

    id_zoom_account_checks: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la verification."
    )
    id_zoom_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "zoom_accounts.id_zoom_accounts",
            name="fk_zoom_account_checks_id_zoom_accounts_zoom_accounts",
            ondelete="CASCADE",
        ),
        comment="Compte verifie.",
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        comment="connection (jeton + appel reel) | token_refresh (nouveau jeton seul).",
    )
    is_ok: Mapped[bool] = mapped_column(Boolean, comment="Vrai si Zoom a accepte l'operation.")
    message: Mapped[str | None] = mapped_column(
        Text, comment="Compte rendu en francais, affiche tel quel dans l'interface."
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer, comment="Duree de l'echange avec Zoom, en millisecondes."
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Moment de la verification (UTC).",
    )
    id_users_checked_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_zoom_account_checks_id_users_checked_by_users"),
        comment="Utilisateur qui a declenche la verification.",
    )
