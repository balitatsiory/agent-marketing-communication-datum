"""Routes du module Modèles IA (OpenRouter). Aucune règle métier ici."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import SessionDep
from app.core.storage import Stockage, get_stockage
from app.modules.ai_models import service
from app.modules.ai_models.constants import MANAGE_AI_MODELS
from app.modules.ai_models.schemas import (
    AiModelRead,
    AiModelsSyncRead,
    AiModelToggle,
    AiPromptCreate,
    AiPromptRead,
    AiPromptTaskRead,
    AiPromptUpdate,
    AiTaskAssignmentRead,
    AiTaskAssignmentUpdate,
    AiWorkspaceCreate,
    AiWorkspaceRead,
    AiWorkspaceSyncRead,
    AiWorkspaceUpdate,
    OpenRouterDashboardRead,
    OpenRouterKeyRead,
    OpenRouterKeySave,
    OpenRouterKeyVerifyRead,
    OpenRouterOverviewRead,
    PromptKind,
    SandboxCompareRequest,
    SandboxCompareResponse,
    SandboxRunHistoryRead,
)
from app.modules.users.deps import CurrentUser, require
from app.modules.users.models import User

router = APIRouter(prefix="/openrouter", tags=["modeles-ia-openrouter"])

GestionnaireIA = Annotated[User, Depends(require(MANAGE_AI_MODELS))]


@router.get(
    "/overview",
    response_model=OpenRouterOverviewRead,
    summary="Synthèse globale OpenRouter (clés, crédits, workspaces, modèles)",
)
async def obtenir_synthese(
    session: SessionDep, _: CurrentUser
) -> OpenRouterOverviewRead:
    return await service.obtenir_synthese(session)


@router.get(
    "/dashboard",
    response_model=OpenRouterDashboardRead,
    summary="Tableau de bord FinOps OpenRouter (cumulé ou filtré par workspace_id)",
)
async def obtenir_tableau_de_bord(
    session: SessionDep,
    _: CurrentUser,
    workspace_id: str | None = Query(
        None,
        description="Identifiant OpenRouter du workspace à filtrer. Omis = cumul de tous les workspaces.",
    ),
) -> OpenRouterDashboardRead:
    return await service.obtenir_tableau_de_bord(session, workspace_id=workspace_id)


# ---------------------------------------------------------------------------
# Clés API chiffrées (Management & Standard)
# ---------------------------------------------------------------------------


@router.get(
    "/keys",
    response_model=list[OpenRouterKeyRead],
    summary="Lister les clés OpenRouter (actives et historique, toujours masquées)",
)
async def lister_cles(
    session: SessionDep, _: CurrentUser
) -> list[OpenRouterKeyRead]:
    return await service.lister_cles(session)


@router.post(
    "/keys",
    response_model=OpenRouterKeyVerifyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Chiffrer et enregistrer une clé OpenRouter (Management ou Standard)",
)
async def enregistrer_cle(
    corps: OpenRouterKeySave,
    session: SessionDep,
    par: GestionnaireIA,
    reponse: Response,
) -> OpenRouterKeyVerifyRead:
    resultat = await service.enregistrer_cle(session, corps, par)
    reponse.headers["Location"] = (
        f"/api/v1/openrouter/keys/{resultat.key.id_openrouter_api_keys}"
    )
    return resultat


@router.post(
    "/keys/{id_key}/verify",
    response_model=OpenRouterKeyVerifyRead,
    summary="Vérifier en direct une clé OpenRouter active",
)
async def verifier_cle(
    id_key: int,
    session: SessionDep,
    _: GestionnaireIA,
) -> OpenRouterKeyVerifyRead:
    return await service.verifier_cle(session, id_key)


@router.post(
    "/keys/{id_key}/revoke",
    response_model=OpenRouterKeyRead,
    summary="Révoquer une clé OpenRouter",
)
async def revoquer_cle(
    id_key: int,
    session: SessionDep,
    _: GestionnaireIA,
) -> OpenRouterKeyRead:
    return await service.revoquer_cle(session, id_key)


# ---------------------------------------------------------------------------
# Workspaces OpenRouter
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces",
    response_model=list[AiWorkspaceRead],
    summary="Lister les workspaces OpenRouter synchronisés",
)
async def lister_workspaces(
    session: SessionDep, _: CurrentUser
) -> list[AiWorkspaceRead]:
    return await service.lister_workspaces(session)


@router.post(
    "/workspaces/sync",
    response_model=AiWorkspaceSyncRead,
    summary="Synchroniser les workspaces depuis OpenRouter (Management API Key)",
)
async def synchroniser_workspaces(
    session: SessionDep,
    par: GestionnaireIA,
) -> AiWorkspaceSyncRead:
    return await service.synchroniser_workspaces(session, par)


@router.post(
    "/workspaces",
    response_model=AiWorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un workspace sur OpenRouter et l'enregistrer",
)
async def creer_workspace(
    corps: AiWorkspaceCreate,
    session: SessionDep,
    par: GestionnaireIA,
    reponse: Response,
) -> AiWorkspaceRead:
    ws = await service.creer_workspace(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/openrouter/workspaces/{ws.id_ai_workspaces}"
    return ws


@router.patch(
    "/workspaces/{id_workspace}",
    response_model=AiWorkspaceRead,
    summary="Modifier un workspace OpenRouter ou le définir comme workspace actif IAGORA",
)
async def modifier_workspace(
    id_workspace: int,
    corps: AiWorkspaceUpdate,
    session: SessionDep,
    par: GestionnaireIA,
) -> AiWorkspaceRead:
    return await service.modifier_workspace(session, id_workspace, corps, par)


@router.delete(
    "/workspaces/{id_workspace}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un workspace sur OpenRouter et l'archiver localement",
)
async def supprimer_workspace(
    id_workspace: int,
    session: SessionDep,
    par: GestionnaireIA,
) -> None:
    await service.supprimer_workspace(session, id_workspace, par)


# ---------------------------------------------------------------------------
# Catalogue des modèles & Affectations
# ---------------------------------------------------------------------------


@router.get(
    "/models",
    response_model=list[AiModelRead],
    summary="Lister les modèles OpenRouter synchronisés",
)
async def lister_modeles(
    session: SessionDep,
    _: CurrentUser,
    search: str | None = Query(None, description="Filtre texte sur nom, ID ou fournisseur."),
    provider: str | None = Query(None, description="Filtre par slug fournisseur."),
    enabled_only: bool = Query(False, description="Limiter aux modèles activés."),
) -> list[AiModelRead]:
    return await service.lister_modeles(
        session, search=search, provider=provider, enabled_only=enabled_only
    )


@router.post(
    "/models/sync",
    response_model=AiModelsSyncRead,
    summary="Synchroniser le catalogue des modèles depuis OpenRouter",
)
async def synchroniser_modeles(
    session: SessionDep,
    _: GestionnaireIA,
) -> AiModelsSyncRead:
    return await service.synchroniser_modeles(session)


@router.patch(
    "/models/{id_model}",
    response_model=AiModelRead,
    summary="Activer ou désactiver un modèle IA",
)
async def basculer_modele(
    id_model: int,
    corps: AiModelToggle,
    session: SessionDep,
    _: GestionnaireIA,
) -> AiModelRead:
    return await service.basculer_modele(session, id_model, corps.is_enabled)


@router.get(
    "/assignments",
    response_model=list[AiTaskAssignmentRead],
    summary="Lister les affectations des modèles IA par tâche métier",
)
async def lister_affectations(
    session: SessionDep, _: CurrentUser
) -> list[AiTaskAssignmentRead]:
    return await service.lister_affectations(session)


@router.put(
    "/assignments/{task_code}",
    response_model=AiTaskAssignmentRead,
    summary="Affecter un modèle OpenRouter à une tâche métier IAGORA",
)
async def modifier_affectation(
    task_code: str,
    corps: AiTaskAssignmentUpdate,
    session: SessionDep,
    par: GestionnaireIA,
) -> AiTaskAssignmentRead:
    return await service.modifier_affectation(session, task_code, corps, par)


# ---------------------------------------------------------------------------
# Bac à sable IA (comparateur A/B/C multi-modèles)
# ---------------------------------------------------------------------------


@router.post(
    "/sandbox/compare",
    response_model=SandboxCompareResponse,
    summary="Exécuter en parallèle une comparaison multi-modèles dans le Bac à sable IA",
)
async def comparer_bac_a_sable(
    corps: SandboxCompareRequest,
    session: SessionDep,
    par: GestionnaireIA,
    stockage: Annotated[Stockage, Depends(get_stockage)],
) -> SandboxCompareResponse:
    return await service.comparer_bac_a_sable(session, corps, par, stockage)


@router.get(
    "/sandbox/history",
    response_model=list[SandboxRunHistoryRead],
    summary="Lister l'historique des exécutions du Bac à sable IA",
)
async def lister_historique_bac_a_sable(
    session: SessionDep,
    _: CurrentUser,
    use_case: str | None = Query(None, description="Filtrer par cas d'utilisation strict."),
    limit: int = Query(50, ge=1, le=200),
) -> list[SandboxRunHistoryRead]:
    return await service.lister_historique_bac_a_sable(session, use_case=use_case, limit=limit)


@router.delete(
    "/sandbox/history/{id_run}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une entrée de l'historique du Bac à sable IA",
)
async def supprimer_historique_bac_a_sable(
    id_run: int,
    session: SessionDep,
    _: GestionnaireIA,
) -> None:
    await service.supprimer_historique_bac_a_sable(session, id_run)


# ---------------------------------------------------------------------------
# Prompts système & Prompt templates
# ---------------------------------------------------------------------------


@router.get(
    "/prompts/tasks",
    response_model=list[AiPromptTaskRead],
    summary="Lister les tâches métier IA avec leur nombre de prompts/gabarits",
)
async def lister_taches_prompts(
    session: SessionDep,
    _: CurrentUser,
    kind: PromptKind = Query("system", description="system ou template."),
) -> list[AiPromptTaskRead]:
    return await service.lister_taches_prompts(session, kind)


@router.get(
    "/prompts",
    response_model=list[AiPromptRead],
    summary="Lister les prompts système ou gabarits pour une tâche métier",
)
async def lister_prompts(
    session: SessionDep,
    _: CurrentUser,
    kind: PromptKind = Query("system", description="system ou template."),
    task_code: str | None = Query(None, description="Filtrer par tâche métier."),
) -> list[AiPromptRead]:
    return await service.lister_prompts(session, prompt_kind=kind, task_code=task_code)


@router.post(
    "/prompts",
    response_model=AiPromptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une nouvelle version de prompt système ou gabarit",
)
async def creer_prompt(
    corps: AiPromptCreate,
    session: SessionDep,
    par: GestionnaireIA,
    reponse: Response,
) -> AiPromptRead:
    cree = await service.creer_prompt(session, corps, par)
    reponse.headers["Location"] = f"/api/v1/openrouter/prompts/{cree.id_ai_prompts}"
    return cree


@router.patch(
    "/prompts/{id_prompt}",
    response_model=AiPromptRead,
    summary="Modifier un prompt système ou gabarit",
)
async def modifier_prompt(
    id_prompt: int,
    corps: AiPromptUpdate,
    session: SessionDep,
    par: GestionnaireIA,
) -> AiPromptRead:
    return await service.modifier_prompt(session, id_prompt, corps, par)


@router.post(
    "/prompts/{id_prompt}/set-default",
    response_model=AiPromptRead,
    summary="Activer ce prompt/gabarit par défaut pour sa tâche métier",
)
async def activer_prompt_par_defaut(
    id_prompt: int,
    session: SessionDep,
    par: GestionnaireIA,
) -> AiPromptRead:
    return await service.activer_prompt_par_defaut(session, id_prompt, par)


@router.delete(
    "/prompts/{id_prompt}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archiver un prompt système ou gabarit",
)
async def supprimer_prompt(
    id_prompt: int,
    session: SessionDep,
    par: GestionnaireIA,
) -> None:
    await service.supprimer_prompt(session, id_prompt, par)
