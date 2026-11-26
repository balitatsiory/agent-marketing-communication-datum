"""Table du module Notifications."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.notifications.constants import SOURCES_VALIDES, TYPES_NOTIFICATION_VALIDES


class Notification(Base):
    """Notification interne ou issue d'une plateforme destinée à un utilisateur."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "source_scope IN ('" + "', '".join(SOURCES_VALIDES) + "')",
            name="source_scope_valide",
        ),
        CheckConstraint(
            "notification_type IN ('" + "', '".join(TYPES_NOTIFICATION_VALIDES) + "')",
            name="notification_type_valide",
        ),
        Index("ix_notifications_recipient_created", "id_users_recipient", "created_at"),
        Index("ix_notifications_recipient_unread", "id_users_recipient", "is_read"),
        Index("ix_notifications_entity", "entity_type", "entity_id"),
        {
            "comment": (
                "Notifications internes (validations, corrections, equipe) et "
                "plateformes (echecs, publications, commentaires, comptes)."
            )
        },
    )

    id_notifications: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_users_recipient: Mapped[int] = mapped_column(
        ForeignKey("users.id_users", ondelete="CASCADE"),
        nullable=False,
    )
    id_users_actor: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    platform_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    requires_action: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=func.false()
    )
    action_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.false())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
