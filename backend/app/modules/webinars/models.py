"""Tables du module Webinaires.

Quatre référentiels (`webinar_statuses`, `webinar_types`, `webinar_categories`,
`webinar_publication_types`), la fiche (`webinars`) et ses rattachements :
catégories, pages d'inscription, inscrits, publications liées.

Les contraintes, index et commentaires sont déclarés ici À L'IDENTIQUE de la
migration 0011 : `alembic check` échoue sur le moindre écart. Seuls les
déclencheurs `updated_at` vivent uniquement dans la migration.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
from app.modules.webinars.constants import (
    LINK_MODES,
    ORIGINS,
    PAGE_KINDS,
    REGISTRATION_MODES,
    REGISTRATION_SOURCES,
)


def _liste_sql(valeurs: tuple[str, ...]) -> str:
    return "'" + "', '".join(valeurs) + "'"


def _horodatage(commentaire: str) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), comment=commentaire)


class WebinarStatus(Base):
    """État d'un webinaire."""

    __tablename__ = "webinar_statuses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_webinar_statuses_code"),
        {"comment": "Etats d'un webinaire : brouillon, a venir, passe, annule."},
    )

    id_webinar_statuses: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de l'etat."
    )
    code: Mapped[str] = mapped_column(
        String(40), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(80), comment="Libelle affiche dans l'interface.")
    sort_order: Mapped[int] = mapped_column(SmallInteger, comment="Ordre d'affichage.")
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarType(Base):
    """Type d'événement : réunion Zoom, ou webinaire publié sur le site."""

    __tablename__ = "webinar_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_webinar_types_code"),
        {"comment": "Types d'evenement : reunion Zoom, webinaire du site datumacademy.com."},
    )

    id_webinar_types: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du type."
    )
    code: Mapped[str] = mapped_column(
        String(40), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(80), comment="Libelle affiche dans l'interface.")
    sort_order: Mapped[int] = mapped_column(SmallInteger, comment="Ordre d'affichage.")
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarCategory(Base):
    """Catégorie thématique."""

    __tablename__ = "webinar_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_webinar_categories_code"),
        {"comment": "Categories thematiques des webinaires."},
    )

    id_webinar_categories: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la categorie."
    )
    code: Mapped[str] = mapped_column(
        String(60), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(120), comment="Libelle affiche dans l'interface.")
    sort_order: Mapped[int] = mapped_column(SmallInteger, comment="Ordre d'affichage.")
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarPublicationType(Base):
    """Rôle d'une publication par rapport à un webinaire."""

    __tablename__ = "webinar_publication_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_webinar_publication_types_code"),
        {"comment": "Roles d'une publication liee : promotion, compte rendu, rediffusion, autre."},
    )

    id_webinar_publication_types: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du role."
    )
    code: Mapped[str] = mapped_column(
        String(40), comment="Code technique lu par le code Python. Ne change jamais."
    )
    label: Mapped[str] = mapped_column(String(80), comment="Libelle affiche dans l'interface.")
    sort_order: Mapped[int] = mapped_column(SmallInteger, comment="Ordre d'affichage.")
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class Webinar(Base):
    """Un webinaire : brouillon, réunion Zoom ou webinaire repris du site."""

    __tablename__ = "webinars"
    __table_args__ = (
        CheckConstraint(f"origin IN ({_liste_sql(ORIGINS)})", name="origin"),
        CheckConstraint(f"link_mode IN ({_liste_sql(LINK_MODES)})", name="link_mode"),
        CheckConstraint(
            f"registration_mode IN ({_liste_sql(REGISTRATION_MODES)})",
            name="registration_mode",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0", name="duration_minutes"
        ),
        # Uniques archivés compris : une synchronisation ou un import ne doit pas
        # recréer une fiche qu'on a volontairement archivée.
        Index(
            "uq_webinars_external_zoom_meeting_id",
            "external_zoom_meeting_id",
            unique=True,
            postgresql_where=text("external_zoom_meeting_id IS NOT NULL"),
        ),
        Index(
            "uq_webinars_external_site_slug",
            "external_site_slug",
            unique=True,
            postgresql_where=text("external_site_slug IS NOT NULL"),
        ),
        Index("ix_webinars_starts_at", "starts_at"),
        Index("ix_webinars_id_zoom_accounts", "id_zoom_accounts"),
        Index("ix_webinars_id_webinar_statuses", "id_webinar_statuses"),
        {
            "comment": (
                "Webinaires : brouillons, reunions Zoom et webinaires repris du site "
                "datumacademy.com. « Passe » se deduit aussi de la date de fin."
            )
        },
    )

    id_webinars: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du webinaire."
    )
    id_webinar_statuses: Mapped[int] = mapped_column(
        ForeignKey(
            "webinar_statuses.id_webinar_statuses",
            name="fk_webinars_id_webinar_statuses_webinar_statuses",
        ),
        comment="Etat enregistre.",
    )
    id_webinar_types: Mapped[int] = mapped_column(
        ForeignKey(
            "webinar_types.id_webinar_types", name="fk_webinars_id_webinar_types_webinar_types"
        ),
        comment="Type d'evenement.",
    )
    id_zoom_accounts: Mapped[int | None] = mapped_column(
        ForeignKey(
            "zoom_accounts.id_zoom_accounts", name="fk_webinars_id_zoom_accounts_zoom_accounts"
        ),
        comment="Compte Zoom porteur. Vide pour un webinaire du site ou un lien manuel.",
    )
    origin: Mapped[str] = mapped_column(
        String(20),
        server_default="manual",
        comment="manual (saisi) | zoom_sync (lu sur Zoom) | site_import (repris du site).",
    )
    title: Mapped[str] = mapped_column(String(255), comment="Titre (francais).")
    title_en: Mapped[str | None] = mapped_column(String(255), comment="Titre anglais.")
    description: Mapped[str | None] = mapped_column(Text, comment="Description (francais).")
    description_en: Mapped[str | None] = mapped_column(Text, comment="Description anglaise.")
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Debut (UTC). Vide tant que la date est inconnue."
    )
    is_date_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.true(),
        comment="Faux quand la date est deduite d'un import et reste a valider.",
    )
    is_time_known: Mapped[bool] = mapped_column(
        Boolean, server_default=func.true(), comment="Faux quand seul le jour est connu."
    )
    published_on: Mapped[date | None] = mapped_column(
        Date, comment="Date approximative de publication sur le site, a defaut de date."
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, comment="Duree en minutes.")
    timezone: Mapped[str | None] = mapped_column(
        String(64), comment="Fuseau d'affichage transmis a Zoom."
    )
    link_mode: Mapped[str] = mapped_column(
        String(20),
        server_default="zoom_auto",
        comment="zoom_auto (reunion creee sur Zoom) | manual (lien fourni a la main).",
    )
    join_url: Mapped[str | None] = mapped_column(Text, comment="Lien pour rejoindre la seance.")
    external_zoom_meeting_id: Mapped[int | None] = mapped_column(
        BigInteger, comment="Numero de la reunion sur Zoom."
    )
    external_zoom_uuid: Mapped[str | None] = mapped_column(
        String(64), comment="UUID Zoom de la reunion."
    )
    zoom_meeting_type: Mapped[int | None] = mapped_column(
        SmallInteger, comment="Type Zoom : 2 programmee, 3 ou 8 recurrente."
    )
    meeting_settings_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Reglages demandes a la creation de la reunion."
    )
    zoom_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Derniere fiche lue sur Zoom, sans lien d'animation ni secret."
    )
    zoom_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Derniere lecture sur Zoom (UTC)."
    )
    registration_mode: Mapped[str] = mapped_column(
        String(20),
        server_default="none",
        comment="none | zoom_page | iagora_form | external.",
    )
    registration_url: Mapped[str | None] = mapped_column(
        Text, comment="Page d'inscription Zoom ou externe. Vide pour un formulaire IAGORA."
    )
    replay_url: Mapped[str | None] = mapped_column(Text, comment="Rediffusion.")
    external_site_slug: Mapped[str | None] = mapped_column(
        String(255), comment="Slug de la fiche sur datumacademy.com."
    )
    source_url: Mapped[str | None] = mapped_column(Text, comment="Fiche d'origine sur le site.")
    flyer_storage_key: Mapped[str | None] = mapped_column(
        String(512), comment="Cle du flyer dans le stockage. Jamais d'URL."
    )
    flyer_source_url: Mapped[str | None] = mapped_column(
        Text, comment="Adresse d'origine du flyer, a rapatrier."
    )
    flyer_sha256: Mapped[str | None] = mapped_column(String(64), comment="Empreinte du flyer.")
    flyer_byte_size: Mapped[int | None] = mapped_column(Integer, comment="Taille du flyer.")
    flyer_error: Mapped[str | None] = mapped_column(
        Text, comment="Echec du dernier rapatriement du flyer."
    )
    import_details_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Anomalies et indices de date releves par l'import."
    )
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_webinars_id_users_created_by_users"),
        comment="Utilisateur qui a cree ou importe la fiche.",
    )
    id_users_changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_webinars_id_users_changed_by_users"),
        comment="Utilisateur de la derniere modification manuelle.",
    )
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Archivage : la fiche disparait des listes."
    )


