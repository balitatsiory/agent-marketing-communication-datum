"""Règles d'authentification : connexion, rotation des jetons, déconnexion."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import TokenPair
from app.modules.users import service as users_service
from app.modules.users.models import User

logger = logging.getLogger(__name__)
settings = get_settings()

# Même message pour un email inconnu et un mot de passe faux : sinon, l'API
# permettrait de découvrir quelles adresses ont un compte.
MESSAGE_IDENTIFIANTS = "Email ou mot de passe incorrect."


async def _creer_session(session: AsyncSession, user: User, user_agent: str | None) -> TokenPair:
    """Crée une session : un jeton de renouvellement en base, un jeton d'accès signé."""
    refresh_token = generate_refresh_token()
    session.add(
        RefreshToken(
            id_users=user.id_users,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_token_expiry(),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    await session.flush()

    return TokenPair(
        access_token=create_access_token(user.id_users, sorted(user.permission_codes)),
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
    )


async def login(
    session: AsyncSession, email: str, password: str, *, user_agent: str | None = None
) -> TokenPair:
    """Vérifie les identifiants et ouvre une session."""
    user = await users_service.find_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError(MESSAGE_IDENTIFIANTS)
    if not user.is_active:
        raise AuthenticationError("Ce compte est désactivé.")

    await users_service.touch_last_login(session, user)
    logger.info("Connexion réussie · utilisateur=%s", user.id_users)
    return await _creer_session(session, user, user_agent)


async def refresh(
    session: AsyncSession, refresh_token: str, *, user_agent: str | None = None
) -> TokenPair:
    """Échange un jeton de renouvellement contre un couple neuf.

    L'ancien jeton est révoqué au passage : un jeton volé ne sert qu'une fois.
    """
    empreinte = hash_refresh_token(refresh_token)
    requete = select(RefreshToken).where(RefreshToken.token_hash == empreinte)
    ligne = (await session.execute(requete)).scalar_one_or_none()

    maintenant = datetime.now(UTC)
    if ligne is None or ligne.revoked_at is not None or ligne.expires_at <= maintenant:
        raise AuthenticationError("Session expirée ou révoquée, reconnectez-vous.")

    user = await users_service.find_user(session, ligne.id_users)
    if user is None or not user.is_active:
        raise AuthenticationError("Ce compte n'est plus actif.")

    ligne.revoked_at = maintenant
    await session.flush()
    return await _creer_session(session, user, user_agent)


async def logout(session: AsyncSession, refresh_token: str) -> None:
    """Ferme une session. Sans effet si le jeton est déjà inconnu ou révoqué."""
    empreinte = hash_refresh_token(refresh_token)
    requete = (
        update(RefreshToken)
        .where(RefreshToken.token_hash == empreinte, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.execute(requete)


async def revoke_all_sessions(session: AsyncSession, id_users: int) -> None:
    """Ferme toutes les sessions d'un compte : suspension, archivage, mot de passe changé."""
    requete = (
        update(RefreshToken)
        .where(RefreshToken.id_users == id_users, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.execute(requete)
