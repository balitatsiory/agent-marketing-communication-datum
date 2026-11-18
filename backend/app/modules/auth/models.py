"""Table du module Authentification.

Comme pour le module Utilisateurs, tout ce que la migration a créé est déclaré
ici à l'identique : sans cela, une autogénération future proposerait de
supprimer les index et les contraintes.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Raisons de révocation permises par la contrainte CHECK de la migration 0001.
ROTATED = "rotated"
LOGOUT = "logout"
USER_ARCHIVED = "user_archived"
REPLAY_DETECTED = "replay_detected"

RAISONS_DE_REVOCATION = (ROTATED, LOGOUT, USER_ARCHIVED, REPLAY_DETECTED)


class RefreshToken(Base):
    """Session ouverte, une ligne par navigateur connecté.

    Seule l'empreinte SHA-256 du jeton est conservée. `family_id` relie toute la
    lignée issue d'une même connexion, ce qui permet de la révoquer d'un bloc
    quand un ancien jeton est rejoué.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        # Les deux requêtes chaudes : révoquer une lignée, et révoquer toutes
        # les sessions d'un utilisateur archivé.
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_id_users", "id_users"),
        CheckConstraint(
            "revoked_reason IN ('" + "', '".join(RAISONS_DE_REVOCATION) + "')",
            name="revoked_reason",
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)",
            name="revocation_complete",
        ),
        {
            "comment": (
                "Sessions ouvertes, une ligne par navigateur connecte. On y garde "
                "l'empreinte SHA-256 du jeton, jamais le jeton. family_id relie "
                "toute la lignee issue d'une meme connexion : rejouer un ancien "
                "jeton revoque la lignee entiere en une seule instruction. Pas "
                "d'adresse IP : donnee personnelle, et aucune exigence ne la "
                "demande. Pas d'updated_at : la ligne est ecrite une fois."
            )
        },
    )

    id_refresh_tokens: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_users: Mapped[int] = mapped_column(ForeignKey("users.id_users"))
    token_hash: Mapped[str] = mapped_column(
        String(64),
        comment="Empreinte SHA-256 du jeton, en hexadecimal. Le jeton n'est jamais stocke.",
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        comment="Lignee des jetons issus d'une meme connexion, pour revocation en bloc.",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(
        String(20), comment="rotated | logout | user_archived | replay_detected."
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512), comment="Navigateur declare a la connexion. Sert au diagnostic."
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
