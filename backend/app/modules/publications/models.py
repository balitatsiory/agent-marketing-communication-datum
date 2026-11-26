"""Tables du module Publications et historique de validation."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.publications.constants import EVENTS_VALIDES, FORMATS_VALIDES, STATUTS_VALIDES


class Publication(Base):
    """Publication programmée ou en cours de validation."""

    __tablename__ = "publication_workflows"
    __table_args__ = (
        CheckConstraint(
            "format_code IN ('" + "', '".join(FORMATS_VALIDES) + "')",
            name="format_code_valide",
        ),
        CheckConstraint(
            "status_code IN ('" + "', '".join(STATUTS_VALIDES) + "')",
            name="status_code_valide",
        ),
        Index("ix_publication_workflows_status", "status_code"),
        Index("ix_publication_workflows_author", "id_users_author"),
        {
            "comment": (
                "Publications multi-reseaux et leur cycle de validation "
                "(brouillon, a valider, corrections demandees, programmee, publiee)."
            )
        },
    )

    id_publications: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    captions_by_platform: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)
    format_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status_code: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    platform_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    media_items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_users_author: Mapped[int] = mapped_column(
        ForeignKey("users.id_users"),
        nullable=False,
    )
    id_users_validator: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublicationEvent(Base):
    """Étape du journal de validation ou commentaire sur une publication."""

    __tablename__ = "publication_workflow_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('" + "', '".join(EVENTS_VALIDES) + "')",
            name="publication_workflow_event_kind_valide",
        ),
        Index("ix_publication_workflow_events_publication", "id_publications", "created_at"),
        {
            "comment": (
                "Journal de validation d'une publication : soumissions, "
                "suggestions de correction en commentaire, approbations et publications."
            )
        },
    )

    id_publication_events: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_publications: Mapped[int] = mapped_column(
        ForeignKey("publication_workflows.id_publications", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_users_author: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
