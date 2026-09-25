"""Erreurs métier et format unique des réponses d'erreur.

Les services lèvent ces erreurs sans rien connaître de HTTP ; les gestionnaires
enregistrés ici les traduisent en réponses, toujours de la même forme :

    {"error": {"code": "publication_not_found", "message": "Publication introuvable."}}

`code` est stable : le front peut s'appuyer dessus. `message` est en français et
destiné à être affiché.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """Contenu de la clé `error`."""

    code: str = Field(description="Code stable, exploitable par le front.", examples=["not_found"])
    message: str = Field(
        description="Message en français, destiné à être affiché.",
        examples=["Publication introuvable."],
    )


class ErrorResponse(BaseModel):
    """Forme unique de toutes les erreurs de l'API."""

    error: ErrorDetail


def _doc(description: str) -> dict[str, Any]:
    return {"model": ErrorResponse, "description": description}


# Réponses d'erreur documentées dans Swagger, à réutiliser dans les routeurs.
REPONSES_AUTHENTIFIEES: dict[int | str, dict[str, Any]] = {
    401: _doc("Jeton absent, invalide ou expiré."),
    403: _doc("Droit insuffisant pour cette action."),
}
REPONSE_INTROUVABLE: dict[int | str, dict[str, Any]] = {404: _doc("Ressource introuvable.")}
REPONSE_CONFLIT: dict[int | str, dict[str, Any]] = {
    409: _doc("Action impossible dans l'état actuel.")
}


class DomainError(Exception):
    """Erreur métier. Les modules en dérivent pour leurs cas particuliers."""

    code = "domain_error"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class AuthenticationError(DomainError):
    """Identifiants absents, invalides ou expirés."""

    code = "not_authenticated"
    status_code = status.HTTP_401_UNAUTHORIZED


class PermissionDeniedError(DomainError):
    """L'utilisateur est connu, mais n'a pas le droit demandé."""

    code = "permission_denied"
    status_code = status.HTTP_403_FORBIDDEN


class NotFoundError(DomainError):
    """Objet inexistant ou archivé."""

    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """Action impossible dans l'état actuel, ou modification concurrente."""

    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


def _reponse(status_code: int, code: str, message: str, **extra: Any) -> JSONResponse:
    contenu: dict[str, Any] = {"error": {"code": code, "message": message, **extra}}
    return JSONResponse(status_code=status_code, content=contenu)


def register_error_handlers(app: FastAPI) -> None:
    """Branche les gestionnaires d'erreurs sur l'application."""

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return _reponse(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # `fields` détaille chaque champ fautif : le front peut afficher l'erreur
        # sous le bon champ du formulaire.
        # 422 en clair : le nom de la constante a changé selon les versions de Starlette.
        return _reponse(
            422,
            "validation_error",
            "Les données envoyées sont invalides.",
            fields=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # La trace part dans les journaux, jamais dans la réponse : elle contiendrait
        # des noms de tables, des chemins de fichiers, parfois des valeurs.
        logger.exception("Erreur inattendue sur %s %s", request.method, request.url.path)
        return _reponse(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Une erreur est survenue. L'équipe technique a été prévenue.",
        )
