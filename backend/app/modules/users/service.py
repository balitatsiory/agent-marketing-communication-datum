"""Règles métier des utilisateurs : unicité de l'email, activation, archivage, droits.

C'est le seul point d'entrée des autres modules : ils appellent ces fonctions,
jamais le routeur ni les modèles.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.modules.users.constants import PermissionCode
from app.modules.users.models import Permission, User, UserPermission
from app.modules.users.schemas import UserCreate, UserUpdate


def normalize_email(email: str) -> str:
    """Un email est comparé en minuscules : Marie@… et marie@… sont le même compte."""
    return email.strip().lower()


async def find_user(session: AsyncSession, id_users: int) -> User | None:
    """Renvoie un utilisateur actif, ou None."""
    requete = select(User).where(User.id_users == id_users, User.deleted_at.is_(None))
    return (await session.execute(requete)).scalar_one_or_none()


async def get_user(session: AsyncSession, id_users: int) -> User:
    """Renvoie un utilisateur actif, ou lève NotFoundError."""
    user = await find_user(session, id_users)
    if user is None:
        raise NotFoundError("Utilisateur introuvable.", code="user_not_found")
    return user


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    requete = select(User).where(User.email == normalize_email(email), User.deleted_at.is_(None))
    return (await session.execute(requete)).scalar_one_or_none()


async def list_users(session: AsyncSession, *, include_archived: bool = False) -> Sequence[User]:
    requete = select(User).order_by(User.last_name, User.first_name)
    if not include_archived:
        requete = requete.where(User.deleted_at.is_(None))
    return (await session.execute(requete)).scalars().all()


async def list_permissions(session: AsyncSession) -> Sequence[Permission]:
    requete = select(Permission).order_by(Permission.sort_order)
    return (await session.execute(requete)).scalars().all()


async def _permissions_par_codes(
    session: AsyncSession, codes: Sequence[PermissionCode]
) -> list[Permission]:
    """Traduit des codes en droits, en vérifiant qu'ils existent tous."""
    if not codes:
        return []
    valeurs = [code.value for code in codes]
    requete = select(Permission).where(Permission.code.in_(valeurs))
    trouves = list((await session.execute(requete)).scalars().all())
    if len(trouves) != len(set(valeurs)):
        manquants = set(valeurs) - {permission.code for permission in trouves}
        raise NotFoundError(
            f"Droits inconnus : {', '.join(sorted(manquants))}.", code="permission_not_found"
        )
    return trouves


async def set_permissions(
    session: AsyncSession, user: User, codes: Sequence[PermissionCode]
) -> User:
    """Remplace les droits d'un utilisateur par la liste fournie."""
    user.permissions = await _permissions_par_codes(session, codes)
    await session.flush()
    return user


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    """Crée un compte. L'email doit être libre."""
    email = normalize_email(payload.email)
    if await find_user_by_email(session, email) is not None:
        raise ConflictError("Cet email est déjà utilisé.", code="email_already_used")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        is_active=True,
    )
    user.permissions = await _permissions_par_codes(session, payload.permissions)
    session.add(user)
    await session.flush()
    return user


async def update_user(session: AsyncSession, id_users: int, payload: UserUpdate) -> User:
    """Modifie un compte. Seuls les champs fournis sont touchés."""
    user = await get_user(session, id_users)

    if payload.first_name is not None:
        user.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.permissions is not None:
        user.permissions = await _permissions_par_codes(session, payload.permissions)

    await session.flush()
    return user


async def change_password(
    session: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    """Change le mot de passe après vérification de l'ancien."""
    if not verify_password(current_password, user.password_hash):
        raise ConflictError("Le mot de passe actuel est incorrect.", code="wrong_password")
    user.password_hash = hash_password(new_password)
    await session.flush()


async def archive_user(session: AsyncSession, id_users: int) -> User:
    """Archive un compte : il disparaît des listes, mais l'historique y renvoie encore."""
    user = await get_user(session, id_users)
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    await session.flush()
    return user


async def touch_last_login(session: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    await session.flush()


async def count_admins(session: AsyncSession) -> int:
    """Nombre d'administrateurs actifs. Sert à ne pas supprimer le dernier."""
    requete = (
        select(User)
        .join(UserPermission, UserPermission.id_users == User.id_users)
        .join(Permission, Permission.id_permissions == UserPermission.id_permissions)
        .where(
            Permission.code == PermissionCode.ADMIN.value,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    return len((await session.execute(requete)).scalars().all())
