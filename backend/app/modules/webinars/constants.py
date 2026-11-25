"""Constantes du module Webinaires."""

MANAGE_WEBINARS = "manage_webinars"
# Créer une réunion agit sur le compte Zoom de l'école, et peut déclencher des
# courriels aux inscrits : c'est un droit distinct de la gestion des fiches.
CREATE_ZOOM_MEETINGS = "create_zoom_meetings"

# Codes des référentiels, tels que la migration 0011 les sème.
STATUS_DRAFT = "draft"
STATUS_SCHEDULED = "scheduled"
STATUS_PAST = "past"
STATUS_CANCELLED = "cancelled"

TYPE_ZOOM_MEETING = "zoom_meeting"
TYPE_SITE_WEBINAR = "site_webinar"

PUBLICATION_PROMOTION = "promotion"
PUBLICATION_SUMMARY = "summary"
PUBLICATION_REPLAY = "replay"
PUBLICATION_OTHER = "other"
# Compte rendu et rediffusion n'existent qu'après la séance.
PUBLICATION_TYPES_AFTER_EVENT = (PUBLICATION_SUMMARY, PUBLICATION_REPLAY)

# Valeurs techniques figées : VARCHAR + CHECK.
ORIGIN_MANUAL = "manual"
ORIGIN_ZOOM_SYNC = "zoom_sync"
ORIGIN_SITE_IMPORT = "site_import"
ORIGINS = (ORIGIN_MANUAL, ORIGIN_ZOOM_SYNC, ORIGIN_SITE_IMPORT)

LINK_ZOOM_AUTO = "zoom_auto"
LINK_MANUAL = "manual"
LINK_MODES = (LINK_ZOOM_AUTO, LINK_MANUAL)

REGISTRATION_NONE = "none"
REGISTRATION_ZOOM_PAGE = "zoom_page"
REGISTRATION_IAGORA_FORM = "iagora_form"
REGISTRATION_EXTERNAL = "external"
REGISTRATION_MODES = (
    REGISTRATION_NONE,
    REGISTRATION_ZOOM_PAGE,
    REGISTRATION_IAGORA_FORM,
    REGISTRATION_EXTERNAL,
)
# Modes dont les inscrits sont enregistrés sur la réunion Zoom.
REGISTRATION_MODES_ON_ZOOM = (REGISTRATION_ZOOM_PAGE, REGISTRATION_IAGORA_FORM)

PAGE_EXTERNAL = "external"
PAGE_IAGORA_FORM = "iagora_form"
PAGE_KINDS = (PAGE_EXTERNAL, PAGE_IAGORA_FORM)

SOURCE_IAGORA_FORM = "iagora_form"
SOURCE_MANUAL = "manual"
SOURCE_ZOOM_SYNC = "zoom_sync"
REGISTRATION_SOURCES = (SOURCE_IAGORA_FORM, SOURCE_MANUAL, SOURCE_ZOOM_SYNC)

# `approval_type` de Zoom : 0 approbation automatique, 1 manuelle, 2 aucune
# inscription demandée.
APPROVAL_AUTOMATIC = 0
APPROVAL_NONE = 2

ZOOM_MEETING_TYPE_SCHEDULED = 2
# Durée supposée quand elle n'est pas connue, pour décider qu'un événement est passé.
DEFAULT_DURATION_MINUTES = 60

# Pagination des listes de Zoom : 300 est son maximum, et le plafond de pages
# évite qu'une réponse anormale fasse tourner la synchronisation sans fin.
ZOOM_PAGE_SIZE = 300
ZOOM_PAGES_MAX = 20
ZOOM_LIST_TYPES = ("scheduled", "previous_meetings")
ZOOM_REGISTRANT_STATUSES = ("approved", "pending")

# Limites de saisie reprises de Zoom.
ZOOM_TOPIC_MAX = 200
ZOOM_AGENDA_MAX = 2000
ZOOM_PASSCODE_PATTERN = r"^[A-Za-z0-9@\-_*]{1,10}$"

# Import des fichiers du site : au-delà, ce n'est plus l'export attendu.
IMPORT_FILE_MAX_BYTES = 5 * 1024 * 1024

# Rapatriement des flyers : seul le site de l'école est interrogé, pour qu'un
# fichier d'import ne puisse pas faire appeler une adresse quelconque au serveur.
FLYER_ALLOWED_HOSTS = ("datumacademy.com", "www.datumacademy.com")
FLYER_MAX_BYTES = 10 * 1024 * 1024
FLYER_TIMEOUT_SECONDS = 30.0
FLYER_BATCH_MAX = 20
# Format reconnu par Pillow → type MIME.
FLYER_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}

# Nombre de jours de la courbe d'inscriptions d'une fiche.
REGISTRATION_SERIES_DAYS = 30
