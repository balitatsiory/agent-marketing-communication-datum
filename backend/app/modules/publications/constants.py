"""Constantes du module Publications et validation."""

FORMATS_VALIDES = (
    "reel",
    "video",
    "image",
    "carousel",
    "story",
    "document",
    "text",
)

STATUT_DRAFT = "draft"
STATUT_REVIEW = "review"
STATUT_CHANGES_REQUESTED = "changes_requested"
STATUT_APPROVED = "approved"
STATUT_SCHEDULED = "scheduled"
STATUT_PUBLISHED = "published"
STATUT_PARTIALLY_PUBLISHED = "partiallyPublished"
STATUT_FAILED = "failed"
STATUT_WITHDRAWN = "withdrawn"

STATUTS_VALIDES = (
    STATUT_DRAFT,
    STATUT_REVIEW,
    STATUT_CHANGES_REQUESTED,
    STATUT_APPROVED,
    STATUT_SCHEDULED,
    STATUT_PUBLISHED,
    STATUT_PARTIALLY_PUBLISHED,
    STATUT_FAILED,
    STATUT_WITHDRAWN,
)

EVENT_CREATED = "created"
EVENT_SUBMITTED = "submitted"
EVENT_COMMENT = "comment"
EVENT_CHANGES_REQUESTED = "changes_requested"
EVENT_APPROVED = "approved"
EVENT_SCHEDULED = "scheduled"
EVENT_MODIFIED = "modified"
EVENT_PUBLISHED = "published"
EVENT_FAILED = "failed"
EVENT_WITHDRAWN = "withdrawn"

EVENTS_VALIDES = (
    EVENT_CREATED,
    EVENT_SUBMITTED,
    EVENT_COMMENT,
    EVENT_CHANGES_REQUESTED,
    EVENT_APPROVED,
    EVENT_SCHEDULED,
    EVENT_MODIFIED,
    EVENT_PUBLISHED,
    EVENT_FAILED,
    EVENT_WITHDRAWN,
)
