"""Règles métier du module Utilisateurs et droits."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.core.security import hash_password, verify_password
from app.modules.auth.models import USER_ARCHIVED, RefreshToken
from app.modules.users.models import Permission, User, UserPermission
from app.modules.users.schemas import UserCreate, UserUpdate


async def _email_est_pris(session: AsyncSession, email: str, sauf: int | None = None) -> bool:
    """L'unicité ignore la casse et ne regarde que les comptes non archivés.

    La base l'impose déjà par un index unique partiel. On vérifie en amont pour
    renvoyer un 409 explicite plutôt qu'une violation de contrainte.
    """
    requete = select(User.id_users).where(
        func.lower(User.email) == email.lower(),
        User.deleted_at.is_(None),
    )
    if sauf is not None:
        requete = requete.where(User.id_users != sauf)
    return (await session.execute(requete)).first() is not None


async def lister(
    session: AsyncSession, params: PageParams, inclure_archives: bool = False
) -> tuple[list[User], int]:
    conditions = [] if inclure_archives else [User.deleted_at.is_(None)]

    total = (
        await session.execute(select(func.count()).select_from(User).where(*conditions))
    ).scalar_one()

    requete = (
        select(User)
        .where(*conditions)
        .order_by(User.last_name, User.first_name)
        .offset(params.offset)
        .limit(params.size)
    )
    return list((await session.execute(requete)).scalars().all()), int(total)


async def obtenir(session: AsyncSession, id_users: int) -> User:
    utilisateur = await session.get(User, id_users)
    if utilisateur is None:
        raise NotFoundError("Cet utilisateur n'existe pas.")
    return utilisateur


async def creer(session: AsyncSession, donnees: UserCreate, par: User) -> User:
    if await _email_est_pris(session, donnees.email):
        raise ConflictError("Un compte utilise déjà cette adresse.")

    utilisateur = User(
        email=donnees.email,
        password_hash=hash_password(donnees.password),
        first_name=donnees.first_name,
        last_name=donnees.last_name,
        is_active=True,
        id_users_created_by=par.id_users,
    )
    session.add(utilisateur)
    await session.flush()
    return utilisateur


async def modifier(session: AsyncSession, id_users: int, donnees: UserUpdate, par: User) -> User:
    utilisateur = await obtenir(session, id_users)
    if utilisateur.deleted_at is not None:
        raise ConflictError("Ce compte est archivé : il n'est plus modifiable.")

    champs = donnees.model_dump(exclude_unset=True)
    if "email" in champs and await _email_est_pris(session, champs["email"], sauf=id_users):
        raise ConflictError("Un compte utilise déjà cette adresse.")

    for nom, valeur in champs.items():
        setattr(utilisateur, nom, valeur)
    utilisateur.id_users_changed_by = par.id_users
    await session.flush()
    return utilisateur


async def definir_mot_de_passe(
    session: AsyncSession, id_users: int, mot_de_passe: str, par: User
) -> None:
    """Changement par un administrateur : aucun courriel, aucun lien.

    Le cahier des charges exclut toute réinitialisation en libre-service ; ce
    geste reste donc purement administratif.
    """
    utilisateur = await obtenir(session, id_users)
    utilisateur.password_hash = hash_password(mot_de_passe)
    utilisateur.id_users_changed_by = par.id_users
    await session.flush()


async def changer_son_mot_de_passe(
    session: AsyncSession, utilisateur: User, ancien: str, nouveau: str
) -> None:
    if not verify_password(ancien, utilisateur.password_hash):
        raise ApiError("wrong_password", "Le mot de passe actuel est incorrect.", 400)
    utilisateur.password_hash = hash_password(nouveau)
    utilisateur.id_users_changed_by = utilisateur.id_users
    await session.flush()


async def archiver(session: AsyncSession, id_users: int, par: User) -> None:
    """Archive un compte et révoque ses sessions dans la MÊME transaction.

    « On garde l'histoire, on détruit le pouvoir » : la ligne demeure, puisque
    l'utilisateur reste l'auteur de ses publications passées, mais ses sessions
    ouvertes cessent immédiatement.

    La révocation est écrite ici et non appelée au module Authentification : un
    module importe les modèles de ceux dont il dépend, jamais leur service.
    """
    utilisateur = await obtenir(session, id_users)
    if utilisateur.deleted_at is not None:
        raise ConflictError("Ce compte est déjà archivé.")
    if utilisateur.id_users == par.id_users:
        raise ConflictError("On ne peut pas archiver son propre compte.")

    maintenant = datetime.now(UTC)
    utilisateur.deleted_at = maintenant
    utilisateur.id_users_deleted_by = par.id_users

    jetons = (
        (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.id_users == id_users,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for jeton in jetons:
        jeton.revoked_at = maintenant
        jeton.revoked_reason = USER_ARCHIVED
    await session.flush()


async def lister_droits(session: AsyncSession) -> list[Permission]:
    requete = select(Permission).order_by(Permission.sort_order)
    return list((await session.execute(requete)).scalars().all())


async def definir_droits(
    session: AsyncSession, id_users: int, codes: list[str], par: User
) -> list[str]:
    """Remplace l'ensemble des droits par celui fourni.

    Les droits retirés sont ARCHIVÉS, non supprimés : savoir qui a détenu quel
    droit et à quelle période fait partie de la traçabilité.
    """
    utilisateur = await obtenir(session, id_users)
    if utilisateur.deleted_at is not None:
        raise ConflictError("Ce compte est archivé : ses droits ne sont plus modifiables.")

    voulus = set(codes)
    connus = {droit.code: droit.id_permissions for droit in await lister_droits(session)}
    inconnus = sorted(voulus - set(connus))
    if inconnus:
        raise ApiError(
            "unknown_permission",
            f"Droits inconnus : {', '.join(inconnus)}.",
            400,
        )

    actuelles = (
        (
            await session.execute(
                select(UserPermission).where(
                    UserPermission.id_users == id_users,
                    UserPermission.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    par_id = {ligne.id_permissions: ligne for ligne in actuelles}
    ids_voulus = {connus[code] for code in voulus}

    maintenant = datetime.now(UTC)
    for id_permissions, ligne in par_id.items():
        if id_permissions not in ids_voulus:
            ligne.deleted_at = maintenant
            ligne.id_users_deleted_by = par.id_users

    for id_permissions in ids_voulus - set(par_id):
        session.add(
            UserPermission(
                id_users=id_users,
                id_permissions=id_permissions,
                id_users_created_by=par.id_users,
            )
        )

    await session.flush()
    requete = (
        select(Permission.code)
        .join(UserPermission, UserPermission.id_permissions == Permission.id_permissions)
        .where(UserPermission.id_users == id_users, UserPermission.deleted_at.is_(None))
        .order_by(Permission.sort_order)
    )
    return list((await session.execute(requete)).scalars().all())