class WebinarCategoryLink(Base):
    """Rattachement d'un webinaire à une catégorie."""

    __tablename__ = "webinar_category_links"
    __table_args__ = (
        UniqueConstraint(
            "id_webinars",
            "id_webinar_categories",
            name="uq_webinar_category_links_id_webinars",
        ),
        {"comment": "Categories portees par chaque webinaire."},
    )

    id_webinar_category_links: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du rattachement."
    )
    id_webinars: Mapped[int] = mapped_column(
        ForeignKey(
            "webinars.id_webinars",
            name="fk_webinar_category_links_id_webinars_webinars",
            ondelete="CASCADE",
        ),
        comment="Webinaire.",
    )
    id_webinar_categories: Mapped[int] = mapped_column(
        ForeignKey(
            "webinar_categories.id_webinar_categories",
            name="fk_webinar_category_links_category",
        ),
        comment="Categorie.",
    )
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarRegistrationPage(Base):
    """Une page d'inscription : externe (site Datum) ou formulaire IAGORA."""

    __tablename__ = "webinar_registration_pages"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_liste_sql(PAGE_KINDS)})", name="kind"),
        UniqueConstraint("kind", "slug", name="uq_webinar_registration_pages_kind"),
        Index("ix_webinar_registration_pages_id_webinars", "id_webinars"),
        {
            "comment": (
                "Pages d'inscription : celles du site datumacademy.com et les formulaires "
                "publics servis par IAGORA."
            )
        },
    )

    id_webinar_registration_pages: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de la page."
    )
    id_webinars: Mapped[int | None] = mapped_column(
        ForeignKey(
            "webinars.id_webinars", name="fk_webinar_registration_pages_id_webinars_webinars"
        ),
        comment="Webinaire rattache. Vide tant que le rattachement n'est pas etabli.",
    )
    id_webinars_candidate: Mapped[int | None] = mapped_column(
        ForeignKey(
            "webinars.id_webinars",
            name="fk_webinar_registration_pages_id_webinars_candidate_webinars",
        ),
        comment="Rattachement propose par ressemblance, a valider.",
    )
    candidate_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3), comment="Ressemblance du rattachement propose, entre 0 et 1."
    )
    kind: Mapped[str] = mapped_column(String(20), comment="external | iagora_form.")
    slug: Mapped[str] = mapped_column(String(255), comment="Slug de la page.")
    url: Mapped[str | None] = mapped_column(
        Text, comment="Adresse d'une page externe. Vide pour un formulaire IAGORA."
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=func.true(), comment="La page accepte des inscriptions."
    )
    event_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Debut annonce par la page importee."
    )
    event_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Fin annoncee par la page importee."
    )
    note: Mapped[str | None] = mapped_column(Text, comment="Remarque relevee a l'import.")
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarRegistration(Base):
    """Un inscrit. Données personnelles : on anonymise, on n'archive pas."""

    __tablename__ = "webinar_registrations"
    __table_args__ = (
        CheckConstraint(f"source IN ({_liste_sql(REGISTRATION_SOURCES)})", name="source"),
        Index(
            "uq_webinar_registrations_adresse",
            "id_webinars",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        {
            "comment": (
                "Inscrits aux webinaires. Les adresses consenties alimentent les "
                "newsletters. Sur demande d'effacement, nom et adresse sont vides."
            )
        },
    )

    id_webinar_registrations: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant de l'inscription."
    )
    id_webinars: Mapped[int] = mapped_column(
        ForeignKey("webinars.id_webinars", name="fk_webinar_registrations_id_webinars_webinars"),
        comment="Webinaire.",
    )
    id_webinar_registration_pages: Mapped[int | None] = mapped_column(
        ForeignKey(
            "webinar_registration_pages.id_webinar_registration_pages",
            name="fk_webinar_registrations_page",
        ),
        comment="Formulaire utilise, le cas echeant.",
    )
    email: Mapped[str | None] = mapped_column(
        String(255), comment="Adresse, en minuscules. Vide apres anonymisation."
    )
    first_name: Mapped[str | None] = mapped_column(String(120), comment="Prenom.")
    last_name: Mapped[str | None] = mapped_column(String(120), comment="Nom de famille.")
    source: Mapped[str] = mapped_column(String(20), comment="iagora_form | manual | zoom_sync.")
    has_newsletter_consent: Mapped[bool] = mapped_column(
        Boolean,
        server_default=func.false(),
        comment="Accord pour recevoir les newsletters. Sans lui, aucun envoi.",
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Date de l'accord (UTC)."
    )
    external_zoom_registrant_id: Mapped[str | None] = mapped_column(
        String(128), comment="Identifiant de l'inscrit sur Zoom."
    )
    zoom_join_url: Mapped[str | None] = mapped_column(
        Text, comment="Lien personnel delivre par Zoom."
    )
    zoom_status: Mapped[str | None] = mapped_column(
        String(20), comment="Etat sur Zoom : approved, pending."
    )
    zoom_error: Mapped[str | None] = mapped_column(
        Text, comment="Echec de l'inscription sur Zoom, a retenter."
    )
    registered_at: Mapped[datetime] = _horodatage("Date de l'inscription (UTC).")
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="Date d'effacement des donnees personnelles."
    )
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")


