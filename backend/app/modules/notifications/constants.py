"""Constantes du module Notifications."""

SOURCE_INTERNAL = "internal"
SOURCE_PLATFORM = "platform"
SOURCES_VALIDES = (SOURCE_INTERNAL, SOURCE_PLATFORM)

TYPE_VALIDATION_REQUEST = "validation_request"
TYPE_CORRECTION_SUGGESTED = "correction_suggested"
TYPE_PUBLICATION_APPROVED = "publication_approved"
TYPE_PUBLICATION_PUBLISHED = "publication_published"
TYPE_PUBLICATION_FAILED = "publication_failed"
TYPE_MESSAGE_REPLY = "message_reply"
TYPE_ACCOUNT_ALERT = "account_alert"
TYPE_WEBINAR_REMINDER = "webinar_reminder"
TYPE_TEAM_ACTIVITY = "team_activity"

TYPES_NOTIFICATION_VALIDES = (
    TYPE_VALIDATION_REQUEST,
    TYPE_CORRECTION_SUGGESTED,
    TYPE_PUBLICATION_APPROVED,
    TYPE_PUBLICATION_PUBLISHED,
    TYPE_PUBLICATION_FAILED,
    TYPE_MESSAGE_REPLY,
    TYPE_ACCOUNT_ALERT,
    TYPE_WEBINAR_REMINDER,
    TYPE_TEAM_ACTIVITY,
)

LIBELLES_TYPES_NOTIFICATION: dict[str, str] = {
    TYPE_VALIDATION_REQUEST: "Demandes de validation",
    TYPE_CORRECTION_SUGGESTED: "Corrections suggérées",
    TYPE_PUBLICATION_APPROVED: "Publications approuvées",
    TYPE_PUBLICATION_PUBLISHED: "Publications publiées",
    TYPE_PUBLICATION_FAILED: "Échecs de publication",
    TYPE_MESSAGE_REPLY: "Messages & commentaires",
    TYPE_ACCOUNT_ALERT: "Alertes comptes",
    TYPE_WEBINAR_REMINDER: "Rappels webinaires",
    TYPE_TEAM_ACTIVITY: "Activité équipe",
}
