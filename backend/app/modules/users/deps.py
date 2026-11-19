"""Dépendances du module : utilisateur courant et vérification d'un droit.

Ces dépendances vivent ici et non dans `core/` : charger l'utilisateur et lire
ses droits suppose les tables de ce module, et `core/` ne doit dépendre d'aucun
module métier.
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import select

from app.core.deps import CurrentUserId, SessionDep
from app.core.errors import NotAuthenticatedError, PermissionDeniedError
from app.modules.users.models import Permission, User, UserPermission


async def current_user(session: SessionDep, id_users: CurrentUserId) -> User:
    """Utilisateur porteur du jeton, s'il peut encore agir.

    C'est ici que la suspension d'un compte prend effet : le jeton reste
    cryptographiquement valide jusqu'à son expiration, mais il ne donne plus
    accès à rien. L'exposition se limite donc à la durée de vie du jeton
    d'accès, un quart d'heure, et non à celle du jeton de renouvellement.
    """
    utilisateur = await session.get(User, id_users)
    if utilisateur is None or not utilisateur.est_utilisable:
        raise NotAuthenticatedError("Ce compte n'est plus actif.")
    return utilisateur


CurrentUser = Annotated[User, Depends(current_user)]


async def codes_de(session: SessionDep, id_users: int) -> list[str]:
    """Codes des droits actifs d'un utilisateur."""
    requete = (
        select(Permission.code)
        .join(UserPermission, UserPermission.id_permissions == Permission.id_permissions)
        .where(
            UserPermission.id_users == id_users,
            UserPermission.deleted_at.is_(None),
        )
        .order_by(Permission.sort_order)
    )
    return list((await session.execute(requete)).scalars().all())


def require(code: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Exige un droit. Renvoie 401 sans jeton valable, 403 sans le droit.

    La distinction compte pour le frontend : il redirige vers la connexion dans
    le premier cas, affiche un refus dans le second.
    """

    async def verificateur(session: SessionDep, utilisateur: CurrentUser) -> User:
        if code not in await codes_de(session, utilisateur.id_users):
            raise PermissionDeniedError(f"Ce geste demande le droit « {code} ».")
        return utilisateur

    return verificateur
