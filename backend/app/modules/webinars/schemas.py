"""Schémas Pydantic du module Webinaires."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.modules.webinars.constants import ZOOM_PASSCODE_PATTERN, ZOOM_TOPIC_MAX

LinkMode = Literal["zoom_auto", "manual"]
RegistrationMode = Literal["none", "zoom_page", "iagora_form", "external"]
Origin = Literal["manual", "zoom_sync", "site_import"]
SortKey = Literal["date", "title", "registrations", "created"]
SortDirection = Literal["asc", "desc"]


def _adresse_web(valeur: str) -> str:
    """Seules les adresses http(s) sont admises : elles finissent dans des liens."""
    morceaux = urlsplit(valeur)
    if morceaux.scheme not in ("http", "https") or not morceaux.netloc:
        raise ValueError("L'adresse doit commencer par http:// ou https://.")
    return valeur


WebUrl = Annotated[str, Field(max_length=1024), AfterValidator(_adresse_web)]
# Un nom de personne : ni balise ni retour à la ligne, il finit dans des courriels.
PersonName = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[^<>\x00-\x1f]+$")]


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


class RefItem(BaseModel):
    code: str
    label: str


class CountItem(BaseModel):
    code: str
    label: str
    count: int


class WebinarReferenceRead(BaseModel):
    """Listes de valeurs des écrans Webinaires."""

    statuses: list[RefItem]
    types: list[RefItem]
    categories: list[RefItem]
    publication_types: list[RefItem]
    platforms: list[RefItem]


# ---------------------------------------------------------------------------
# Publications liées et pages d'inscription
# ---------------------------------------------------------------------------


class PublicationLinkCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type_code: str = Field(..., max_length=40)
    url: WebUrl
    platform_code: str | None = Field(default=None, max_length=40)
    label: str | None = Field(default=None, max_length=200)


class PublicationLinkRead(BaseModel):
    id_webinar_publication_links: int
    type_code: str
    type_label: str
    platform_code: str | None
    platform_label: str | None
    url: str
    label: str | None
    created_by_name: str | None
    created_at: datetime


class RegistrationPageRead(BaseModel):
    id_webinar_registration_pages: int
    kind: str
    slug: str
    url: str | None
    is_active: bool
    id_webinars: int | None
    webinar_title: str | None
    id_webinars_candidate: int | None
    candidate_title: str | None
    candidate_score: float | None
    event_starts_at: datetime | None
    event_ends_at: datetime | None
    note: str | None


class RegistrationPageLink(BaseModel):
    """Rattache une page à un webinaire, ou la détache (`null`)."""

    id_webinars: int | None


# ---------------------------------------------------------------------------
# Webinaires
# ---------------------------------------------------------------------------


class MeetingSettings(BaseModel):
    """Réglages d'une réunion créée sur Zoom."""

    passcode: str | None = Field(default=None, pattern=ZOOM_PASSCODE_PATTERN)
    waiting_room: bool = True
    join_before_host: bool = False
    mute_upon_entry: bool = True
    host_video: bool = True
    participant_video: bool = False
    auto_recording: Literal["none", "local", "cloud"] = "none"
    email_notification: bool = Field(
        default=True, description="Zoom envoie la confirmation à chaque inscrit."
    )


class WebinarCreate(BaseModel):
    """Création d'une fiche. Elle naît en brouillon : seul le titre est exigé."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=ZOOM_TOPIC_MAX)
    description: str | None = Field(default=None, max_length=10_000)
    category_codes: list[str] = Field(default_factory=list, max_length=20)
    starts_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    timezone: str | None = Field(default=None, max_length=64)
    link_mode: LinkMode = "zoom_auto"
    id_zoom_accounts: int | None = None
    join_url: WebUrl | None = None
    registration_mode: RegistrationMode = "none"
    registration_url: WebUrl | None = None
    replay_url: WebUrl | None = None
    meeting_settings: MeetingSettings = Field(default_factory=MeetingSettings)
    publication_links: list[PublicationLinkCreate] = Field(default_factory=list, max_length=30)


class WebinarUpdate(BaseModel):
    """Modification partielle : seuls les champs envoyés changent."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    category_codes: list[str] | None = Field(default=None, max_length=20)
    starts_at: AwareDatetime | None = None
    is_date_confirmed: bool | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    timezone: str | None = Field(default=None, max_length=64)
    link_mode: LinkMode | None = None
    id_zoom_accounts: int | None = None
    join_url: WebUrl | None = None
    registration_mode: RegistrationMode | None = None
    registration_url: WebUrl | None = None
    replay_url: WebUrl | None = None
    meeting_settings: MeetingSettings | None = None


