"""Règles métier du module Authentification.

Le cycle d'une session : connexion, puis renouvellements successifs par
ROTATION — le jeton utilisé est révoqué et remplacé. Rejouer un jeton déjà
révoqué révoque toute la lignée, parce qu'un tel rejeu ne peut venir que d'un
jeton volé ou d'un client qui a perdu le fil.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotAuthenticatedError
from app.core.security import (
    create_access_token,
    hash_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.modules.auth.models import LOGOUT, REPLAY_DETECTED, ROTATED, RefreshToken
from app.modules.users.models import User

# Message unique pour « adresse inconnue » et « mot de passe faux » : dire
# laquelle des deux est fausse révélerait quelles adresses ont un compte.
IDENTIFIANTS_REFUSES = "Adresse ou mot de passe incorrect."


def _duree_du_jeton_d_acces() -> int:
    return get_settings().ACCESS_TOKEN_MINUTES * 60


async def _emettre(
    session: AsyncSession,
    id_users: int,
    family_id: uuid.UUID,
    user_agent: str | None,
) -> str:
    """Crée une ligne de session et renvoie le jeton en clair.

    Le jeton n'est renvoyé qu'ici, une seule fois : seule son empreinte est
    conservée.
    """
    brut = new_refresh_token()
    session.add(
        RefreshToken(
            id_users=id_users,
            token_hash=hash_token(brut),
            family_id=family_id,
            expires_at=refresh_expiry(),
            user_agent=user_agent[:512] if user_agent else None,
        )
    )
    await session.flush()
    return brut


async def _revoquer_la_lignee(session: AsyncSession, family_id: uuid.UUID, raison: str) -> None:
    lignee = (
        (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.family_id == family_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    maintenant = datetime.now(UTC)
    for jeton in lignee:
        jeton.revoked_at = maintenant
        jeton.revoked_reason = raison
    await session.flush()


async def connexion(
    session: AsyncSession, email: str, mot_de_passe: str, user_agent: str | None
) -> tuple[str, str, int]:
    utilisateur = (
        await session.execute(
            select(User).where(
                User.email.ilike(email),
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if utilisateur is None or not verify_password(mot_de_passe, utilisateur.password_hash):
        raise NotAuthenticatedError(IDENTIFIANTS_REFUSES)

    # Un compte suspendu se voit refuser la connexion, et on le lui dit : à ce
    # stade les identifiants sont bons, l'information ne révèle donc rien.
    if not utilisateur.is_active:
        raise NotAuthenticatedError("Ce compte est suspendu. Contacter un administrateur.")

    utilisateur.last_login_at = datetime.now(UTC)
    brut = await _emettre(session, utilisateur.id_users, uuid.uuid4(), user_agent)
    return (
        create_access_token(utilisateur.id_users),
        brut,
        _duree_du_jeton_d_acces(),
    )


async def renouveler(
    session: AsyncSession, jeton_brut: str, user_agent: str | None
) -> tuple[str, str, int]:
    jeton = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(jeton_brut))
        )
    ).scalar_one_or_none()

    if jeton is None:
        raise NotAuthenticatedError("Jeton de renouvellement inconnu.")

    if jeton.revoked_at is not None:
        # Un jeton déjà révoqué qui revient : soit il a été volé, soit un client
        # rejoue. Dans les deux cas la lignée n'est plus digne de confiance.
        await _revoquer_la_lignee(session, jeton.family_id, REPLAY_DETECTED)
        raise NotAuthenticatedError("Session invalidée. Se reconnecter.")

    if jeton.expires_at <= datetime.now(UTC):
        raise NotAuthenticatedError("Session expirée. Se reconnecter.")

    utilisateur = await session.get(User, jeton.id_users)
    if utilisateur is None or not utilisateur.est_utilisable:
        raise NotAuthenticatedError("Ce compte n'est plus actif.")

    # Rotation : l'ancien est révoqué, le nouveau garde la même lignée.
    jeton.revoked_at = datetime.now(UTC)
    jeton.revoked_reason = ROTATED
    brut = await _emettre(session, utilisateur.id_users, jeton.family_id, user_agent)
    return (
        create_access_token(utilisateur.id_users),
        brut,
        _duree_du_jeton_d_acces(),
    )


async def deconnexion(session: AsyncSession, jeton_brut: str) -> None:
    """Ferme la session. Reste silencieuse sur un jeton inconnu.

    Se déconnecter deux fois, ou avec un jeton déjà expiré, ne doit pas produire
    d'erreur : le résultat voulu est atteint dans tous les cas.
    """
    jeton = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(jeton_brut))
        )
    ).scalar_one_or_none()
    if jeton is not None and jeton.revoked_at is None:
        await _revoquer_la_lignee(session, jeton.family_id, LOGOUT)
