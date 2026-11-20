"""Formats d'entrée et de sortie du module Comptes réseaux sociaux.

Les jetons chiffrés ne sortent JAMAIS dans un schéma de lecture : l'interface
ne voit que leur présence, leur type et leur date d'expiration.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlatformMetricRead(BaseModel):
    """Mesure de compte exposée par une plateforme."""

    code: str
    label: str
    nature: str
    is_summable: bool
    platform_metric_name: str


class SocialPlatformRead(BaseModel):
    """Plateforme sociale et ses capacités techniques."""

    model_config = ConfigDict(from_attributes=True)

    id_social_platforms: int
    code: str
    label: str
    is_enabled: bool
    api_version: str | None
    max_description_length: int | None
    supports_event_polling: bool
    supports_account_metrics: bool
    allows_automated_message_reply: bool
    message_response_window_hours: int | None
    sort_order: int
    supported_metrics: list[PlatformMetricRead] = Field(default_factory=list)


class SocialAccountStatusRead(BaseModel):
    """État possible d'un compte raccordé."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    sort_order: int


class SocialAccountErrorCauseRead(BaseModel):
    """Cause de panne traduite dans le vocabulaire d'IAGORA."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    recommended_action: str


class SocialAccountMetricsSummary(BaseModel):
    """Synthèse des mesures connues pour l'affichage en liste.

    Un champ à `None` signifie « pas encore relevé » ou « non fourni par ce
    réseau » (à croiser avec `supported_metrics` de la plateforme), jamais zéro.
    """

    followers: int | None = None
    reach: int | None = None
    views_30d: int | None = None
    interactions_30d: int | None = None
    last_metric_date: date | None = None
    last_collected_at: datetime | None = None
    posts_30d: int = 0


class SocialAccountRead(BaseModel):
    """Compte réseau social raccordé à IAGORA."""

    id_social_accounts: int
    platform_code: str
    platform_label: str
    status_code: str
    status_label: str
    id_social_accounts_parent: int | None
    parent_display_name: str | None = None
    parent_platform_code: str | None = None
    account_external_id: str
    account_display_name: str
    account_username: str | None
    profile_url: str | None
    credential_mode: str
    error_cause: SocialAccountErrorCauseRead | None = None
    current_error_message: str | None = None
    has_active_token: bool = False
    token_kind: str | None = None
    token_expires_at: datetime | None = None
    metrics: SocialAccountMetricsSummary = Field(default_factory=SocialAccountMetricsSummary)
    created_at: datetime
    updated_at: datetime


class SocialAccountCreate(BaseModel):
    """Raccordement manuel d'un compte (mode « own » ou « inherited »)."""

    platform_code: str = Field(min_length=1, max_length=40)
    account_display_name: str = Field(min_length=1, max_length=255)
    account_username: str | None = Field(default=None, max_length=120)
    account_external_id: str = Field(min_length=1, max_length=120)
    profile_url: str | None = Field(default=None, max_length=512)
    credential_mode: Literal["own", "inherited"] = "own"
    id_social_accounts_parent: int | None = None
    access_token: str | None = Field(default=None, min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)
    token_kind: str | None = Field(default=None, max_length=40)
    obtained_at: datetime | None = None
    access_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None

    @model_validator(mode="after")
    def verifier_mode_cles(self) -> "SocialAccountCreate":
        if self.credential_mode == "inherited":
            if self.id_social_accounts_parent is None:
                raise ValueError("Un compte hérité exige un compte parent.")
        elif not self.access_token or not self.access_token.strip():
            raise ValueError("Un jeton d'accès est obligatoire en mode « own ».")
        return self


class SocialAccountReconnect(BaseModel):
    """Nouvelle délivrance de clés pour un compte existant (rotation)."""

    access_token: str = Field(min_length=1)
    refresh_token: str | None = Field(default=None, min_length=1)
    token_kind: str | None = Field(default=None, max_length=40)
    obtained_at: datetime | None = None
    access_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None


class SocialAccountVerifyRead(BaseModel):
    """Résultat d'une vérification en direct d'un compte auprès de la plateforme."""

    verified: bool
    message: str
    platform_name: str | None = None
    platform_username: str | None = None
    platform_url: str | None = None
    granted_permissions: list[str] | None = None
    missing_permissions: list[str] = Field(default_factory=list)
    raw_error: str | None = None
    account: SocialAccountRead


class SocialStatisticTypeRead(BaseModel):
    """Une mesure du vocabulaire fermé, avec son support pour la plateforme du compte."""

    code: str
    label: str
    description: str | None
    nature: str
    is_summable: bool
    supported_by_platform: bool
    platform_metric_name: str | None = None


class StatisticPointRead(BaseModel):
    """Un point quotidien d'une série statistique."""

    metric_date: date
    collected_at: datetime
    value: int


class SocialAccountStatisticsRead(BaseModel):
    """Séries statistiques d'un compte sur une fenêtre donnée."""

    days: int
    metric_types: list[SocialStatisticTypeRead]
    series: dict[str, list[StatisticPointRead]]


class SocialAccountSyncStatsRead(BaseModel):
    """Résultat d'une collecte manuelle des statistiques."""

    ok: bool
    synced_days: int
    message: str
    raw_error: str | None = None
    account: SocialAccountRead


class SocialAccountTokenRead(BaseModel):
    """Une délivrance de clés dans l'historique (sans jamais exposer les secrets)."""

    id_social_account_tokens: int
    token_kind: str | None
    obtained_at: datetime
    access_expires_at: datetime | None
    superseded_at: datetime | None
    revoked_at: datetime | None
    granted_permissions: list[str] = Field(default_factory=list)
    created_by_name: str | None = None
    is_active: bool


class SocialAccountSyncRead(BaseModel):
    """Un passage enregistré dans `social_account_syncs`."""

    id_social_account_syncs: int
    sync_kind: str
    started_at: datetime
    finished_at: datetime | None
    sync_outcome: str | None
    covered_until_date: date | None
    error_cause_code: str | None = None
    error_cause_label: str | None = None
    retry_after: datetime | None
    triggered_by_name: str | None = None


class SocialPostRead(BaseModel):
    """Une publication parue sur le réseau (`social_posts`)."""

    id_social_posts: int
    post_external_id: str
    permalink: str | None
    published_at: datetime | None
    archived_on_platform_at: datetime | None
    archived_by_name: str | None = None
    deleted_on_platform_at: datetime | None
    created_at: datetime


class SocialAccountSyncPostsRead(BaseModel):
    """Résultat d'un import des publications déjà parues sur la plateforme."""

    ok: bool
    imported_count: int
    total_fetched: int
    message: str
    raw_error: str | None = None
    posts: list[SocialPostRead] = Field(default_factory=list)
