"""Table de reference des plateformes de diffusion.

Elle vit dans son propre module et non dans Comptes reseaux sociaux : quatre
modules la lisent — Media pour ses variantes, Generation pour les formats,
Connecteurs pour l'adresse de l'API, Publications pour les cibles. En faire la
propriete d'un seul aurait cree une dependance de tous vers lui.

Les contraintes et commentaires sont declares ici A L'IDENTIQUE de la
migration 0002 : `alembic check` echoue sur le moindre ecart, et tout ce qui
manquerait ici serait propose en SUPPRESSION dans la migration suivante.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocialPlatform(Base):
    """Reseau connu et ses regles."""

    __tablename__ = "social_platforms"
    __table_args__ = (
        UniqueConstraint("code", name="uq_social_platforms_code"),
        CheckConstraint(
            "message_response_window_hours IS NULL OR allows_automated_message_reply",
            name="fenetre_sans_reponse_automatisee",
        ),
        CheckConstraint(
            "max_description_length IS NULL OR max_description_length > 0",
            name="longueur_positive",
        ),
        {
            "comment": (
                "Reseaux connus et leurs regles. Seul endroit a modifier pour changer "
                "de version d'API. Zoom, Google Calendar et la messagerie d'envoi en "
                "sont exclus depuis le 20 octobre 2026 : ce ne sont pas des reseaux "
                "sociaux, ils n'ont ni comptes a raccorder ni mesures quotidiennes."
            )
        },
    )

    id_social_platforms: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(40),
        comment="Identifiant stable du reseau, en anglais et minuscules : facebook, linkedin.",
    )
    label: Mapped[str] = mapped_column(String(80))
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment=(
            "Un reseau se desactive, il ne se supprime pas : les publications "
            "passees le referencent."
        ),
    )
    api_base_url: Mapped[str | None] = mapped_column(
        String(255),
        comment="Adresse de base de l'API. Seul endroit a modifier pour changer de version.",
    )
    api_version: Mapped[str | None] = mapped_column(String(40))
    api_settings_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Reglages propres au reseau qui ne meritent pas une colonne chacun.",
    )
    max_description_length: Mapped[int | None] = mapped_column(
        Integer,
        comment="Longueur maximale du texte publie, description et hashtags assembles.",
    )
    supports_event_polling: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    supports_account_metrics: Mapped[bool] = mapped_column(Boolean, server_default=func.false())
    allows_automated_message_reply: Mapped[bool] = mapped_column(
        Boolean, server_default=func.false()
    )
    message_response_window_hours: Mapped[int | None] = mapped_column(
        Integer,
        comment=(
            "Duree pendant laquelle une reponse automatisee reste permise. "
            "Nulle si le reseau ne l'autorise pas."
        ),
    )
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
