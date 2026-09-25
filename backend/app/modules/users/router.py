"""Endpoints de gestion des utilisateurs et de leurs droits."""

from fastapi import APIRouter, Depends, Path, status

from app.core.deps import CurrentUser, SessionDep, require_permission
from app.core.errors import (
    REPONSE_CONFLIT,
    REPONSE_INTROUVABLE,
    REPONSES_AUTHENTIFIEES,
    ConflictError,
)
from app.modules.users import service
from app.modules.users.constants import PermissionCode
from app.modules.users.models import User
from app.modules.users.schemas import (
    PasswordChange,
    PermissionRead,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["utilisateurs"])
permissions_router = APIRouter(prefix="/permissions", tags=["utilisateurs"])

AdminRequired = Depends(require_permission(PermissionCode.ADMIN))
IdUsers = Path(description="Identifiant de l'utilisateur.", examples=[2])


@router.get(
    "",
    response_model=list[UserRead],
    summary="Lister les comptes",
    responses=REPONSES_AUTHENTIFIEES,
)
async def list_users(session: SessionDep, user: User = AdminRequired) -> list[UserRead]:
    """Liste les comptes actifs. Les comptes archivés n'y figurent pas."""
    return [UserRead.from_model(compte) for compte in await service.list_users(session)]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
    responses={**REPONSES_AUTHENTIFIEES, **REPONSE_CONFLIT},
)
async def create_user(
    payload: UserCreate, session: SessionDep, user: User = AdminRequired
) -> UserRead:
    """Crée un compte et lui attribue ses droits (F-22).

    Le premier administrateur se crée en ligne de commande, puisque cet endpoint
    exige déjà le droit « administrer » :
    `python -m app.cli create-admin --email … --first-name … --last-name …`
    """
    return UserRead.from_model(await service.create_user(session, payload))


@router.get(
    "/{id_users}",
    response_model=UserRead,
    summary="Consulter un compte",
    responses={**REPONSES_AUTHENTIFIEES, **REPONSE_INTROUVABLE},
)
async def get_user(
    session: SessionDep, id_users: int = IdUsers, user: User = AdminRequired
) -> UserRead:
    """Renvoie un compte et ses droits."""
    return UserRead.from_model(await service.get_user(session, id_users))


@router.patch(
    "/{id_users}",
    response_model=UserRead,
    summary="Modifier un compte",
    responses={**REPONSES_AUTHENTIFIEES, **REPONSE_INTROUVABLE},
)
async def update_user(
    payload: UserUpdate,
    session: SessionDep,
    id_users: int = IdUsers,
    user: User = AdminRequired,
) -> UserRead:
    """Modifie un compte. Seuls les champs fournis sont touchés.

    Fournir `permissions` **remplace** la liste des droits ; l'omettre la laisse intacte.
    """
    return UserRead.from_model(await service.update_user(session, id_users, payload))


@router.delete(
    "/{id_users}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un compte",
    responses={**REPONSES_AUTHENTIFIEES, **REPONSE_INTROUVABLE, **REPONSE_CONFLIT},
)
async def archive_user(
    session: SessionDep, id_users: int = IdUsers, user: User = AdminRequired
) -> None:
    """Archive un compte : il disparaît des listes, l'historique y renvoie encore.

    Deux refus volontaires : archiver **son propre** compte, et archiver **le dernier**
    administrateur — plus personne ne pourrait alors administrer la plateforme.
    """
    if id_users == user.id_users:
        raise ConflictError(
            "Vous ne pouvez pas archiver votre propre compte.", code="self_archive_forbidden"
        )
    cible = await service.get_user(session, id_users)
    if (
        PermissionCode.ADMIN.value in cible.permission_codes
        and await service.count_admins(session) <= 1
    ):
        raise ConflictError("Impossible d'archiver le dernier administrateur.", code="last_admin")
    await service.archive_user(session, id_users)


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Changer son mot de passe",
    responses={**REPONSES_AUTHENTIFIEES, **REPONSE_CONFLIT},
)
async def change_password(payload: PasswordChange, session: SessionDep, user: CurrentUser) -> None:
    """Change son propre mot de passe, après vérification de l'ancien.

    Aucun droit particulier n'est requis : chacun gère son compte.
    """
    await service.change_password(session, user, payload.current_password, payload.new_password)


@permissions_router.get(
    "",
    response_model=list[PermissionRead],
    summary="Lister les droits attribuables",
    responses=REPONSES_AUTHENTIFIEES,
)
async def list_permissions(session: SessionDep, user: CurrentUser) -> list[PermissionRead]:
    """Liste les cinq droits du cahier des charges, pour l'écran Utilisateurs."""
    return [
        PermissionRead.model_validate(permission)
        for permission in await service.list_permissions(session)
    ]
