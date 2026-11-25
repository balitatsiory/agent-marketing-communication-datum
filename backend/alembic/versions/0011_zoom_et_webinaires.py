"""Comptes Zoom et webinaires.

Comptes Zoom :
- `zoom_accounts`, `zoom_account_credentials` (secrets chiffrés),
  `zoom_account_checks` (historique en ajout seul).

Webinaires :
- référentiels `webinar_statuses`, `webinar_types`, `webinar_categories`,
  `webinar_publication_types` ;
- `webinars`, `webinar_category_links`, `webinar_registration_pages`,
  `webinar_registrations`, `webinar_publication_links`.

Insère les droits `manage_zoom_accounts` (900), `manage_webinars` (910) et
`create_zoom_meetings` (920).

`set_updated_at()` vient de la migration 0001, `refuser_reecriture()` de la 0009.

Révision : 0011
Révision précédente : 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = (
    ("draft", "Brouillon", 10),
    ("scheduled", "À venir", 20),
    ("past", "Passé", 30),
    ("cancelled", "Annulé", 40),
)
TYPES = (
    ("zoom_meeting", "Réunion Zoom", 10),
    ("site_webinar", "Webinaire (hors Zoom)", 20),
)
CATEGORIES = (
    ("ai_and_big_data", "AI and BIG DATA", 10),
    ("programs_presentation", "Programs Presentation", 20),
)
PUBLICATION_TYPES = (
    ("promotion", "Promotion du webinaire", 10),
    ("summary", "Compte rendu", 20),
    ("replay", "Rediffusion", 30),
    ("other", "Autre", 40),
)
PERMISSIONS = (
    (
        "manage_zoom_accounts",
        "Gerer les comptes Zoom",
        "Raccorder les comptes Zoom, remplacer leurs secrets et tester la connexion.",
        900,
    ),
    (
        "manage_webinars",
        "Gerer les webinaires",
        "Creer et modifier les fiches, importer, synchroniser et consulter les inscrits.",
        910,
    ),
    (
        "create_zoom_meetings",
        "Creer des reunions Zoom",
        "Valider un webinaire en creant sa reunion sur le compte Zoom.",
        920,
    ),
)

# Tables dont `updated_at` est tenu par déclencheur.
TABLES_HORODATEES = (
    "zoom_accounts",
    "webinar_statuses",
    "webinar_types",
    "webinar_categories",
    "webinar_publication_types",
    "webinars",
    "webinar_category_links",
    "webinar_registration_pages",
    "webinar_registrations",
    "webinar_publication_links",
)


def _id(nom: str, commentaire: str) -> sa.Column:
    return sa.Column(
        nom, sa.Integer, sa.Identity(always=False), nullable=False, comment=commentaire
    )


def _date(nom: str, commentaire: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        nom,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.func.now(),
        comment=commentaire,
    )


def _horodatages() -> tuple[sa.Column, sa.Column]:
    return (
        _date("created_at", "Date de creation (UTC)."),
        _date("updated_at", "Date de derniere modification (UTC)."),
    )


def _colonne(
    nom: str,
    genre: sa.types.TypeEngine,
    commentaire: str,
    nullable: bool = True,
    defaut: sa.sql.elements.TextClause | sa.sql.elements.ColumnElement | str | None = None,
) -> sa.Column:
    return sa.Column(nom, genre, nullable=nullable, server_default=defaut, comment=commentaire)


def _referentiel(
    table: str, cle: str, commentaire: str, longueur_code: int, longueur_libelle: int
) -> None:
    op.create_table(
        table,
        _id(cle, "Identifiant."),
        _colonne(
            "code",
            sa.String(longueur_code),
            "Code technique lu par le code Python. Ne change jamais.",
            False,
        ),
        _colonne(
            "label", sa.String(longueur_libelle), "Libelle affiche dans l'interface.", False
        ),
        _colonne("sort_order", sa.SmallInteger, "Ordre d'affichage.", False),
        *_horodatages(),
        sa.PrimaryKeyConstraint(cle, name=f"pk_{table}"),
        sa.UniqueConstraint("code", name=f"uq_{table}_code"),
        comment=commentaire,
    )


def _zoom() -> None:
    op.create_table(
        "zoom_accounts",
        _id("id_zoom_accounts", "Identifiant du compte Zoom."),
        _colonne(
            "label", sa.String(120), "Nom lisible du compte, affiche dans l'interface.", False
        ),
        _colonne(
            "host_email",
            sa.String(255),
            "Adresse Zoom de la personne hote, en minuscules. Les reunions sont listees "
            "et creees a son nom.",
            False,
        ),
        _colonne(
            "external_zoom_account_id",
            sa.String(128),
            "Account ID de l'application, lu sur marketplace.zoom.us.",
            False,
        ),
        _colonne("client_id", sa.String(255), "Client ID de l'application.", False),
        _colonne(
            "granted_scopes_json",
            postgresql.JSONB,
            "Droits Zoom portes par le dernier jeton obtenu.",
        ),
        _colonne(
            "access_token_encrypted",
            sa.Text,
            "Dernier jeton d'acces, chiffre par Fernet. Valable une heure.",
        ),
        _date("access_token_obtained_at", "Date d'obtention du dernier jeton (UTC).", True),
        _date("access_token_expires_at", "Expiration du dernier jeton (UTC).", True),
        _date(
            "last_verified_at", "Date de la derniere verification (UTC), reussie ou non.", True
        ),
        _colonne(
            "last_verify_ok",
            sa.Boolean,
            "Resultat de la derniere verification. Vide si aucune n'a eu lieu.",
        ),
        _colonne(
            "last_verify_message",
            sa.Text,
            "Compte rendu de la derniere verification, affiche tel quel.",
        ),
        _colonne("id_users_created_by", sa.Integer, "Utilisateur qui a enregistre le compte."),
        _colonne(
            "id_users_changed_by", sa.Integer, "Utilisateur de la derniere modification."
        ),
        *_horodatages(),
        _date(
            "deleted_at",
            "Archivage du compte : il n'est plus propose, ses webinaires restent.",
            True,
        ),
        sa.PrimaryKeyConstraint("id_zoom_accounts", name="pk_zoom_accounts"),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_zoom_accounts_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_zoom_accounts_id_users_changed_by_users",
        ),
        comment=(
            "Comptes Zoom (applications Server-to-Server OAuth). Le Client Secret n'est "
            "pas ici : il vit chiffre dans zoom_account_credentials."
        ),
    )
    op.create_index(
        "uq_zoom_accounts_identifiant",
        "zoom_accounts",
        ["external_zoom_account_id", "host_email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "zoom_account_credentials",
        _id("id_zoom_account_credentials", "Identifiant de la delivrance du secret."),
        _colonne("id_zoom_accounts", sa.Integer, "Compte Zoom concerne.", False),
        _colonne(
            "client_secret_encrypted",
            sa.Text,
            "Chiffre par Fernet (TOKEN_ENCRYPTION_KEY). Le secret en clair ne touche "
            "jamais le disque.",
            False,
        ),
        _colonne(
            "client_secret_masked",
            sa.String(40),
            "Apercu masque sans secret, pour que l'interface montre qu'il existe.",
            False,
        ),
        _date("obtained_at", "Date de saisie du secret (UTC)."),
        _date("superseded_at", "Remplacement par un secret plus recent.", True),
        _date(
            "revoked_at",
            "Retrait sans remplacement : le compte ne peut plus appeler Zoom.",
            True,
        ),
        _colonne("id_users_created_by", sa.Integer, "Utilisateur qui a saisi le secret."),
        _date("created_at", "Date de creation (UTC)."),
        sa.PrimaryKeyConstraint(
            "id_zoom_account_credentials", name="pk_zoom_account_credentials"
        ),
        sa.ForeignKeyConstraint(
            ["id_zoom_accounts"],
            ["zoom_accounts.id_zoom_accounts"],
            name="fk_zoom_account_credentials_id_zoom_accounts_zoom_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_zoom_account_credentials_id_users_created_by_users",
        ),
        comment=(
            "Client Secret des comptes Zoom, chiffres par Fernet. Un changement cree "
            "une nouvelle ligne et marque la precedente remplacee."
        ),
    )
    op.create_index(
        "uq_zoom_account_credentials_actif",
        "zoom_account_credentials",
        ["id_zoom_accounts"],
        unique=True,
        postgresql_where=sa.text("superseded_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "zoom_account_checks",
        _id("id_zoom_account_checks", "Identifiant de la verification."),
        _colonne("id_zoom_accounts", sa.Integer, "Compte verifie.", False),
        _colonne(
            "kind",
            sa.String(20),
            "connection (jeton + appel reel) | token_refresh (nouveau jeton seul).",
            False,
        ),
        _colonne("is_ok", sa.Boolean, "Vrai si Zoom a accepte l'operation.", False),
        _colonne(
            "message", sa.Text, "Compte rendu en francais, affiche tel quel dans l'interface."
        ),
        _colonne(
            "latency_ms", sa.Integer, "Duree de l'echange avec Zoom, en millisecondes."
        ),
        _date("checked_at", "Moment de la verification (UTC)."),
        _colonne(
            "id_users_checked_by",
            sa.Integer,
            "Utilisateur qui a declenche la verification.",
        ),
        sa.PrimaryKeyConstraint("id_zoom_account_checks", name="pk_zoom_account_checks"),
        sa.CheckConstraint(
            "kind IN ('connection', 'token_refresh')", name="ck_zoom_account_checks_kind"
        ),
        sa.ForeignKeyConstraint(
            ["id_zoom_accounts"],
            ["zoom_accounts.id_zoom_accounts"],
            name="fk_zoom_account_checks_id_zoom_accounts_zoom_accounts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_checked_by"],
            ["users.id_users"],
            name="fk_zoom_account_checks_id_users_checked_by_users",
        ),
        comment=(
            "Historique des verifications d'un compte Zoom : test de connexion ou "
            "renouvellement du jeton. En ajout seul."
        ),
    )


def _webinaires() -> None:
    op.create_table(
        "webinars",
        _id("id_webinars", "Identifiant du webinaire."),
        _colonne("id_webinar_statuses", sa.Integer, "Etat enregistre.", False),
        _colonne("id_webinar_types", sa.Integer, "Type d'evenement.", False),
        _colonne(
            "id_zoom_accounts",
            sa.Integer,
            "Compte Zoom porteur. Vide pour un webinaire du site ou un lien manuel.",
        ),
        _colonne(
            "origin",
            sa.String(20),
            "manual (saisi) | zoom_sync (lu sur Zoom) | site_import (repris du site).",
            False,
            "manual",
        ),
        _colonne("title", sa.String(255), "Titre (francais).", False),
        _colonne("title_en", sa.String(255), "Titre anglais."),
        _colonne("description", sa.Text, "Description (francais)."),
        _colonne("description_en", sa.Text, "Description anglaise."),
        _date("starts_at", "Debut (UTC). Vide tant que la date est inconnue.", True),
        _colonne(
            "is_date_confirmed",
            sa.Boolean,
            "Faux quand la date est deduite d'un import et reste a valider.",
            False,
            sa.true(),
        ),
        _colonne(
            "is_time_known", sa.Boolean, "Faux quand seul le jour est connu.", False, sa.true()
        ),
        _colonne(
            "published_on",
            sa.Date,
            "Date approximative de publication sur le site, a defaut de date.",
        ),
        _colonne("duration_minutes", sa.Integer, "Duree en minutes."),
        _colonne("timezone", sa.String(64), "Fuseau d'affichage transmis a Zoom."),
        _colonne(
            "link_mode",
            sa.String(20),
            "zoom_auto (reunion creee sur Zoom) | manual (lien fourni a la main).",
            False,
            "zoom_auto",
        ),
        _colonne("join_url", sa.Text, "Lien pour rejoindre la seance."),
        _colonne(
            "external_zoom_meeting_id", sa.BigInteger, "Numero de la reunion sur Zoom."
        ),
        _colonne("external_zoom_uuid", sa.String(64), "UUID Zoom de la reunion."),
        _colonne(
            "zoom_meeting_type",
            sa.SmallInteger,
            "Type Zoom : 2 programmee, 3 ou 8 recurrente.",
        ),
        _colonne(
            "meeting_settings_json",
            postgresql.JSONB,
            "Reglages demandes a la creation de la reunion.",
        ),
        _colonne(
            "zoom_snapshot_json",
            postgresql.JSONB,
            "Derniere fiche lue sur Zoom, sans lien d'animation ni secret.",
        ),
        _date("zoom_synced_at", "Derniere lecture sur Zoom (UTC).", True),
        _colonne(
            "registration_mode",
            sa.String(20),
            "none | zoom_page | iagora_form | external.",
            False,
            "none",
        ),
        _colonne(
            "registration_url",
            sa.Text,
            "Page d'inscription Zoom ou externe. Vide pour un formulaire IAGORA.",
        ),
        _colonne("replay_url", sa.Text, "Rediffusion."),
        _colonne(
            "external_site_slug", sa.String(255), "Slug de la fiche sur datumacademy.com."
        ),
        _colonne("source_url", sa.Text, "Fiche d'origine sur le site."),
        _colonne(
            "flyer_storage_key", sa.String(512), "Cle du flyer dans le stockage. Jamais d'URL."
        ),
        _colonne("flyer_source_url", sa.Text, "Adresse d'origine du flyer, a rapatrier."),
        _colonne("flyer_sha256", sa.String(64), "Empreinte du flyer."),
        _colonne("flyer_byte_size", sa.Integer, "Taille du flyer."),
        _colonne("flyer_error", sa.Text, "Echec du dernier rapatriement du flyer."),
        _colonne(
            "import_details_json",
            postgresql.JSONB,
            "Anomalies et indices de date releves par l'import.",
        ),
        _colonne(
            "id_users_created_by", sa.Integer, "Utilisateur qui a cree ou importe la fiche."
        ),
        _colonne(
            "id_users_changed_by",
            sa.Integer,
            "Utilisateur de la derniere modification manuelle.",
        ),
        *_horodatages(),
        _date("deleted_at", "Archivage : la fiche disparait des listes.", True),
        sa.PrimaryKeyConstraint("id_webinars", name="pk_webinars"),
        sa.CheckConstraint(
            "origin IN ('manual', 'zoom_sync', 'site_import')", name="ck_webinars_origin"
        ),
        sa.CheckConstraint("link_mode IN ('zoom_auto', 'manual')", name="ck_webinars_link_mode"),
        sa.CheckConstraint(
            "registration_mode IN ('none', 'zoom_page', 'iagora_form', 'external')",
            name="ck_webinars_registration_mode",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_webinars_duration_minutes",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinar_statuses"],
            ["webinar_statuses.id_webinar_statuses"],
            name="fk_webinars_id_webinar_statuses_webinar_statuses",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinar_types"],
            ["webinar_types.id_webinar_types"],
            name="fk_webinars_id_webinar_types_webinar_types",
        ),
        sa.ForeignKeyConstraint(
            ["id_zoom_accounts"],
            ["zoom_accounts.id_zoom_accounts"],
            name="fk_webinars_id_zoom_accounts_zoom_accounts",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_webinars_id_users_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_changed_by"],
            ["users.id_users"],
            name="fk_webinars_id_users_changed_by_users",
        ),
        comment=(
            "Webinaires : brouillons, reunions Zoom et webinaires repris du site "
            "datumacademy.com. « Passe » se deduit aussi de la date de fin."
        ),
    )
    op.create_index(
        "uq_webinars_external_zoom_meeting_id",
        "webinars",
        ["external_zoom_meeting_id"],
        unique=True,
        postgresql_where=sa.text("external_zoom_meeting_id IS NOT NULL"),
    )
    op.create_index(
        "uq_webinars_external_site_slug",
        "webinars",
        ["external_site_slug"],
        unique=True,
        postgresql_where=sa.text("external_site_slug IS NOT NULL"),
    )
    for colonne in ("starts_at", "id_zoom_accounts", "id_webinar_statuses"):
        op.create_index(f"ix_webinars_{colonne}", "webinars", [colonne])

    op.create_table(
        "webinar_category_links",
        _id("id_webinar_category_links", "Identifiant du rattachement."),
        _colonne("id_webinars", sa.Integer, "Webinaire.", False),
        _colonne("id_webinar_categories", sa.Integer, "Categorie.", False),
        *_horodatages(),
        sa.PrimaryKeyConstraint("id_webinar_category_links", name="pk_webinar_category_links"),
        sa.UniqueConstraint(
            "id_webinars",
            "id_webinar_categories",
            name="uq_webinar_category_links_id_webinars",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinars"],
            ["webinars.id_webinars"],
            name="fk_webinar_category_links_id_webinars_webinars",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinar_categories"],
            ["webinar_categories.id_webinar_categories"],
            name="fk_webinar_category_links_category",
        ),
        comment="Categories portees par chaque webinaire.",
    )

    op.create_table(
        "webinar_registration_pages",
        _id("id_webinar_registration_pages", "Identifiant de la page."),
        _colonne(
            "id_webinars",
            sa.Integer,
            "Webinaire rattache. Vide tant que le rattachement n'est pas etabli.",
        ),
        _colonne(
            "id_webinars_candidate",
            sa.Integer,
            "Rattachement propose par ressemblance, a valider.",
        ),
        _colonne(
            "candidate_score",
            sa.Numeric(4, 3),
            "Ressemblance du rattachement propose, entre 0 et 1.",
        ),
        _colonne("kind", sa.String(20), "external | iagora_form.", False),
        _colonne("slug", sa.String(255), "Slug de la page.", False),
        _colonne(
            "url", sa.Text, "Adresse d'une page externe. Vide pour un formulaire IAGORA."
        ),
        _colonne(
            "is_active", sa.Boolean, "La page accepte des inscriptions.", False, sa.true()
        ),
        _date("event_starts_at", "Debut annonce par la page importee.", True),
        _date("event_ends_at", "Fin annoncee par la page importee.", True),
        _colonne("note", sa.Text, "Remarque relevee a l'import."),
        *_horodatages(),
        sa.PrimaryKeyConstraint(
            "id_webinar_registration_pages", name="pk_webinar_registration_pages"
        ),
        sa.CheckConstraint(
            "kind IN ('external', 'iagora_form')", name="ck_webinar_registration_pages_kind"
        ),
        sa.UniqueConstraint("kind", "slug", name="uq_webinar_registration_pages_kind"),
        sa.ForeignKeyConstraint(
            ["id_webinars"],
            ["webinars.id_webinars"],
            name="fk_webinar_registration_pages_id_webinars_webinars",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinars_candidate"],
            ["webinars.id_webinars"],
            name="fk_webinar_registration_pages_id_webinars_candidate_webinars",
        ),
        comment=(
            "Pages d'inscription : celles du site datumacademy.com et les formulaires "
            "publics servis par IAGORA."
        ),
    )
    op.create_index(
        "ix_webinar_registration_pages_id_webinars",
        "webinar_registration_pages",
        ["id_webinars"],
    )

    op.create_table(
        "webinar_registrations",
        _id("id_webinar_registrations", "Identifiant de l'inscription."),
        _colonne("id_webinars", sa.Integer, "Webinaire.", False),
        _colonne(
            "id_webinar_registration_pages", sa.Integer, "Formulaire utilise, le cas echeant."
        ),
        _colonne(
            "email", sa.String(255), "Adresse, en minuscules. Vide apres anonymisation."
        ),
        _colonne("first_name", sa.String(120), "Prenom."),
        _colonne("last_name", sa.String(120), "Nom de famille."),
        _colonne("source", sa.String(20), "iagora_form | manual | zoom_sync.", False),
        _colonne(
            "has_newsletter_consent",
            sa.Boolean,
            "Accord pour recevoir les newsletters. Sans lui, aucun envoi.",
            False,
            sa.false(),
        ),
        _date("consented_at", "Date de l'accord (UTC).", True),
        _colonne(
            "external_zoom_registrant_id", sa.String(128), "Identifiant de l'inscrit sur Zoom."
        ),
        _colonne("zoom_join_url", sa.Text, "Lien personnel delivre par Zoom."),
        _colonne("zoom_status", sa.String(20), "Etat sur Zoom : approved, pending."),
        _colonne("zoom_error", sa.Text, "Echec de l'inscription sur Zoom, a retenter."),
        _date("registered_at", "Date de l'inscription (UTC)."),
        _date("anonymized_at", "Date d'effacement des donnees personnelles.", True),
        *_horodatages(),
        sa.PrimaryKeyConstraint("id_webinar_registrations", name="pk_webinar_registrations"),
        sa.CheckConstraint(
            "source IN ('iagora_form', 'manual', 'zoom_sync')",
            name="ck_webinar_registrations_source",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinars"],
            ["webinars.id_webinars"],
            name="fk_webinar_registrations_id_webinars_webinars",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinar_registration_pages"],
            ["webinar_registration_pages.id_webinar_registration_pages"],
            name="fk_webinar_registrations_page",
        ),
        comment=(
            "Inscrits aux webinaires. Les adresses consenties alimentent les "
            "newsletters. Sur demande d'effacement, nom et adresse sont vides."
        ),
    )
    op.create_index(
        "uq_webinar_registrations_adresse",
        "webinar_registrations",
        ["id_webinars", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "webinar_publication_links",
        _id("id_webinar_publication_links", "Identifiant du lien."),
        _colonne("id_webinars", sa.Integer, "Webinaire.", False),
        _colonne("id_webinar_publication_types", sa.Integer, "Role de la publication.", False),
        _colonne("id_social_platforms", sa.Integer, "Reseau ou la publication est parue."),
        _colonne("url", sa.String(1024), "Adresse de la publication.", False),
        _colonne("label", sa.String(200), "Intitule libre."),
        _colonne("id_users_created_by", sa.Integer, "Utilisateur qui a pose le lien."),
        *_horodatages(),
        sa.PrimaryKeyConstraint(
            "id_webinar_publication_links", name="pk_webinar_publication_links"
        ),
        sa.UniqueConstraint(
            "id_webinars", "url", name="uq_webinar_publication_links_id_webinars"
        ),
        sa.ForeignKeyConstraint(
            ["id_webinars"],
            ["webinars.id_webinars"],
            name="fk_webinar_publication_links_id_webinars_webinars",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_webinar_publication_types"],
            ["webinar_publication_types.id_webinar_publication_types"],
            name="fk_webinar_publication_links_type",
        ),
        sa.ForeignKeyConstraint(
            ["id_social_platforms"],
            ["social_platforms.id_social_platforms"],
            name="fk_webinar_publication_links_platform",
        ),
        sa.ForeignKeyConstraint(
            ["id_users_created_by"],
            ["users.id_users"],
            name="fk_webinar_publication_links_id_users_created_by_users",
        ),
        comment=(
            "Publications liees a un webinaire, par leur adresse. Une cle vers "
            "publications les remplacera quand ce module sera integre."
        ),
    )


def upgrade() -> None:
    _zoom()
    _referentiel(
        "webinar_statuses",
        "id_webinar_statuses",
        "Etats d'un webinaire : brouillon, a venir, passe, annule.",
        40,
        80,
    )
    _referentiel(
        "webinar_types",
        "id_webinar_types",
        "Types d'evenement : reunion Zoom, webinaire du site datumacademy.com.",
        40,
        80,
    )
    _referentiel(
        "webinar_categories",
        "id_webinar_categories",
        "Categories thematiques des webinaires.",
        60,
        120,
    )
    _referentiel(
        "webinar_publication_types",
        "id_webinar_publication_types",
        "Roles d'une publication liee : promotion, compte rendu, rediffusion, autre.",
        40,
        80,
    )
    # Les commentaires de colonnes des référentiels sont propres à chaque modèle.
    for table, cle, commentaire in (
        ("webinar_statuses", "id_webinar_statuses", "Identifiant de l'etat."),
        ("webinar_types", "id_webinar_types", "Identifiant du type."),
        ("webinar_categories", "id_webinar_categories", "Identifiant de la categorie."),
        ("webinar_publication_types", "id_webinar_publication_types", "Identifiant du role."),
    ):
        op.alter_column(table, cle, comment=commentaire, existing_comment="Identifiant.")
    _webinaires()

    for table in TABLES_HORODATEES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )
    op.execute("REVOKE UPDATE, DELETE ON zoom_account_checks FROM PUBLIC")
    op.execute("REVOKE DELETE ON zoom_account_credentials FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_zoom_account_checks_ajout_seul "
        "BEFORE UPDATE OR DELETE ON zoom_account_checks "
        "FOR EACH ROW EXECUTE FUNCTION refuser_reecriture()"
    )
    op.execute(
        "CREATE TRIGGER trg_zoom_account_credentials_ajout_seul "
        "BEFORE DELETE ON zoom_account_credentials "
        "FOR EACH ROW EXECUTE FUNCTION refuser_reecriture()"
    )

    for table, lignes in (
        ("webinar_statuses", STATUSES),
        ("webinar_types", TYPES),
        ("webinar_categories", CATEGORIES),
        ("webinar_publication_types", PUBLICATION_TYPES),
    ):
        for code, label, rang in lignes:
            op.execute(
                sa.text(
                    f"INSERT INTO {table} (code, label, sort_order) "
                    "VALUES (:c, :l, :r) ON CONFLICT (code) DO NOTHING"
                ).bindparams(c=code, l=label, r=rang)
            )
    for code, label, description, rang in PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, label, description, sort_order) "
                "VALUES (:c, :l, :d, :r) ON CONFLICT (code) DO NOTHING"
            ).bindparams(c=code, l=label, d=description, r=rang)
        )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, *_ in PERMISSIONS)
    # Les attributions d'abord : un droit accordé est référencé par user_permissions.
    op.execute(
        "DELETE FROM user_permissions WHERE id_permissions IN "
        f"(SELECT id_permissions FROM permissions WHERE code IN ({codes}))"
    )
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")
    for table in (
        "webinar_publication_links",
        "webinar_registrations",
        "webinar_registration_pages",
        "webinar_category_links",
        "webinars",
        "webinar_publication_types",
        "webinar_categories",
        "webinar_types",
        "webinar_statuses",
        "zoom_account_checks",
        "zoom_account_credentials",
        "zoom_accounts",
    ):
        # DROP TABLE emporte ses index et ses déclencheurs.
        op.drop_table(table)