class WebinarPublicationLink(Base):
    """Une publication associée à un webinaire, désignée par son adresse."""

    __tablename__ = "webinar_publication_links"
    __table_args__ = (
        UniqueConstraint("id_webinars", "url", name="uq_webinar_publication_links_id_webinars"),
        {
            "comment": (
                "Publications liees a un webinaire, par leur adresse. Une cle vers "
                "publications les remplacera quand ce module sera integre."
            )
        },
    )

    id_webinar_publication_links: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Identifiant du lien."
    )
    id_webinars: Mapped[int] = mapped_column(
        ForeignKey(
            "webinars.id_webinars",
            name="fk_webinar_publication_links_id_webinars_webinars",
            ondelete="CASCADE",
        ),
        comment="Webinaire.",
    )
    id_webinar_publication_types: Mapped[int] = mapped_column(
        ForeignKey(
            "webinar_publication_types.id_webinar_publication_types",
            name="fk_webinar_publication_links_type",
        ),
        comment="Role de la publication.",
    )
    id_social_platforms: Mapped[int | None] = mapped_column(
        ForeignKey(
            "social_platforms.id_social_platforms",
            name="fk_webinar_publication_links_platform",
        ),
        comment="Reseau ou la publication est parue.",
    )
    url: Mapped[str] = mapped_column(String(1024), comment="Adresse de la publication.")
    label: Mapped[str | None] = mapped_column(String(200), comment="Intitule libre.")
    id_users_created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id_users", name="fk_webinar_publication_links_id_users_created_by_users"),
        comment="Utilisateur qui a pose le lien.",
    )
    created_at: Mapped[datetime] = _horodatage("Date de creation (UTC).")
    updated_at: Mapped[datetime] = _horodatage("Date de derniere modification (UTC).")