class WebinarListItem(BaseModel):
    id_webinars: int
    title: str
    status_code: str = Field(..., description="État effectif : « passé » se déduit de la date.")
    status_label: str
    type_code: str
    type_label: str
    origin: Origin
    categories: list[RefItem]
    id_zoom_accounts: int | None
    zoom_account_label: str | None
    external_zoom_meeting_id: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_date_confirmed: bool
    is_time_known: bool
    published_on: date | None
    duration_minutes: int | None
    join_url: str | None
    registration_mode: RegistrationMode
    registration_url: str | None
    form_slug: str | None = Field(..., description="Slug du formulaire IAGORA, s'il y en a un.")
    replay_url: str | None
    flyer_url: str | None
    registration_count: int | None = Field(
        ..., description="`null` quand les inscriptions sont inconnues (reprise du site)."
    )
    excerpt: str | None


class DailyCount(BaseModel):
    day: date
    count: int


class WebinarDetailRead(WebinarListItem):
    title_en: str | None
    description: str | None
    description_en: str | None
    timezone: str | None
    link_mode: LinkMode
    meeting_settings: MeetingSettings | None
    zoom_meeting: dict[str, Any] | None = Field(
        ..., description="Dernière fiche lue sur Zoom, sans lien d'animation ni mot de passe."
    )
    zoom_synced_at: datetime | None
    source_url: str | None
    flyer_source_url: str | None
    flyer_error: str | None
    anomalies: list[str]
    date_hint: str | None = Field(..., description="Origine d'une date restant à valider.")
    registration_pages: list[RegistrationPageRead]
    publication_links: list[PublicationLinkRead]
    consented_count: int
    registration_series: list[DailyCount]
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime


class MonthCount(BaseModel):
    month: str = Field(..., description="AAAA-MM.")
    count: int


class AccountStats(BaseModel):
    id_zoom_accounts: int | None
    label: str
    total: int
    scheduled: int
    past: int
    draft: int


class WebinarStatsRead(BaseModel):
    """Chiffres généraux, pour un compte ou cumulés."""

    total: int
    scheduled: int
    past: int
    draft: int
    cancelled: int
    by_type: list[CountItem]
    by_category: list[CountItem]
    by_month: list[MonthCount]
    accounts: list[AccountStats]
    registrations: int
    consented_registrations: int
    with_replay: int
    dates_to_confirm: int
    pending_flyers: int
    next_webinar: WebinarListItem | None


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------


class ZoomSyncRequest(BaseModel):
    id_zoom_accounts: int | None = Field(default=None, description="Vide : tous les comptes.")


class ZoomSyncAccountResult(BaseModel):
    id_zoom_accounts: int
    label: str
    ok: bool
    message: str
    found: int = 0
    created: int = 0
    updated: int = 0


class ZoomSyncResult(BaseModel):
    accounts: list[ZoomSyncAccountResult]


class ZoomMeetingImport(BaseModel):
    """Lecture d'une réunion précise, par son numéro."""

    id_zoom_accounts: int
    meeting_id: str = Field(
        ..., max_length=20, pattern=r"^[0-9 ]{9,20}$", description="Numéro, espaces admis."
    )


# ---------------------------------------------------------------------------
# Inscriptions
# ---------------------------------------------------------------------------


class RegistrationCreate(BaseModel):
    """Inscription saisie par l'équipe."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    first_name: PersonName
    last_name: PersonName
    has_newsletter_consent: bool = False


class RegistrationUpdate(BaseModel):
    has_newsletter_consent: bool


class RegistrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_webinar_registrations: int
    email: str | None
    first_name: str | None
    last_name: str | None
    source: str
    has_newsletter_consent: bool
    registered_at: datetime
    zoom_status: str | None
    zoom_join_url: str | None
    zoom_error: str | None
    anonymized_at: datetime | None


class RegistrantSyncResult(BaseModel):
    found: int
    created: int
    updated: int


class NewsletterAudienceItem(BaseModel):
    email: str
    display_name: str | None


class NewsletterAudienceRead(BaseModel):
    """Destinataires d'une newsletter : les seuls inscrits ayant consenti."""

    id_webinars: int
    title: str
    items: list[NewsletterAudienceItem]
    excluded_without_consent: int


class PublicPageRead(BaseModel):
    """Ce que voit un visiteur anonyme du formulaire."""

    title: str
    description: str | None
    starts_at: datetime | None
    is_time_known: bool
    duration_minutes: int | None
    flyer_url: str | None
    is_open: bool


class PublicRegistrationCreate(RegistrationCreate):
    # Champ leurre, invisible dans le formulaire : seul un robot le remplit.
    website: str | None = Field(default=None, max_length=200)


class PublicRegistrationRead(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


class ImportReport(BaseModel):
    webinars_created: int
    webinars_updated: int
    webinars_kept: int
    pages_created: int
    pages_updated: int
    dates_to_confirm: int
    pending_flyers: int
    warnings: list[str]


class FlyerError(BaseModel):
    id_webinars: int
    title: str
    message: str


class FlyerBatchResult(BaseModel):
    stored: int
    failed: int
    remaining: int
    errors: list[FlyerError]
