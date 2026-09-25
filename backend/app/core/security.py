"""Mots de passe, jetons de session, chiffrement des jetons Meta.

Trois opérations à ne pas confondre :

* **mot de passe** — haché avec bcrypt, donc irréversible : on vérifie seulement
  qu'un mot de passe correspond ;
* **jeton de renouvellement** — haché avec SHA-256 : c'est une valeur aléatoire de
  grande entropie, qu'on doit pouvoir retrouver en base à partir du jeton présenté ;
* **jeton Meta** — chiffré avec Fernet, donc réversible : il faut le renvoyer à Meta
  à chaque appel.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Final

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import AuthenticationError

ALGORITHM: Final = "HS256"
# bcrypt ne prend en compte que les 72 premiers octets : au-delà, la fin du mot de
# passe serait ignorée sans prévenir. On refuse plutôt que de tronquer en silence.
MAX_PASSWORD_BYTES: Final = 72

settings = get_settings()


# ---------------------------------------------------------------------------
# Mots de passe
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hache un mot de passe. Le résultat contient le sel et le coût."""
    octets = password.encode("utf-8")
    if len(octets) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Le mot de passe dépasse {MAX_PASSWORD_BYTES} octets.")
    return bcrypt.hashpw(octets, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe face à son empreinte."""
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES], password_hash.encode())
    except ValueError:
        # Empreinte illisible : on refuse, sans faire échouer la requête.
        return False


# ---------------------------------------------------------------------------
# Jetons d'accès (JWT)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TokenPayload:
    """Contenu utile d'un jeton d'accès."""

    id_users: int
    permissions: list[str]


def create_access_token(id_users: int, permissions: list[str]) -> str:
    """Crée un jeton d'accès de courte durée."""
    maintenant = datetime.now(UTC)
    contenu: dict[str, Any] = {
        "sub": str(id_users),
        "perms": permissions,
        "type": "access",
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(contenu, settings.JWT_SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Lit un jeton d'accès. Lève AuthenticationError s'il est expiré ou falsifié."""
    try:
        contenu = jwt.decode(
            token, settings.JWT_SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM]
        )
    except jwt.ExpiredSignatureError as erreur:
        raise AuthenticationError("Votre session a expiré, reconnectez-vous.") from erreur
    except jwt.PyJWTError as erreur:
        raise AuthenticationError("Jeton d'authentification invalide.") from erreur

    if contenu.get("type") != "access":
        raise AuthenticationError("Jeton d'authentification invalide.")

    return TokenPayload(id_users=int(contenu["sub"]), permissions=list(contenu.get("perms", [])))


# ---------------------------------------------------------------------------
# Jetons de renouvellement
# ---------------------------------------------------------------------------
def generate_refresh_token() -> str:
    """Valeur aléatoire remise au client. Elle n'est jamais stockée telle quelle."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Empreinte du jeton, stockée en base.

    SHA-256 et non bcrypt : l'empreinte doit être déterministe pour retrouver la
    session à partir du jeton présenté, et la valeur est déjà imprévisible.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    """Date d'expiration d'un nouveau jeton de renouvellement."""
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_DAYS)


# ---------------------------------------------------------------------------
# Chiffrement des jetons de plateformes (Meta)
# ---------------------------------------------------------------------------
@lru_cache
def _fernet() -> Fernet:
    """Construit l'outil de chiffrement au premier usage, pas au démarrage."""
    return Fernet(settings.TOKEN_ENCRYPTION_KEY.get_secret_value().encode("utf-8"))


def encrypt_token(clair: str) -> str:
    """Chiffre un jeton de plateforme avant de le stocker."""
    return _fernet().encrypt(clair.encode("utf-8")).decode("utf-8")


def decrypt_token(chiffre: str) -> str:
    """Déchiffre un jeton de plateforme pour appeler l'API."""
    try:
        return _fernet().decrypt(chiffre.encode("utf-8")).decode("utf-8")
    except InvalidToken as erreur:
        raise ValueError(
            "Jeton illisible : la clé de chiffrement a changé ou la valeur est corrompue."
        ) from erreur
