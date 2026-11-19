"""Routes du module Authentification. Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Header, status

from app.core.deps import SessionDep
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, MeRead, RefreshRequest, TokenPair
from app.modules.users.deps import CurrentUser, codes_de
from app.modules.users.schemas import PasswordChange
from app.modules.users.service import changer_son_mot_de_passe

router = APIRouter(prefix="/auth", tags=["authentification"])

UserAgent = Annotated[str | None, Header(include_in_schema=False)]


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Ouvrir une session",
    responses={401: {"description": "Identifiants refusés, ou compte suspendu."}},
)
async def login(
    corps: LoginRequest, session: SessionDep, user_agent: UserAgent = None
) -> TokenPair:
    acces, renouvellement, duree = await service.connexion(
        session, corps.email, corps.password, user_agent
    )
    return TokenPair(access_token=acces, refresh_token=renouvellement, expires_in=duree)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Renouveler le jeton d'accès",
    responses={401: {"description": "Jeton inconnu, expiré, ou lignée invalidée."}},
)
async def refresh(
    corps: RefreshRequest, session: SessionDep, user_agent: UserAgent = None
) -> TokenPair:
    acces, renouvellement, duree = await service.renouveler(
        session, corps.refresh_token, user_agent
    )
    return TokenPair(access_token=acces, refresh_token=renouvellement, expires_in=duree)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Fermer la session",
)
async def logout(corps: RefreshRequest, session: SessionDep) -> None:
    await service.deconnexion(session, corps.refresh_token)


@router.get("/me", response_model=MeRead, summary="Profil courant et ses droits")
async def me(session: SessionDep, utilisateur: CurrentUser) -> MeRead:
    return MeRead(
        id_users=utilisateur.id_users,
        email=utilisateur.email,
        first_name=utilisateur.first_name,
        last_name=utilisateur.last_name,
        permissions=await codes_de(session, utilisateur.id_users),
    )


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Changer son propre mot de passe",
    responses={400: {"description": "Le mot de passe actuel est incorrect."}},
)
async def changer_mot_de_passe(
    corps: PasswordChange, session: SessionDep, utilisateur: CurrentUser
) -> None:
    await changer_son_mot_de_passe(session, utilisateur, corps.current_password, corps.new_password)
