"""Schémas Pydantic du module Newsletter."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

TemplateStatus = Literal["draft", "published"]


# ---------------------------------------------------------------------------
# Référentiels
# ---------------------------------------------------------------------------


class MailCategoryRead(BaseModel):
    """Une catégorie de courriel, telle que l'écran la montre."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    note: str
    sort_order: int


class SendStatusRead(BaseModel):
    """Un état d'envoi."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    sort_order: int


# ---------------------------------------------------------------------------
# Modèles de mail
# ---------------------------------------------------------------------------


class MailTemplateCreate(BaseModel):
    """Création d'un modèle. Le corps n'est que le CORPS : pas de bannière."""

    category_code: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=160)
    subject: str = Field(..., min_length=1, max_length=200)
    preheader: str | None = Field(default=None, max_length=255)
    body_html: str = Field(..., min_length=1)
    status: TemplateStatus = "draft"


class MailTemplateUpdate(BaseModel):
    """Modification d'un modèle. Chaque enregistrement crée une version."""

    category_code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    preheader: str | None = Field(default=None, max_length=255)
    body_html: str | None = Field(default=None, min_length=1)
    status: TemplateStatus | None = None
    change_note: str | None = Field(default=None, max_length=500)


class MailTemplateRead(BaseModel):
    """Fiche d'un modèle."""

    model_config = ConfigDict(from_attributes=True)

    id_mail_templates: int
    category_code: str
    category_label: str
    category_note: str
    name: str
    subject: str
    preheader: str | None
    body_html: str
    variables: list[str]
    status: TemplateStatus
    version_label: str
    is_standard: bool
    usage_count: int
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class MailTemplateVersionRead(BaseModel):
    """Une version enregistrée d'un modèle."""

    model_config = ConfigDict(from_attributes=True)

    id_mail_template_versions: int
    label: str
    subject: str
    change_note: str | None
    author_name: str | None = None
    created_at: datetime


class MailTemplatePreviewRead(BaseModel):
    """Le message tel qu'il partira, variables substituées."""

    subject: str
    preheader: str
    html: str
    text: str
    variables: list[str]
    missing_variables: list[str] = Field(
        default_factory=list,
        description=(
            "Variables du modèle qu'aucune valeur ne renseigne : elles partiraient telles quelles."
        ),
    )


class MailTemplatePreviewRequest(BaseModel):
    """Valeurs à injecter dans l'aperçu. Vide = valeurs d'exemple."""

    variables: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Envois
# ---------------------------------------------------------------------------


class NewsletterRecipientCreate(BaseModel):
    """Un destinataire d'un envoi."""

    email: EmailStr
    display_name: str | None = Field(default=None, max_length=120)


class NewsletterSendCreate(BaseModel):
    """Déclenchement d'un envoi depuis un modèle publié."""

    id_mail_templates: int
    id_email_accounts: int | None = Field(
        default=None, description="Compte expéditeur. Vide = le compte d'envoi actif."
    )
    event_title: str | None = Field(default=None, max_length=200)
    recipients: list[NewsletterRecipientCreate] = Field(..., min_length=1)
    variables: dict[str, str] = Field(default_factory=dict)


class NewsletterSendRecipientRead(BaseModel):
    """Le sort d'un destinataire dans un envoi."""

    model_config = ConfigDict(from_attributes=True)

    email: str
    display_name: str | None
    is_delivered: bool
    error_message: str | None
    sent_at: datetime | None


class NewsletterSendRead(BaseModel):
    """Une ligne de la boîte d'envois."""

    model_config = ConfigDict(from_attributes=True)

    id_newsletter_sends: int
    category_code: str
    category_label: str
    status_code: str
    status_label: str
    subject: str
    event_title: str | None
    template_name: str
    template_version: str
    id_mail_templates: int | None
    id_email_accounts: int
    account_label: str
    account_from_email: str
    recipient_count: int
    delivered_count: int
    bounce_count: int
    delivery_rate: int
    failure_note: str | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    created_by_name: str | None = None
    created_at: datetime


class NewsletterSendDetailRead(NewsletterSendRead):
    """La fiche d'un envoi, avec le détail par destinataire et le message parti."""

    recipients: list[NewsletterSendRecipientRead]
    html: str | None = None


class CompteRead(BaseModel):
    """Un décompte par code, pour les filtres de la boîte d'envois."""

    code: str
    label: str
    count: int


class NewsletterStatsRead(BaseModel):
    """Chiffres d'en-tête de la boîte d'envois.

    Les cumuls ne portent que sur les envois TENTÉS : mêler les envois
    programmés ferait chuter le taux de remise sans raison.
    """

    sends: int
    attempted: int
    targeted: int
    delivered: int
    bounced: int
    delivery_rate: int
    needing_attention: int
    by_category: list[CompteRead]
    by_status: list[CompteRead]
    computed_at: datetime
