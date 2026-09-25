"""Tables des comptes de réseaux sociaux et de leurs statistiques."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Platform(Base):
    """Réseau social. Table de référence : les règles de chaque plateforme y vivent."""

    __tablename__ = "platforms"
    __table_args__ = {
        "comment": "Réseaux sociaux connus et leurs règles. Table de référence : c'est le "
        "seul endroit à modifier pour changer de version d'API ou activer un nouveau réseau."
    }

    id_platforms: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant du réseau."
    )
    code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        comment="Code technique : facebook, instagram, linkedin, tiktok, youtube. "
        "Ne change jamais.",
    )
    label: Mapped[str] = mapped_column(String(50), comment="Nom affiché dans l'interface.")
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        comment="Faux = réseau prévu au cahier des charges mais sans connecteur : l'API le refuse.",
    )
    api_base_url: Mapped[str | None] = mapped_column(
        String(255), comment="Adresse de l'API du réseau, par exemple https://graph.facebook.com."
    )
    api_version: Mapped[str | None] = mapped_column(
        String(10),
        comment="Version d'API utilisée, par exemple v26.0. Modifiable sans toucher au code.",
    )
    max_caption_length: Mapped[int | None] = mapped_column(
        Integer,
        comment="Longueur maximale d'une légende, imposée par le réseau : 2 200 sur Instagram.",
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="Ordre d'affichage dans les listes."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de création (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )


class SocialAccountStatus(Base):
    """État d'un compte raccordé. Table de référence."""

    __tablename__ = "social_account_statuses"
    __table_args__ = {
        "comment": "États possibles d'un compte raccordé : connecté, à reconnecter, "
        "déconnecté. Table de référence."
    }

    id_social_account_statuses: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant du statut."
    )
    code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        comment="Code technique : connected, needs_reconnect, disconnected. Ne change jamais.",
    )
    label: Mapped[str] = mapped_column(String(50), comment="Libellé affiché dans l'interface.")
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, default=0, comment="Ordre d'affichage dans les listes."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de création (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )


class SocialAccount(Base):
    """Compte officiel de DATUM Academy raccordé à IAGORA."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("id_platforms", "external_meta_id"),
        {
            "comment": "Comptes officiels de DATUM Academy raccordés à IAGORA (page Facebook, "
            "compte Instagram). Détient les jetons d'accès chiffrés : sans eux, ni publication, "
            "ni messages, ni statistiques."
        },
    )

    id_social_accounts: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant du compte."
    )
    id_platforms: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("platforms.id_platforms"),
        comment="Réseau auquel appartient ce compte.",
    )
    id_social_account_statuses: Mapped[int] = mapped_column(
        BigInteger,
        # Nom donné à la main : la convention produirait 70 caractères, or PostgreSQL
        # tronque les identifiants à 63 — la contrainte deviendrait introuvable.
        ForeignKey(
            "social_account_statuses.id_social_account_statuses",
            name="fk_social_accounts_status",
        ),
        index=True,
        comment="État courant : connecté, à reconnecter, déconnecté.",
    )
    id_social_accounts_parent: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("social_accounts.id_social_accounts"),
        comment="Compte dont dépend celui-ci : un compte Instagram professionnel est rattaché "
        "à une page Facebook, et c'est le jeton de cette page qui sert.",
    )

    external_meta_id: Mapped[str] = mapped_column(
        String(64),
        comment="Identifiant du compte chez Meta (id de page ou de compte Instagram). Clé de "
        "tous les appels à l'API.",
    )
    name: Mapped[str] = mapped_column(
        String(255), comment="Nom du compte, par exemple Datum Academy."
    )
    handle: Mapped[str | None] = mapped_column(
        String(100), comment="Nom d'utilisateur public, par exemple @datum.academy."
    )

    access_token_encrypted: Mapped[str] = mapped_column(
        Text,
        comment="Jeton d'accès chiffré (Fernet). Réversible, car il doit être renvoyé à Meta "
        "à chaque appel. Ne sort jamais de l'API et n'apparaît jamais dans les journaux.",
    )
    token_kind: Mapped[str] = mapped_column(
        String(20),
        default="page",
        server_default="page",
        comment="Nature du jeton : page, user ou system_user.",
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Expiration du jeton (UTC). Vide si le jeton n'expire pas. Sert à prévenir "
        "avant la panne.",
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        JSONB,
        comment="Droits réellement accordés au jeton. Sans eux, impossible d'expliquer "
        "pourquoi une statistique est absente : read_insights manquant, par exemple.",
    )

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Dernière vérification réussie du compte (UTC)."
    )
    last_error: Mapped[str | None] = mapped_column(
        Text, comment="Dernier message d'erreur renvoyé par le réseau, pour le diagnostic."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de raccordement (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Date d'archivage (UTC). Renseignée = le compte disparaît des listes, mais "
        "les publications passées continuent d'y renvoyer.",
    )

    platform: Mapped[Platform] = relationship(lazy="selectin")
    status: Mapped[SocialAccountStatus] = relationship(lazy="selectin")

    @property
    def is_archived(self) -> bool:
        return self.deleted_at is not None


class SocialAccountMetric(Base):
    """Statistiques d'un compte, une ligne par jour.

    Toutes les valeurs sont **nullables** : Meta renvoie un ensemble vide quand la
    donnée n'existe pas. `null` signifie « non communiqué », et non « zéro » — la
    distinction est visible à l'écran, qui affiche « — ».
    """

    __tablename__ = "social_account_metrics"
    __table_args__ = (
        UniqueConstraint("id_social_accounts", "metric_date"),
        {
            "comment": "Statistiques d'un compte, une ligne par jour. Une valeur vide signifie "
            "« non communiqué par le réseau », et non « zéro » : l'interface affiche alors « — »."
        },
    )

    id_social_account_metrics: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant de la mesure."
    )
    id_social_accounts: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("social_accounts.id_social_accounts", ondelete="CASCADE"),
        index=True,
        comment="Compte mesuré. Ses mesures disparaissent avec lui.",
    )
    metric_date: Mapped[date] = mapped_column(
        Date, comment="Jour mesuré. Une seule ligne par compte et par jour."
    )

    followers: Mapped[int | None] = mapped_column(
        Integer, comment="Nombre d'abonnés à cette date. État, et non valeur du jour."
    )
    profile_views: Mapped[int | None] = mapped_column(
        Integer, comment="Consultations du profil pendant la journée."
    )
    reach: Mapped[int | None] = mapped_column(
        Integer,
        comment="Comptes uniques ayant vu un contenu pendant la journée. Indisponible en "
        "dessous de 100 abonnés sur Instagram.",
    )
    interactions: Mapped[int | None] = mapped_column(
        Integer, comment="J'aime, commentaires et partages cumulés sur la journée."
    )
    posts_count: Mapped[int | None] = mapped_column(
        Integer, comment="Nombre de publications parues ce jour-là."
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Moment de la collecte (UTC). Les données de Meta ont jusqu'à 48 h de retard.",
    )
    raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Réponse brute du réseau. Permet de retrouver une valeur quand un indicateur "
        "est renommé, comme « impressions » devenu « views ».",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de création (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )
