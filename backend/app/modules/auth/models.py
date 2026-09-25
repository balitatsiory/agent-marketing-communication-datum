"""Table refresh_tokens : les sessions ouvertes.

Le jeton d'accès, de courte durée, n'est pas stocké : il se vérifie par sa signature.
Le jeton de renouvellement, lui, est enregistré pour pouvoir être **révoqué** —
sans quoi « Se déconnecter » n'aurait aucun effet côté serveur.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RefreshToken(Base):
    """Une ligne = une session : un navigateur, un poste."""

    __tablename__ = "refresh_tokens"
    __table_args__ = {
        "comment": "Sessions ouvertes : une ligne par navigateur connecté. Existe pour "
        "pouvoir révoquer une session ; sans elle, la déconnexion serait sans effet côté serveur."
    }

    id_refresh_tokens: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True, comment="Identifiant de la session."
    )
    id_users: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id_users", ondelete="CASCADE"),
        index=True,
        comment="Utilisateur connecté. Ses sessions disparaissent avec son compte.",
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        comment="Empreinte SHA-256 du jeton de renouvellement. Le jeton lui-même n'est jamais "
        "stocké ; l'empreinte est déterministe pour retrouver la session à partir du jeton reçu.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment="Fin de validité de la session (UTC)."
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Date de révocation (UTC) : déconnexion, ou renouvellement qui a remplacé ce "
        "jeton. Renseignée = le jeton ne vaut plus rien.",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255), comment="Navigateur ou outil à l'origine de la session, pour s'y retrouver."
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date d'ouverture de la session (UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Date de dernière modification (UTC).",
    )
