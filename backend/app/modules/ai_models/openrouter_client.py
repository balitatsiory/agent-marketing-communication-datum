"""Client HTTP asynchrone vers l'API OpenRouter (Management API et API Standard).

Toute erreur réseau ou HTTP d'OpenRouter est traduite en message français clair
ou en `ApiError` propre afin de ne jamais fuiter la clé API dans les traces.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import ApiError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SECONDES = 20.0


@dataclass
class VerifyKeyResult:
    """Résultat normalisé d'un contrôle de clé auprès d'OpenRouter."""

    ok: bool
    message: str
    total_credits: float | None = None
    total_usage: float | None = None
    remaining_credits: float | None = None
    key_label: str | None = None
    limit_remaining: float | None = None
    is_free_tier: bool | None = None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://iagora.datum-academy.local",
        "X-Title": "IAGORA",
    }


def _extraire_message_erreur(rep: httpx.Response) -> str:
    try:
        corps = rep.json()
    except ValueError:
        return rep.text[:300] or f"HTTP {rep.status_code}"

    if isinstance(corps, dict):
        err = corps.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
        if corps.get("message"):
            return str(corps["message"])
    return f"HTTP {rep.status_code}"


def _lever_erreur_openrouter(rep: httpx.Response, contexte: str) -> None:
    detail = _extraire_message_erreur(rep)
    if rep.status_code == 401:
        raise ApiError(
            "openrouter_unauthorized",
            f"Clé OpenRouter refusée ({contexte}) : {detail}",
            401,
        )
    if rep.status_code == 403:
        raise ApiError(
            "openrouter_forbidden",
            f"Permissions insuffisantes sur OpenRouter ({contexte}) : {detail}",
            403,
        )
    if rep.status_code == 404:
        raise ApiError(
            "openrouter_not_found",
            f"Ressource introuvable sur OpenRouter ({contexte}) : {detail}",
            404,
        )
    if rep.status_code == 409:
        raise ApiError(
            "openrouter_conflict",
            f"Conflit signalé par OpenRouter ({contexte}) : {detail}",
            409,
        )
    raise ApiError(
        "openrouter_error",
        f"Erreur OpenRouter ({contexte}, HTTP {rep.status_code}) : {detail}",
        502,
    )


async def _requete(
    methode: str,
    chemin: str,
    api_key: str,
    *,
    contexte: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            timeout=TIMEOUT_SECONDES,
        ) as client:
            rep = await client.request(
                methode,
                chemin,
                headers=_headers(api_key),
                params=params,
                json=json_body,
            )
    except httpx.TimeoutException as err:
        raise ApiError(
            "openrouter_timeout",
            f"OpenRouter n'a pas répondu dans le délai imparti ({contexte}).",
            504,
        ) from err
    except httpx.HTTPError as err:
        raise ApiError(
            "openrouter_unreachable",
            f"Impossible de joindre OpenRouter ({contexte}) : {err}",
            502,
        ) from err

    if rep.status_code >= 400:
        _lever_erreur_openrouter(rep, contexte)

    if rep.status_code == 204 or not rep.content:
        return {}
    try:
        return rep.json()
    except ValueError:
        return {}


async def verify_standard_key(api_key: str) -> VerifyKeyResult:
    """Vérifie une clé API Standard via `GET /api/v1/key`."""
    try:
        corps = await _requete("GET", "/key", api_key, contexte="vérification clé standard")
    except ApiError as err:
        return VerifyKeyResult(ok=False, message=err.message)

    data = corps.get("data", corps) if isinstance(corps, dict) else {}
    label = data.get("label")
    limit_remaining = data.get("limit_remaining")
    is_free_tier = data.get("is_free_tier")
    usage = data.get("usage")

    msg = "Clé API Standard valide et active sur OpenRouter."
    if label:
        msg = f"Clé API Standard valide ({label})."

    return VerifyKeyResult(
        ok=True,
        message=msg,
        key_label=str(label) if label is not None else None,
        total_usage=float(usage) if isinstance(usage, (int, float)) else None,
        limit_remaining=(
            float(limit_remaining) if isinstance(limit_remaining, (int, float)) else None
        ),
        is_free_tier=bool(is_free_tier) if isinstance(is_free_tier, bool) else None,
    )


async def verify_management_key(api_key: str) -> VerifyKeyResult:
    """Vérifie une Management API Key via `GET /api/v1/credits`."""
    try:
        corps = await _requete("GET", "/credits", api_key, contexte="vérification clé management")
    except ApiError as err:
        return VerifyKeyResult(ok=False, message=err.message)

    data = corps.get("data", corps) if isinstance(corps, dict) else {}
    total_credits = data.get("total_credits")
    total_usage = data.get("total_usage")
    tc = float(total_credits) if isinstance(total_credits, (int, float)) else None
    tu = float(total_usage) if isinstance(total_usage, (int, float)) else None
    rem = round(tc - tu, 6) if (tc is not None and tu is not None) else None

    return VerifyKeyResult(
        ok=True,
        message="Management API Key valide et opérationnelle sur OpenRouter.",
        total_credits=tc,
        total_usage=tu,
        remaining_credits=rem,
    )


async def get_credits(management_key: str) -> dict[str, float | None]:
    """Récupère le solde des crédits OpenRouter via `GET /api/v1/credits`."""
    corps = await _requete("GET", "/credits", management_key, contexte="lecture des crédits")
    data = corps.get("data", corps) if isinstance(corps, dict) else {}
    tc = data.get("total_credits")
    tu = data.get("total_usage")
    total_credits = float(tc) if isinstance(tc, (int, float)) else None
    total_usage = float(tu) if isinstance(tu, (int, float)) else None
    remaining = (
        round(total_credits - total_usage, 6)
        if (total_credits is not None and total_usage is not None)
        else None
    )
    return {
        "total_credits": total_credits,
        "total_usage": total_usage,
        "remaining_credits": remaining,
    }


async def list_workspaces(management_key: str) -> list[dict[str, Any]]:
    """Liste les workspaces OpenRouter via `GET /api/v1/workspaces`."""
    corps = await _requete(
        "GET",
        "/workspaces",
        management_key,
        contexte="liste des workspaces",
        params={"limit": 100},
    )
    if isinstance(corps, list):
        return [item for item in corps if isinstance(item, dict)]
    if isinstance(corps, dict):
        data = corps.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


async def create_workspace(
    management_key: str,
    *,
    name: str,
    description: str | None = None,
    default_text_model: str | None = None,
    default_image_model: str | None = None,
    default_provider_sort: str | None = None,
) -> dict[str, Any]:
    """Crée un workspace sur OpenRouter via `POST /api/v1/workspaces`."""
    payload: dict[str, Any] = {"name": name}
    if description:
        payload["description"] = description
    if default_text_model:
        payload["default_text_model"] = default_text_model
    if default_image_model:
        payload["default_image_model"] = default_image_model
    if default_provider_sort:
        payload["default_provider_sort"] = default_provider_sort

    corps = await _requete(
        "POST",
        "/workspaces",
        management_key,
        contexte="création de workspace",
        json_body=payload,
    )
    if isinstance(corps, dict) and isinstance(corps.get("data"), dict):
        return dict(corps["data"])
    return dict(corps) if isinstance(corps, dict) else {}


async def update_workspace(
    management_key: str,
    workspace_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    default_text_model: str | None = None,
    default_image_model: str | None = None,
    default_provider_sort: str | None = None,
) -> dict[str, Any]:
    """Met à jour un workspace sur OpenRouter via `PATCH /api/v1/workspaces/{id}`."""
    payload: dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if default_text_model is not None:
        payload["default_text_model"] = default_text_model
    if default_image_model is not None:
        payload["default_image_model"] = default_image_model
    if default_provider_sort is not None:
        payload["default_provider_sort"] = default_provider_sort

    corps = await _requete(
        "PATCH",
        f"/workspaces/{workspace_id}",
        management_key,
        contexte="modification de workspace",
        json_body=payload,
    )
    if isinstance(corps, dict) and isinstance(corps.get("data"), dict):
        return dict(corps["data"])
    return dict(corps) if isinstance(corps, dict) else {}


async def delete_workspace(management_key: str, workspace_id: str) -> None:
    """Supprime un workspace sur OpenRouter via `DELETE /api/v1/workspaces/{id}`."""
    await _requete(
        "DELETE",
        f"/workspaces/{workspace_id}",
        management_key,
        contexte="suppression de workspace",
    )


async def list_models(api_key: str) -> list[dict[str, Any]]:
    """Récupère le catalogue des modèles disponibles sur OpenRouter via `GET /api/v1/models`."""
    corps = await _requete("GET", "/models", api_key, contexte="synchronisation du catalogue")
    if isinstance(corps, dict) and isinstance(corps.get("data"), list):
        return [item for item in corps["data"] if isinstance(item, dict)]
    if isinstance(corps, list):
        return [item for item in corps if isinstance(item, dict)]
    return []


async def get_activity(management_key: str, date_iso: str | None = None) -> list[dict[str, Any]]:
    """Récupère l'activité quotidienne agrégée par modèle via `GET /api/v1/activity`."""
    params = {"date": date_iso} if date_iso else None
    corps = await _requete(
        "GET",
        "/activity",
        management_key,
        contexte="lecture de l'activité OpenRouter",
        params=params,
    )
    if isinstance(corps, dict) and isinstance(corps.get("data"), list):
        return [item for item in corps["data"] if isinstance(item, dict)]
    if isinstance(corps, list):
        return [item for item in corps if isinstance(item, dict)]
    return []


async def list_remote_keys(management_key: str) -> list[dict[str, Any]]:
    """Liste les clés API provisionnées sur OpenRouter via `GET /api/v1/keys`."""
    corps = await _requete(
        "GET",
        "/keys",
        management_key,
        contexte="liste des clés OpenRouter",
    )
    if isinstance(corps, dict) and isinstance(corps.get("data"), list):
        return [item for item in corps["data"] if isinstance(item, dict)]
    if isinstance(corps, list):
        return [item for item in corps if isinstance(item, dict)]
    return []
