"""Endpoints d'authentification."""

from fastapi import APIRouter, Request, status

from app.core.deps import CurrentUser, SessionDep
from app.core.errors import REPONSES_AUTHENTIFIEES, ErrorResponse
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenPair
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["authentification"])


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Se connecter",
    responses={401: {"model": ErrorResponse, "description": "Identifiants incorrects."}},
)
async def login(payload: LoginRequest, request: Request, session: SessionDep) -> TokenPair:
    """Ouvre une session et renvoie le couple de jetons.

    Le message d'erreur est **le même** pour un email inconnu et un mot de passe faux :
    sinon, l'API permettrait de découvrir quelles adresses ont un compte.
    """
    return await service.login(
        session,
        payload.email,
        payload.password,
        user_agent=request.headers.get("User-Agent"),
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Renouveler le jeton d'accès",
    responses={401: {"model": ErrorResponse, "description": "Session expirée ou révoquée."}},
)
async def refresh(payload: RefreshRequest, request: Request, session: SessionDep) -> TokenPair:
    """Échange un jeton de renouvellement contre un couple neuf.

    L'ancien jeton est **révoqué au passage** : un jeton volé ne sert qu'une fois.
    """
    return await service.refresh(
        session, payload.refresh_token, user_agent=request.headers.get("User-Agent")
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Se déconnecter")
async def logout(payload: RefreshRequest, session: SessionDep) -> None:
    """Ferme la session correspondant au jeton fourni.

    Sans effet si le jeton est déjà inconnu ou révoqué : la déconnexion ne doit pas
    renseigner un attaquant sur la validité d'un jeton.
    """
    await service.logout(session, payload.refresh_token)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Compte connecté et ses droits",
    responses=REPONSES_AUTHENTIFIEES,
)
async def me(user: CurrentUser) -> UserRead:
    """Renvoie le compte connecté et ses droits.

    Le front s'en sert pour afficher ou masquer les actions : « Approuver » n'apparaît
    que si le droit `review` figure dans la réponse.
    """
    return UserRead.from_model(user)
