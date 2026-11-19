"""Enveloppe d'erreur unique de l'API, et ses gestionnaires.

Toute erreur sort sous la même forme :

    {"error": {"code": "not_found", "message": "…"}}

`code` est stable et en anglais : c'est lui que le frontend teste. `message` est
en français et destiné à l'affichage. Jamais l'inverse.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Erreur métier, destinée à être renvoyée telle quelle au client."""

    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# --- erreurs courantes, pour que les codes ne soient pas réécrits à la main ---


class NotFoundError(ApiError):
    def __init__(self, message: str = "Ressource introuvable."):
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND)


class NotAuthenticatedError(ApiError):
    def __init__(self, message: str = "Authentification requise."):
        super().__init__("not_authenticated", message, status.HTTP_401_UNAUTHORIZED)


class PermissionDeniedError(ApiError):
    def __init__(self, message: str = "Droit insuffisant pour cette action."):
        super().__init__("permission_denied", message, status.HTTP_403_FORBIDDEN)


class ConflictError(ApiError):
    def __init__(self, message: str = "Conflit avec l'état actuel de la ressource."):
        super().__init__("conflict", message, status.HTTP_409_CONFLICT)


def _enveloppe(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Branche les gestionnaires sur l'application."""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ApiError)
        return _enveloppe(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: Exception) -> JSONResponse:
        # 422 : la requête est bien formée mais ses valeurs sont refusées.
        # Le détail de Pydantic est en anglais et technique : on le journalise
        # plutôt que de l'envoyer tel quel à l'utilisateur.
        logger.info("Requête refusée à la validation : %s", exc)
        return _enveloppe(
            "validation_error",
            "Les données envoyées sont incomplètes ou mal formées.",
            # 422 en clair : Starlette a deprecie HTTP_422_UNPROCESSABLE_ENTITY
            # au profit de HTTP_422_UNPROCESSABLE_CONTENT, et le nom changera
            # encore. Le code numerique, lui, est fixe par la norme HTTP.
            422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, StarletteHTTPException)
        # Les erreurs levées par le framework (404 de route inconnue, 405…)
        # passent par la même enveloppe que les nôtres.
        codes = {
            status.HTTP_401_UNAUTHORIZED: "not_authenticated",
            status.HTTP_403_FORBIDDEN: "permission_denied",
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
        }
        code = codes.get(exc.status_code, "http_error")
        return _enveloppe(code, str(exc.detail), exc.status_code)

    # Référencées pour que ruff ne les signale pas comme inutilisées.
    _ = (_api_error, _validation, _http)


async def envelopper_les_erreurs_inattendues(
    request: Request, appeler_la_suite: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Rattrape toute erreur non prévue et la renvoie dans l'enveloppe.

    Pourquoi un INTERGICIEL et non un `@app.exception_handler(Exception)` :
    un gestionnaire d'exception générique est traité par ServerErrorMiddleware,
    que Starlette place TOUJOURS à l'extérieur de la pile — donc à l'extérieur
    du CORS. La réponse 500 sortait alors sans en-tête
    `Access-Control-Allow-Origin`, et le navigateur annonçait « CORS Missing
    Allow Origin » alors que la vraie cause était une panne de l'API.

    Un intergiciel posé À L'INTÉRIEUR du CORS laisse la réponse traverser la
    couche CORS, et le navigateur reçoit enfin le vrai code d'erreur.
    """
    try:
        return await appeler_la_suite(request)
    except Exception:
        # Une erreur non prévue ne doit jamais fuir sa trace vers le client.
        logger.exception("Erreur inattendue sur %s %s", request.method, request.url.path)
        return _enveloppe(
            "internal_error",
            "Une erreur interne est survenue. Elle a été journalisée.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
