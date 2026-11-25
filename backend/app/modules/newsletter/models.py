"""Tables du module Newsletter : modèles de mail et envois.

Six tables, dont deux référentiels (`mail_categories`, `newsletter_send_statuses`)
et un historique en ajout seul (`mail_template_versions`).

Ce que les modèles ne portent pas, et que seule la migration 0010 pose : les
déclencheurs `updated_at` et celui qui tient `mail_template_versions` en ajout
seul. Tout le reste — contraintes, index, commentaires — est déclaré ici À
L'IDENTIQUE de la migration : `alembic check` échoue sur le moindre écart.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.newsletter.constants import TEMPLATE_STATUSES


class MailCategory(Base):
    """Catégorie de courriel : elle classe les modèles et, par eux, les envois."""

    __tablename__ = "mail_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_mail_categories_code"),
        {
            "comment": (
                "Categories de courriel liees aux evenements. Elles classent a la fois "
                "les modeles et les envois : un envoi herite de la categorie de son modele."
            )
        },
    )

    id_mail_categories: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la categorie."
    )
    code: Mapped[str] = mapped_column(
        String(40), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(120), comment="Libelle affiche dans l'interface.")
    note: Mapped[str] = mapped_column(
        String(255), comment="Ce que la categorie sert a dire, affiche sous son titre."
    )
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, comment="Ordre d'affichage : celui du cycle de vie d'un evenement."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de derniere modification (UTC).",
    )


class NewsletterSendStatus(Base):
    """État d'un envoi. Déduit du résultat, jamais saisi."""

    __tablename__ = "newsletter_send_statuses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_newsletter_send_statuses_code"),
        {
            "comment": (
                "Etats d'un envoi : envoye, programme, envoye en partie, echec. "
                "L'etat est DEDUIT du resultat de l'envoi, jamais saisi."
            )
        },
    )

    id_newsletter_send_statuses: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de l'etat."
    )
    code: Mapped[str] = mapped_column(
        String(40), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(120), comment="Libelle affiche dans l'interface.")
    sort_order: Mapped[int] = mapped_column(SmallInteger, comment="Ordre d'affichage des filtres.")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de derniere modification (UTC).",
    )


class MailTemplate(Base):
    """Un modèle de courriel : son objet et son corps, insérés dans la coquille commune."""

    __tablename__ = "mail_templates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "', '".join(TEMPLATE_STATUSES) + "')",
            name="status",
        ),
        Index(
            "uq_mail_templates_name",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "comment": (
                "Modeles de courriel. Le corps est insere dans la coquille commune : "
                "la banniere et la signature ne sont donc pas recopiees a chaque modele."
            )
        },
    )

    id_mail_templates: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du modele."
    )
    id_mail_categories: Mapped[int] = mapped_column(
        ForeignKey(
            "mail_categories.id_mail_categories",
            name="fk_mail_templates_id_mail_categories_mail_categories",
        ),
        comment="Categorie du modele. Les envois en heritent.",
    )
    name: Mapped[str] = mapped_column(String(160), comment="Nom du modele dans la liste.")
    subject: Mapped[str] = mapped_column(
        String(200), comment="Objet du message, variables comprises."
    )
    preheader: Mapped[str | None] = mapped_column(
        String(255), comment="Premiere ligne visible dans la liste de la boite de reception."
    )
    body_html: Mapped[str] = mapped_column(
        Text,
        comment=(
            "Corps du message, insere dans la coquille commune (banniere et "
            "signature). Les variables s'y ecrivent entre doubles accolades."
        ),
    )
    variables_json: Mapped[list[str] | None] = mapped_column(
        JSONB, comment="Variables attendues par le modele, sans les accolades."
    )
    status: Mapped[str] = mapped_column(
        String(20),
        server_default="draft",
        comment="draft (non proposable a l'envoi) | published.",
    )
    version_label: Mapped[str] = mapped_column(
        String(20),
        server_default="v1",
        comment="Version courante, recopiee sur chaque envoi produit.",
    )
    is_standard: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="Modele livre avec l'application, cree par l'installation des standards.",
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_mail_templates_id_users_created_by_users"),
        comment="Utilisateur qui a cree le modele.",
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_mail_templates_id_users_changed_by_users"),
        comment="Utilisateur de la derniere modification.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de derniere modification (UTC).",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Archivage : le modele disparait des listes, les envois y renvoient toujours.",
    )


