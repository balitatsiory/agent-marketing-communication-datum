"""Codes des droits portés par ce module."""

MANAGE_MEDIA = "manage_media"
MANAGE_MEDIA_REFERENCE = "manage_media_reference"
PURGE_MEDIA = "purge_media"

# Image d'une référence rapatriée depuis une adresse saisie. Au-delà du plafond
# rangé elle est compressée, comme un dépôt ; au-delà de celui-ci, refusée.
IMAGE_LINK_MAX_BYTES = 20 * 1024 * 1024
IMAGE_LINK_TIMEOUT_SECONDS = 20.0

# Reprise des logos d'organisations.
LOGO_NATURE_CODE = "logo"
LOGO_ALLOWED_HOSTS = ("datumacademy.com", "www.datumacademy.com")
LOGO_TIMEOUT_SECONDS = 30.0
