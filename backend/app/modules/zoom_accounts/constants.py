"""Constantes du module Comptes Zoom."""

MANAGE_ZOOM_ACCOUNTS = "manage_zoom_accounts"

# Nature d'une vérification consignée dans l'historique.
CHECK_CONNECTION = "connection"
CHECK_TOKEN_REFRESH = "token_refresh"
CHECK_KINDS = (CHECK_CONNECTION, CHECK_TOKEN_REFRESH)

# Droits Zoom (« scopes » granulaires) dont l'application a besoin, et à quoi
# sert chacun. La fiche d'un compte montre ceux que le jeton ne porte pas : un
# droit oublié sur marketplace.zoom.us se voit ainsi avant le premier échec.
SCOPE_LIST_MEETINGS = "meeting:read:list_meetings:admin"
SCOPE_READ_MEETING = "meeting:read:meeting:admin"
SCOPE_WRITE_MEETING = "meeting:write:meeting:admin"
SCOPE_WRITE_REGISTRANT = "meeting:write:registrant:admin"
SCOPE_LIST_REGISTRANTS = "meeting:read:list_registrants:admin"

REQUIRED_SCOPES: dict[str, str] = {
    SCOPE_LIST_MEETINGS: "Lister les réunions",
    SCOPE_READ_MEETING: "Voir le détail d'une réunion",
    SCOPE_WRITE_MEETING: "Créer une réunion",
    SCOPE_WRITE_REGISTRANT: "Inscrire un participant",
    SCOPE_LIST_REGISTRANTS: "Lister les inscrits",
}

# Un jeton Server-to-Server vaut une heure. On le renouvelle un peu avant son
# terme : un jeton qui expire pendant l'appel produirait une erreur évitable.
TOKEN_EXPIRY_MARGIN_SECONDS = 60

# Délai d'attente d'un appel à Zoom.
ZOOM_TIMEOUT_SECONDS = 20.0

CLIENT_SECRET_LENGTH_MIN = 8
CLIENT_SECRET_LENGTH_MAX = 255
