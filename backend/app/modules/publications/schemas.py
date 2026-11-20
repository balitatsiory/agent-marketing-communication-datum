"""Formats d'entrée et de sortie du module Publications."""

from datetime import datetime

from pydantic import BaseModel, Field


class PublicationFormatRead(BaseModel):
    """Un format de publication et les plateformes qui l'acceptent."""

    code: str
    label: str
    min_media_count: int
    max_media_count: int
    is_enabled: bool
    sort_order: int
    platforms: list[str] = Field(default_factory=list)


class PublicationTargetCreate(BaseModel):
    """Une cible visée (un compte réseau social, sa légende et sa date prévue)."""

    id_social_accounts: int
    description: str = Field(min_length=1, max_length=63206)
    scheduled_at: datetime


class PublicationCreate(BaseModel):
    """Création et soumission d'une publication à la validation humaine."""

    format_code: str = Field(min_length=1, max_length=40)
    media_ids: list[int] = Field(default_factory=list)
    targets: list[PublicationTargetCreate] = Field(min_length=1)


class PublicationDecision(BaseModel):
    """Décision de validation ou demande de correction."""

    comment: str | None = Field(default=None, max_length=2000)


class PublicationMediaRead(BaseModel):
    """Média rattaché à une publication, dans son ordre d'affichage."""

    id_media: int
    carousel_position: int
    display_name: str
    file_type: str
    url: str


class PublicationTargetRead(BaseModel):
    """Cible d'une publication et son état d'envoi."""

    id_publication_targets: int
    id_social_accounts: int
    account_display_name: str
    platform_code: str
    platform_label: str
    description: str | None
    scheduled_at: datetime
    delivery_status_code: str
    delivery_status_label: str
    id_social_posts: int | None = None
    post_external_id: str | None = None
    permalink: str | None = None
    last_error: str | None = None


class PublicationHistoryRead(BaseModel):
    """Entrée du journal d'historique de la publication."""

    event_code: str
    event_label: str
    status_code: str
    status_label: str
    changed_by_name: str | None = None
    comment: str | None = None
    created_at: datetime


class PublicationRead(BaseModel):
    """Publication complète avec ses médias, cibles et historique."""

    id_publications: int
    format_code: str
    format_label: str
    status_code: str
    status_label: str
    created_by_name: str | None = None
    media: list[PublicationMediaRead] = Field(default_factory=list)
    targets: list[PublicationTargetRead] = Field(default_factory=list)
    history: list[PublicationHistoryRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PublicationPublishResultRead(BaseModel):
    """Résultat d'une diffusion vers les plateformes."""

    ok: bool
    message: str
    published_count: int
    failed_count: int
    publication: PublicationRead
