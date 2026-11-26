"""Schémas Pydantic du module Publications et cycle de validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidatorOptionRead(BaseModel):
    id_users: int
    full_name: str
    initials: str
    email: str
    is_self: bool = False


class PublicationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_publication_events: int
    id_publications: int
    kind: str
    label: str
    comment: str | None
    id_users_author: int | None
    author_name: str
    author_initials: str
    created_at: datetime


class PublicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    caption: str = Field(default="")
    captions_by_platform: dict[str, str] | None = None
    format_code: str = Field(default="image", max_length=40)
    platform_codes: list[str] = Field(min_length=1)
    hashtags: list[str] | None = None
    media_items: list[dict[str, Any]] | None = None
    scheduled_at: datetime | None = None
    id_users_validator: int | None = None
    submit_for_validation: bool = False


class PublicationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    caption: str | None = None
    captions_by_platform: dict[str, str] | None = None
    platform_codes: list[str] | None = None
    hashtags: list[str] | None = None
    scheduled_at: datetime | None = None
    id_users_validator: int | None = None


class SubmitValidationInput(BaseModel):
    id_users_validator: int | None = None
    comment: str | None = None


class CommentInput(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class ApprovePublicationInput(BaseModel):
    publish_now: bool = False
    comment: str | None = Field(default=None, max_length=2000)


class PublicationSummaryRead(BaseModel):
    id_publications: int
    title: str
    caption: str
    format_code: str
    status_code: str
    platform_codes: list[str]
    hashtags: list[str]
    scheduled_at: datetime | None
    published_at: datetime | None
    id_users_author: int
    author_name: str
    author_initials: str
    id_users_validator: int | None
    validator_name: str | None
    comment_count: int
    created_at: datetime
    updated_at: datetime


class PublicationDetailRead(PublicationSummaryRead):
    captions_by_platform: dict[str, str] | None
    media_items: list[dict[str, Any]] | None
    events: list[PublicationEventRead]
