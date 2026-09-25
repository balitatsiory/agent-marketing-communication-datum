"""Dépendances FastAPI : session de base, utilisateur courant, vérification des droits.

Déclarer la règle d'accès dans la signature de l'endpoint la rend visible :

    async def approve(user: User = Depends(require_permission(PermissionCode.REVIEW))):

`HTTPBearer` sert aussi la documentation : c'est lui qui fait apparaître le bouton
« Authorize » dans Swagger, et le cadenas sur les endpoints protégés.
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.modules.users import service as users_service
from app.modules.users.constants import PermissionCode
from app.modules.users.models import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False : on lève nos propres erreurs, au format unique de l'API.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="Jeton d'accès",
    description="Coller le champ `access_token` renvoyé par POST /api/v1/auth/login.",
)

CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(credentials: CredentialsDep, session: SessionDep) -> User:
    """Utilisateur rattaché au jeton présenté.

    Un compte archivé ou suspendu est refusé, même si son jeton est encore valide :
    la révocation prend effet immédiatement.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentification requise.")

    contenu = decode_access_token(credentials.credentials)
    user = await users_service.find_user(session, contenu.id_users)
    if user is None:
        raise AuthenticationError("Compte introuvable.")
    if not user.is_active:
        raise AuthenticationError("Ce compte est désactivé.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(
    code: PermissionCode,
) -> Callable[[User], Coroutine[Any, Any, User]]:
    """Exige un droit précis. Le droit « administrer » ouvre tout."""

    async def verifier(user: CurrentUser) -> User:
        codes = user.permission_codes
        if PermissionCode.ADMIN.value in codes or code.value in codes:
            return user
        raise PermissionDeniedError(f"Vous n'avez pas le droit « {code.value} » pour cette action.")

    return verifier