class MailTemplateVersion(Base):
    """Une version enregistrée d'un modèle. Historique en ajout seul."""

    __tablename__ = "mail_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "id_mail_templates", "label", name="uq_mail_template_versions_id_mail_templates"
        ),
        {
            "comment": (
                "Historique des versions d'un modele, en ajout seul. Chaque "
                "enregistrement du modele y depose l'etat precedent."
            )
        },
    )

    id_mail_template_versions: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la version."
    )
    id_mail_templates: Mapped[int] = mapped_column(
        ForeignKey(
            "mail_templates.id_mail_templates",
            name="fk_mail_template_versions_id_mail_templates_mail_templates",
            ondelete="CASCADE",
        ),
        comment="Modele concerne. Ses versions disparaissent avec lui.",
    )
    label: Mapped[str] = mapped_column(String(20), comment="Nom de la version (v1, v2...).")
    subject: Mapped[str] = mapped_column(String(200), comment="Objet, tel qu'a cette date.")
    preheader: Mapped[str | None] = mapped_column(
        String(255), comment="Pre-entete, tel qu'a cette date."
    )
    body_html: Mapped[str] = mapped_column(Text, comment="Corps, tel qu'a cette date.")
    change_note: Mapped[str | None] = mapped_column(
        Text, comment="Ce que cette version a change, saisi par l'auteur."
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_mail_template_versions_id_users_created_by_users"),
        comment="Utilisateur qui a enregistre la version.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )


class NewsletterSend(Base):
    """Un envoi : le message parti, le compte qui l'a expédié, ses cumuls."""

    __tablename__ = "newsletter_sends"
    __table_args__ = (
        CheckConstraint("delivered_count <= recipient_count", name="delivered_count"),
        Index("ix_newsletter_sends_id_email_accounts", "id_email_accounts"),
        {
            "comment": (
                "Un envoi de newsletter : le message parti, le compte qui l'a expedie "
                "et ses cumuls de remise."
            )
        },
    )

    id_newsletter_sends: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de l'envoi."
    )
    id_mail_templates: Mapped[int | None] = mapped_column(
        ForeignKey(
            "mail_templates.id_mail_templates",
            name="fk_newsletter_sends_id_mail_templates_mail_templates",
        ),
        comment="Modele utilise. Vide si le modele a ete archive depuis.",
    )
    id_mail_categories: Mapped[int] = mapped_column(
        ForeignKey(
            "mail_categories.id_mail_categories",
            name="fk_newsletter_sends_id_mail_categories_mail_categories",
        ),
        comment="Categorie, heritee du modele au moment de l'envoi.",
    )
    id_email_accounts: Mapped[int] = mapped_column(
        ForeignKey(
            "email_accounts.id_email_accounts",
            name="fk_newsletter_sends_id_email_accounts_email_accounts",
        ),
        comment="Compte d'envoi qui a expedie les messages.",
    )
    id_newsletter_send_statuses: Mapped[int] = mapped_column(
        ForeignKey(
            "newsletter_send_statuses.id_newsletter_send_statuses",
            name="fk_newsletter_sends_status",
        ),
        comment="Etat de l'envoi.",
    )
    subject: Mapped[str] = mapped_column(
        String(200), comment="Objet reellement expedie, variables substituees."
    )
    event_title: Mapped[str | None] = mapped_column(
        String(200), comment="Evenement auquel l'envoi se rattache."
    )
    template_name_denormalized: Mapped[str] = mapped_column(
        String(160),
        comment="Nom du modele AU MOMENT de l'envoi : le modele peut etre renomme depuis.",
    )
    template_version_denormalized: Mapped[str] = mapped_column(
        String(20), comment="Version du modele au moment de l'envoi."
    )
    recipient_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), comment="Destinataires vises."
    )
    delivered_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        comment=(
            "Messages acceptes par le serveur d'envoi. C'est tout ce qu'un serveur "
            "SMTP rend : ni ouvertures ni clics ne transitent par lui."
        ),
    )
    failure_note: Mapped[str | None] = mapped_column(
        Text, comment="Renseigne quand l'envoi a echoue, en tout ou partie."
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Date prevue d'un envoi programme (UTC)."
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Moment ou l'envoi a ete tente (UTC). Vide tant qu'il est programme.",
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_newsletter_sends_id_users_created_by_users"),
        comment="Utilisateur qui a declenche l'envoi.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Date de derniere modification (UTC).",
    )


class NewsletterSendRecipient(Base):
    """Le détail par destinataire : accepté ou refusé, et pourquoi."""

    __tablename__ = "newsletter_send_recipients"
    __table_args__ = (
        UniqueConstraint(
            "id_newsletter_sends", "email", name="uq_newsletter_send_recipients_id_newsletter_sends"
        ),
        {
            "comment": (
                "Detail par destinataire d'un envoi : accepte ou refuse, et le motif "
                "du refus. C'est de ces lignes que viennent les cumuls de l'envoi."
            )
        },
    )

    id_newsletter_send_recipients: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la ligne destinataire."
    )
    id_newsletter_sends: Mapped[int] = mapped_column(
        ForeignKey(
            "newsletter_sends.id_newsletter_sends",
            name="fk_newsletter_send_recipients_send",
            ondelete="CASCADE",
        ),
        comment="Envoi concerne. Ses destinataires disparaissent avec lui.",
    )
    email: Mapped[str] = mapped_column(
        String(255), comment="Adresse du destinataire, toujours en minuscules."
    )
    display_name: Mapped[str | None] = mapped_column(
        String(120), comment="Nom du destinataire, utilise par la variable prenom."
    )
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="Vrai si le serveur d'envoi a accepte le message pour cette adresse.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, comment="Refus du serveur pour cette adresse, tel qu'il l'a formule."
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Moment de la tentative pour cette adresse (UTC)."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="Date de creation (UTC)."
    )
