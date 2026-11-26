"""Modules 04 Notifications et 08 Publications (cycle de validation).

Trois tables : publications, publication_events, notifications.

Révision : 0012
Révision précédente : 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES_VALIDES = ("internal", "platform")
TYPES_NOTIFICATION_VALIDES = (
    "validation_request",
    "correction_suggested",
    "publication_approved",
    "publication_published",
    "publication_failed",
    "message_reply",
    "account_alert",
    "webinar_reminder",
    "team_activity",
)
FORMATS_VALIDES = ("reel", "video", "image", "carousel", "story", "document", "text")
STATUTS_VALIDES = (
    "draft",
    "review",
    "changes_requested",
    "approved",
    "scheduled",
    "published",
    "partiallyPublished",
    "failed",
    "withdrawn",
)
EVENTS_VALIDES = (
    "created",
    "submitted",
    "comment",
    "changes_requested",
    "approved",
    "scheduled",
    "modified",
    "published",
    "failed",
    "withdrawn",
)


def upgrade() -> None:
    op.create_table(
        "publication_workflows",
        sa.Column("id_publications", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("caption", sa.Text, nullable=False),
        sa.Column("captions_by_platform", postgresql.JSONB, nullable=True),
        sa.Column("format_code", sa.String(40), nullable=False),
        sa.Column("status_code", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("platform_codes", postgresql.JSONB, nullable=False),
        sa.Column("hashtags", postgresql.JSONB, nullable=False),
        sa.Column("media_items", postgresql.JSONB, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id_users_author", sa.Integer, nullable=False),
        sa.Column("id_users_validator", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_publications", name="pk_publication_workflows"),
        sa.ForeignKeyConstraint(
            ["id_users_author"],
            ["users.id_users"],
            name="fk_publication_workflows_id_users_author_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_validator"],
            ["users.id_users"],
            name="fk_publication_workflows_id_users_validator_users",
        ),
        sa.CheckConstraint(
            "format_code IN ('" + "', '".join(FORMATS_VALIDES) + "')",
            name="format_code_valide",
        ),
        sa.CheckConstraint(
            "status_code IN ('" + "', '".join(STATUTS_VALIDES) + "')",
            name="status_code_valide",
        ),
        comment=(
            "Publications multi-reseaux et leur cycle de validation "
            "(brouillon, a valider, corrections demandees, programmee, publiee)."
        ),
    )
    op.create_index("ix_publication_workflows_status", "publication_workflows", ["status_code"])
    op.create_index("ix_publication_workflows_author", "publication_workflows", ["id_users_author"])

    op.execute(
        "CREATE TRIGGER trg_publication_workflows_updated_at BEFORE UPDATE ON publication_workflows "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "publication_workflow_events",
        sa.Column("id_publication_events", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_publications", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("id_users_author", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_publication_events", name="pk_publication_workflow_events"),
        sa.ForeignKeyConstraint(
            ["id_publications"],
            ["publication_workflows.id_publications"],
            name="fk_publication_workflow_events_id_publications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_author"],
            ["users.id_users"],
            name="fk_publication_workflow_events_id_users_author_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "kind IN ('" + "', '".join(EVENTS_VALIDES) + "')",
            name="publication_workflow_event_kind_valide",
        ),
        comment=(
            "Journal de validation d'une publication : soumissions, "
            "suggestions de correction en commentaire, approbations et publications."
        ),
    )
    op.create_index(
        "ix_publication_workflow_events_publication",
        "publication_workflow_events",
        ["id_publications", "created_at"],
    )

    op.create_table(
        "notifications",
        sa.Column("id_notifications", sa.Integer, sa.Identity(always=False), nullable=False),
        sa.Column("id_users_recipient", sa.Integer, nullable=False),
        sa.Column("id_users_actor", sa.Integer, nullable=True),
        sa.Column("notification_type", sa.String(40), nullable=False),
        sa.Column("source_scope", sa.String(20), nullable=False),
        sa.Column("platform_code", sa.String(40), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("requires_action", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("action_label", sa.String(80), nullable=True),
        sa.Column("action_url", sa.String(255), nullable=True),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id_notifications", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["id_users_recipient"],
            ["users.id_users"],
            name="fk_notifications_id_users_recipient_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_actor"],
            ["users.id_users"],
            name="fk_notifications_id_users_actor_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "source_scope IN ('" + "', '".join(SOURCES_VALIDES) + "')",
            name="source_scope_valide",
        ),
        sa.CheckConstraint(
            "notification_type IN ('" + "', '".join(TYPES_NOTIFICATION_VALIDES) + "')",
            name="notification_type_valide",
        ),
        comment=(
            "Notifications internes (validations, corrections, equipe) et "
            "plateformes (echecs, publications, commentaires, comptes)."
        ),
    )
    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["id_users_recipient", "created_at"],
    )
    op.create_index(
        "ix_notifications_recipient_unread",
        "notifications",
        ["id_users_recipient", "is_read"],
    )
    op.create_index("ix_notifications_entity", "notifications", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_entity", table_name="notifications")
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_publication_workflow_events_publication", table_name="publication_workflow_events")
    op.drop_table("publication_workflow_events")

    op.execute("DROP TRIGGER IF EXISTS trg_publication_workflows_updated_at ON publication_workflows")
    op.drop_index("ix_publication_workflows_author", table_name="publication_workflows")
    op.drop_index("ix_publication_workflows_status", table_name="publication_workflows")
    op.drop_table("publication_workflows")
