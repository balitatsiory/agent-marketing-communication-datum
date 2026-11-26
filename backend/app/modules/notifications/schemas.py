"""Schémas Pydantic du module Notifications."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_notifications: int
    id_users_recipient: int
    id_users_actor: int | None
    actor_name: str | None = None
    actor_initials: str | None = None
    notification_type: str
    notification_type_label: str
    source_scope: str
    platform_code: str | None
    title: str
    body: str
    requires_action: bool
    action_label: str | None
    action_url: str | None
    entity_type: str | None
    entity_id: int | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationStatsRead(BaseModel):
    total: int
    unread: int
    action_required: int
    internal_count: int
    platform_count: int
    by_type: dict[str, int]
    by_platform: dict[str, int]
    pending_actions: list[NotificationRead]


class MarkAllReadResponse(BaseModel):
    updated: int
