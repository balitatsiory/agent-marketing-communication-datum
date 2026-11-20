"""Empreintes de mots de passe, jetons d'accès et de renouvellement.

Deux fonctions de hachage, pour deux usages qu'il ne faut pas confondre :

- **bcrypt** pour les mots de passe. Un mot de passe humain est court et
  devinable : il faut un hachage volontairement LENT, qui rende une attaque par
  force brute coûteuse.
- **SHA-256** pour les jetons de renouvellement. Un jeton est une valeur
  aléatoire de 64 caractères, impossible à deviner, et il est vérifié à CHAQUE
  renouvellement : un hachage lent y serait un coût sans contrepartie.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import ApiError, NotAuthenticatedError

ALGORITHME = "HS256"

# bcrypt tronque silencieusement au-delà de 72 octets : les caractères suivants
# ne comptent pas. On refuse explicitement plutôt que d'accepter un mot de passe
# dont la fin serait ignorée.
MOT_DE_PASSE_OCTETS_MAX = 72


def hash_password(mot_de_passe: str) -> str:
    """Calcule l'empreinte bcrypt d'un mot de passe."""
    brut = mot_de_passe.encode("utf-8")
    if len(brut) > MOT_DE_PASSE_OCTETS_MAX:
        raise ApiError(
            "password_too_long",
            f"Le mot de passe ne doit pas dépasser {MOT_DE_PASSE_OCTETS_MAX} octets "
            "(les caractères accentués en comptent deux).",
        )
    return bcrypt.hashpw(brut, bcrypt.gensalt()).decode("utf-8")


def verify_password(mot_de_passe: str, empreinte: str) -> bool:
    """Vérifie un mot de passe contre son empreinte."""
    brut = mot_de_passe.encode("utf-8")
    if len(brut) > MOT_DE_PASSE_OCTETS_MAX:
        return False
    try:
        return bcrypt.checkpw(brut, empreinte.encode("utf-8"))
    except ValueError:
        # Empreinte illisible en base : on refuse, sans faire échouer la requête.
        return False


def new_refresh_token() -> str:
    """Produit un jeton de renouvellement : 64 caractères aléatoires."""
    return secrets.token_urlsafe(48)


def hash_token(jeton: str) -> str:
    """Empreinte SHA-256 d'un jeton, en hexadécimal (64 caractères).

    C'est cette empreinte qui est stockée. Le jeton lui-même ne l'est jamais :
    une base volée ne doit pas livrer de sessions utilisables.
    """
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def create_access_token(id_users: int) -> str:
    """Émet un jeton d'accès pour un utilisateur."""
    reglages = get_settings()
    maintenant = datetime.now(UTC)
    charge: dict[str, Any] = {
        "sub": str(id_users),
        "iat": int(maintenant.timestamp()),
        "exp": int((maintenant + timedelta(minutes=reglages.ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(charge, reglages.JWT_SECRET_KEY.get_secret_value(), algorithm=ALGORITHME)


def decode_access_token(jeton: str) -> int:
    """Lit un jeton d'accès et renvoie l'identifiant de son porteur.

    Lève `NotAuthenticatedError` si le jeton est expiré, mal signé ou mal formé — le
    client n'a pas à savoir laquelle des trois.
    """
    reglages = get_settings()
    try:
        charge = jwt.decode(
            jeton,
            reglages.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[ALGORITHME],
        )
    except jwt.ExpiredSignatureError as erreur:
        raise NotAuthenticatedError("Session expirée. Se reconnecter.") from erreur
    except jwt.PyJWTError as erreur:
        raise NotAuthenticatedError("Jeton d'accès invalide.") from erreur

    sujet = charge.get("sub")
    if not isinstance(sujet, str) or not sujet.isdigit():
        raise NotAuthenticatedError("Jeton d'accès invalide.")
    return int(sujet)


def refresh_expiry() -> datetime:
    """Date d'expiration d'un jeton de renouvellement émis maintenant."""
    return datetime.now(UTC) + timedelta(days=get_settings().REFRESH_TOKEN_DAYS)


def _fernet() -> Fernet:
    cle = get_settings().TOKEN_ENCRYPTION_KEY.get_secret_value().encode("utf-8")
    return Fernet(cle)


def encrypt_token(clair: str) -> str:
    """Chiffre un secret de plateforme par Fernet avant stockage en base."""
    return _fernet().encrypt(clair.encode("utf-8")).decode("ascii")


def decrypt_token(chiffre: str) -> str:
    """Déchiffre un secret de plateforme lu depuis la base."""
    try:
        return _fernet().decrypt(chiffre.encode("ascii")).decode("utf-8")
    except InvalidToken as erreur:
        raise ApiError("invalid_encrypted_token", "Secret de plateforme illisible.", 500) from erreur
