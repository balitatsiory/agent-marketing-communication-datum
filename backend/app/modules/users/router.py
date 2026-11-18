"""Routes du module Utilisateurs et droits. Aucune règle métier ici."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.core.pagination import Page, PageParams, page_params
from app.modules.users import service
from app.modules.users.constants import MANAGE_PERMISSIONS, MANAGE_USERS
from app.modules.users.deps import require
from app.modules.users.models import User
from app.modules.users.schemas import (
    PasswordSet,
    PermissionCodes,
    PermissionRead,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter(tags=["utilisateurs"])

Params = Annotated[PageParams, Depends(page_params)]
GestionnaireUtilisateurs = Annotated[User, Depends(require(MANAGE_USERS))]
GestionnaireDroits = Annotated[User, Depends(require(MANAGE_PERMISSIONS))]


async def _avec_droits(session: SessionDep, utilisateurs: Sequence[User]) -> list[UserRead]:
    """Compose la lecture d'un ou plusieurs comptes avec leurs droits.

    Une seule requête quel que soit le nombre de comptes.
    """
    codes = await service.droits_par_utilisateur(session, [u.id_users for u in utilisateurs])
    return [
        UserRead.model_validate(u).model_copy(update={"permissions": codes[u.id_users]})
        for u in utilisateurs
    ]


@router.get("/users", response_model=Page[UserRead], summary="Lister les utilisateurs")
async def lister(
    session: SessionDep,
    params: Params,
    _: GestionnaireUtilisateurs,
    inclure_archives: bool = Query(
        False, alias="include_archived", description="Inclure les comptes archivés."
    ),
) -> Page[UserRead]:
    utilisateurs, total = await service.lister(session, params, inclure_archives)
    return Page[UserRead].build(await _avec_droits(session, utilisateurs), total, params)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un utilisateur",
    responses={409: {"description": "Adresse déjà utilisée."}},
)
async def creer(
    corps: UserCreate, session: SessionDep, par: GestionnaireUtilisateurs, reponse: Response
) -> UserRead:
    utilisateur = await service.creer(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/users/{utilisateur.id_users}"
    return (await _avec_droits(session, [utilisateur]))[0]


@router.get("/users/{id_users}", response_model=UserRead, summary="Lire un utilisateur")
async def obtenir(id_users: int, session: SessionDep, _: GestionnaireUtilisateurs) -> UserRead:
    utilisateur = await service.obtenir(session, id_users)
    return (await _avec_droits(session, [utilisateur]))[0]


@router.patch("/users/{id_users}", response_model=UserRead, summary="Modifier un utilisateur")
async def modifier(
    id_users: int, corps: UserUpdate, session: SessionDep, par: GestionnaireUtilisateurs
) -> UserRead:
    utilisateur = await service.modifier(session, id_users, corps, par)
    return (await _avec_droits(session, [utilisateur]))[0]


@router.patch(
    "/users/{id_users}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Changer le mot de passe d'un utilisateur",
    description=(
        "Réservé aux administrateurs. N'envoie aucun courriel et ne produit aucun "
        "lien : le cahier des charges exclut toute réinitialisation en libre-service."
    ),
)
async def definir_mot_de_passe(
    id_users: int, corps: PasswordSet, session: SessionDep, par: GestionnaireUtilisateurs
) -> None:
    await service.definir_mot_de_passe(session, id_users, corps.password, par)


@router.delete(
    "/users/{id_users}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un utilisateur",
    description=(
        "Archivage et non suppression : le compte sort des listes mais reste "
        "l'auteur de ses publications passées. Ses sessions ouvertes sont "
        "révoquées dans la même transaction."
    ),
    responses={409: {"description": "Compte déjà archivé, ou son propre compte."}},
)
async def archiver(id_users: int, session: SessionDep, par: GestionnaireUtilisateurs) -> None:
    await service.archiver(session, id_users, par)


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    summary="Lister les droits attribuables",
)
async def lister_droits(session: SessionDep, _: GestionnaireUtilisateurs) -> list[PermissionRead]:
    return [PermissionRead.model_validate(d) for d in await service.lister_droits(session)]


@router.put(
    "/users/{id_users}/permissions",
    response_model=list[str],
    summary="Définir les droits d'un utilisateur",
    description=(
        "Remplace l'ensemble complet des droits. Les droits retirés sont archivés, "
        "non supprimés. Demande le droit « manage_permissions », distinct de "
        "« manage_users » : attribuer des droits est la seule action permettant "
        "une élévation de privilèges."
    ),
    responses={400: {"description": "Un ou plusieurs codes de droits sont inconnus."}},
)
async def definir_droits(
    id_users: int, corps: PermissionCodes, session: SessionDep, par: GestionnaireDroits
) -> list[str]:
    return await service.definir_droits(session, id_users, corps.codes, par)
