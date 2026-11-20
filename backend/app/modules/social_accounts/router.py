"""Routes du module Comptes réseaux sociaux. Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.modules.social_accounts import service
from app.modules.social_accounts.constants import MANAGE_SOCIAL_ACCOUNTS
from app.modules.social_accounts.schemas import (
    SocialAccountCreate,
    SocialAccountRead,
    SocialAccountReconnect,
    SocialAccountStatisticsRead,
    SocialAccountStatusRead,
    SocialAccountSyncPostsRead,
    SocialAccountSyncRead,
    SocialAccountSyncStatsRead,
    SocialAccountTokenRead,
    SocialAccountVerifyRead,
    SocialPlatformRead,
    SocialPostRead,
)
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User

router = APIRouter(tags=["reseaux-sociaux"])

GestionnaireReseaux = Annotated[User, Depends(require(MANAGE_SOCIAL_ACCOUNTS))]


@router.get(
    "/social-platforms",
    response_model=list[SocialPlatformRead],
    summary="Lister les plateformes sociales et leurs capacités",
)
async def lister_plateformes(
    session: SessionDep, _: CurrentUser
) -> list[SocialPlatformRead]:
    return await service.lister_plateformes(session)


@router.get(
    "/social-account-statuses",
    response_model=list[SocialAccountStatusRead],
    summary="Lister les états possibles d'un compte réseau social",
)
async def lister_statuts(
    session: SessionDep, _: CurrentUser
) -> list[SocialAccountStatusRead]:
    return [SocialAccountStatusRead.model_validate(s) for s in await service.lister_statuts(session)]


@router.get(
    "/social-accounts",
    response_model=list[SocialAccountRead],
    summary="Lister les comptes réseaux sociaux raccordés",
)
async def lister_comptes(
    session: SessionDep,
    _: CurrentUser,
    statut: str | None = Query(None, alias="status", description="Filtrer par code d'état."),
    plateforme: str | None = Query(
        None, alias="platform", description="Filtrer par code de plateforme."
    ),
) -> list[SocialAccountRead]:
    return await service.lister_comptes(session, status_code=statut, platform_code=plateforme)


@router.post(
    "/social-accounts",
    response_model=SocialAccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Connecter un compte réseau social (saisie manuelle)",
    responses={409: {"description": "Ce compte est déjà raccordé sur cette plateforme."}},
)
async def creer_compte(
    corps: SocialAccountCreate,
    session: SessionDep,
    par: GestionnaireReseaux,
    reponse: Response,
) -> SocialAccountRead:
    compte = await service.creer_compte(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/social-accounts/{compte.id_social_accounts}"
    return compte


@router.post(
    "/social-accounts/{id_social_accounts}/reconnect",
    response_model=SocialAccountRead,
    summary="Reconnecter un compte avec une nouvelle délivrance de clés",
)
async def reconnecter_compte(
    id_social_accounts: int,
    corps: SocialAccountReconnect,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialAccountRead:
    return await service.reconnecter_compte(session, id_social_accounts, corps, par)


@router.post(
    "/social-accounts/{id_social_accounts}/verify",
    response_model=SocialAccountVerifyRead,
    summary="Vérifier en direct le compte et son jeton auprès de la plateforme (Meta)",
    description=(
        "Appelle Meta Graph API pour confirmer que le jeton est valide et donne "
        "bien accès à l'identifiant externe saisi. Journalise le passage dans "
        "`social_account_syncs` (sorte `token_check`) et met à jour l'état du compte."
    ),
)
async def verifier_compte(
    id_social_accounts: int,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialAccountVerifyRead:
    return await service.verifier_compte(session, id_social_accounts, par)


@router.post(
    "/social-accounts/{id_social_accounts}/disconnect",
    response_model=SocialAccountRead,
    summary="Débrancher volontairement un compte réseau social",
    description=(
        "Révoque les jetons actifs et arrête toute publication sur ce compte, "
        "tout en conservant l'historique des statistiques et publications parues."
    ),
)
async def debrancher_compte(
    id_social_accounts: int,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialAccountRead:
    return await service.debrancher_compte(session, id_social_accounts, par)


@router.get(
    "/social-accounts/{id_social_accounts}",
    response_model=SocialAccountRead,
    summary="Lire la fiche d'un compte réseau social",
)
async def obtenir_compte(
    id_social_accounts: int,
    session: SessionDep,
    _: CurrentUser,
) -> SocialAccountRead:
    return await service.obtenir_compte(session, id_social_accounts)


@router.get(
    "/social-accounts/{id_social_accounts}/statistics",
    response_model=SocialAccountStatisticsRead,
    summary="Lire les séries statistiques d'un compte",
)
async def lister_statistiques(
    id_social_accounts: int,
    session: SessionDep,
    _: CurrentUser,
    jours: int = Query(30, alias="days", ge=1, le=365, description="Fenêtre en jours (7, 30, 90…)."),
) -> SocialAccountStatisticsRead:
    return await service.lister_statistiques_compte(session, id_social_accounts, jours=jours)


@router.post(
    "/social-accounts/{id_social_accounts}/sync-statistics",
    response_model=SocialAccountSyncStatsRead,
    summary="Collecter manuellement les statistiques d'un compte (Meta Graph API)",
)
async def synchroniser_statistiques(
    id_social_accounts: int,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialAccountSyncStatsRead:
    return await service.synchroniser_statistiques_compte(session, id_social_accounts, par)


@router.get(
    "/social-accounts/{id_social_accounts}/tokens",
    response_model=list[SocialAccountTokenRead],
    summary="Lister l'historique des délivrances de clés d'un compte",
)
async def lister_jetons(
    id_social_accounts: int,
    session: SessionDep,
    _: CurrentUser,
) -> list[SocialAccountTokenRead]:
    return await service.lister_jetons_compte(session, id_social_accounts)


@router.get(
    "/social-accounts/{id_social_accounts}/syncs",
    response_model=list[SocialAccountSyncRead],
    summary="Lister le journal des passages du collecteur pour un compte",
)
async def lister_passages(
    id_social_accounts: int,
    session: SessionDep,
    _: CurrentUser,
) -> list[SocialAccountSyncRead]:
    return await service.lister_passages_compte(session, id_social_accounts)


@router.get(
    "/social-accounts/{id_social_accounts}/posts",
    response_model=list[SocialPostRead],
    summary="Lister les publications parues sur ce compte",
)
async def lister_posts(
    id_social_accounts: int,
    session: SessionDep,
    _: CurrentUser,
) -> list[SocialPostRead]:
    return await service.lister_posts_compte(session, id_social_accounts)


@router.post(
    "/social-accounts/{id_social_accounts}/sync-posts",
    response_model=SocialAccountSyncPostsRead,
    summary="Importer les publications déjà parues depuis Meta Graph API",
)
async def synchroniser_posts(
    id_social_accounts: int,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialAccountSyncPostsRead:
    return await service.synchroniser_posts_compte(session, id_social_accounts, par)


@router.post(
    "/social-accounts/{id_social_accounts}/posts/{id_social_posts}/archive",
    response_model=SocialPostRead,
    summary="Déclarer une publication comme archivée sur le réseau",
)
async def declarer_post_archive(
    id_social_accounts: int,
    id_social_posts: int,
    session: SessionDep,
    par: GestionnaireReseaux,
) -> SocialPostRead:
    return await service.declarer_post_archive(session, id_social_accounts, id_social_posts, par)
