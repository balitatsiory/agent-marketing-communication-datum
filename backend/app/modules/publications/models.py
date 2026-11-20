"""Tables SQLAlchemy du module 08 Publications (alignées sur la base PostgreSQL)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Format(Base):
    """Format de publication commun aux cibles (image, carrousel, reel, texte…)."""

    __tablename__ = "formats"

    id_formats: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    min_media_count: Mapped[int] = mapped_column(SmallInteger)
    max_media_count: Mapped[int] = mapped_column(SmallInteger)
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=func.true())
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformFormat(Base):
    """Association plateforme × format accepté."""

    __tablename__ = "platform_formats"

    id_platform_formats: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_social_platforms: Mapped[int] = mapped_column(
        ForeignKey("social_platforms.id_social_platforms")
    )
    id_formats: Mapped[int] = mapped_column(ForeignKey("formats.id_formats"))
    format_duration_hours: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicationStatus(Base):
    __tablename__ = "publication_statuses"

    id_publication_statuses: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)


class DeliveryStatus(Base):
    __tablename__ = "delivery_statuses"

    id_delivery_statuses: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)


class PublicationEventType(Base):
    __tablename__ = "publication_event_types"

    id_publication_event_types: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))


class DeliveryEventType(Base):
    __tablename__ = "delivery_event_types"

    id_delivery_event_types: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))


class Publication(Base):
    __tablename__ = "publications"

    id_publications: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publication_statuses: Mapped[int] = mapped_column(
        ForeignKey("publication_statuses.id_publication_statuses")
    )
    id_formats: Mapped[int] = mapped_column(ForeignKey("formats.id_formats"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicationMedia(Base):
    __tablename__ = "publication_media"

    id_publication_media: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publications: Mapped[int] = mapped_column(ForeignKey("publications.id_publications"))
    id_media: Mapped[int] = mapped_column(ForeignKey("media.id_media"))
    carousel_position: Mapped[int] = mapped_column(SmallInteger)


class PublicationTarget(Base):
    __tablename__ = "publication_targets"

    id_publication_targets: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publications: Mapped[int] = mapped_column(ForeignKey("publications.id_publications"))
    id_social_accounts: Mapped[int] = mapped_column(
        ForeignKey("social_accounts.id_social_accounts")
    )
    description_publication_targets: Mapped[str | None] = mapped_column(Text)
    current_scheduled_at_denormalized: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    id_delivery_statuses: Mapped[int] = mapped_column(
        ForeignKey("delivery_statuses.id_delivery_statuses")
    )
    id_social_posts: Mapped[int | None] = mapped_column(
        ForeignKey("social_posts.id_social_posts")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HistoryPublication(Base):
    __tablename__ = "history_publications"

    id_history_publications: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publications: Mapped[int] = mapped_column(ForeignKey("publications.id_publications"))
    id_publication_event_types: Mapped[int] = mapped_column(
        ForeignKey("publication_event_types.id_publication_event_types")
    )
    id_publication_statuses: Mapped[int] = mapped_column(
        ForeignKey("publication_statuses.id_publication_statuses")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    id_users_changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
    commentaires_users: Mapped[str | None] = mapped_column(Text)


class HistoryPublicationTarget(Base):
    __tablename__ = "history_publication_targets"

    id_history_publication_targets: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publication_targets: Mapped[int] = mapped_column(
        ForeignKey("publication_targets.id_publication_targets")
    )
    id_delivery_event_types: Mapped[int] = mapped_column(
        ForeignKey("delivery_event_types.id_delivery_event_types")
    )
    id_delivery_statuses: Mapped[int] = mapped_column(
        ForeignKey("delivery_statuses.id_delivery_statuses")
    )
    new_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_description_publication_targets: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    id_users_changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id_users"))
    commentaires_users: Mapped[str | None] = mapped_column(Text)
    error_message_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
