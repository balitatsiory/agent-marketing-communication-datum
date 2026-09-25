"""Codes des tables de référence du module, et leurs valeurs initiales.

Les codes sont **techniques et stables** : le code Python s'appuie sur eux, jamais sur
l'identifiant numérique. Les libellés, eux, se modifient librement en base.
"""

from enum import StrEnum


class PlatformCode(StrEnum):
    """Réseaux connus. Tous ne sont pas activés."""

    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class SocialAccountStatusCode(StrEnum):
    """État d'un compte raccordé."""

    CONNECTED = "connected"
    NEEDS_RECONNECT = "needs_reconnect"
    DISCONNECTED = "disconnected"


class TokenKind(StrEnum):
    """Nature du jeton conservé. Valeur technique et figée."""

    PAGE = "page"
    USER = "user"
    SYSTEM_USER = "system_user"


# Valeurs initiales, posées par migration.
# LinkedIn, TikTok et YouTube figurent dès maintenant : le cahier des charges les
# prévoit (F-05), mais ils restent désactivés tant qu'aucun connecteur n'existe.
PLATFORMS: list[dict[str, object]] = [
    {
        "code": PlatformCode.FACEBOOK.value,
        "label": "Facebook",
        "is_enabled": True,
        "api_base_url": "https://graph.facebook.com",
        "api_version": "v26.0",
        "max_caption_length": 63206,
        "sort_order": 1,
    },
    {
        "code": PlatformCode.INSTAGRAM.value,
        "label": "Instagram",
        "is_enabled": True,
        "api_base_url": "https://graph.facebook.com",
        "api_version": "v26.0",
        "max_caption_length": 2200,
        "sort_order": 2,
    },
    {
        "code": PlatformCode.LINKEDIN.value,
        "label": "LinkedIn",
        "is_enabled": False,
        "api_base_url": "https://api.linkedin.com",
        "api_version": None,
        "max_caption_length": 3000,
        "sort_order": 3,
    },
    {
        "code": PlatformCode.TIKTOK.value,
        "label": "TikTok",
        "is_enabled": False,
        "api_base_url": "https://open.tiktokapis.com",
        "api_version": None,
        "max_caption_length": 2200,
        "sort_order": 4,
    },
    {
        "code": PlatformCode.YOUTUBE.value,
        "label": "YouTube",
        "is_enabled": False,
        "api_base_url": "https://www.googleapis.com/youtube",
        "api_version": "v3",
        "max_caption_length": 5000,
        "sort_order": 5,
    },
]

SOCIAL_ACCOUNT_STATUSES: list[dict[str, object]] = [
    {"code": SocialAccountStatusCode.CONNECTED.value, "label": "Connecté", "sort_order": 1},
    {
        "code": SocialAccountStatusCode.NEEDS_RECONNECT.value,
        "label": "À reconnecter",
        "sort_order": 2,
    },
    {
        "code": SocialAccountStatusCode.DISCONNECTED.value,
        "label": "Déconnecté",
        "sort_order": 3,
    },
]
