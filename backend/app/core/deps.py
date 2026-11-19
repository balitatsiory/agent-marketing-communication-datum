"""Dépendances communes : session de base de données et lecture du jeton.

Ce fichier ne connaît AUCUN module métier : il s'arrête à l'identifiant porté
par le jeton. Charger l'utilisateur et vérifier ses droits suppose les tables du
module Utilisateurs, et relève donc de ce module.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import NotAuthenticatedError
from app.core.security import decode_access_token

# auto_error=False : sans cela, Starlette renvoie son propre 403 quand l'en-tête
# manque, ce qui contournerait notre enveloppe d'erreur et donnerait 403 là où
# 401 est la bonne réponse.
schema_jeton = HTTPBearer(auto_error=False, description="Jeton d'accès obtenu par /auth/login.")

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def current_user_id(
    informations: Annotated[HTTPAuthorizationCredentials | None, Depends(schema_jeton)],
) -> int:
    """Identifiant de l'utilisateur porté par le jeton d'accès."""
    if informations is None:
        raise NotAuthenticatedError()
    return decode_access_token(informations.credentials)


CurrentUserId = Annotated[int, Depends(current_user_id)]
