"""Point d'entrée de l'API IAGORA.

Assemble l'application : réglages, CORS, gestion des erreurs, routeurs, et le
point de contrôle /health.
"""

import logging

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from app.api.v1 import api_v1_router
from app.core.config import Settings, get_settings
from app.core.database import check_database
from app.core.errors import register_error_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DESCRIPTION = """
API de la plateforme **IAGORA** — agent IA de marketing et communication digitale
de DATUM Academy.

### Comment tester depuis cette page

1. Appeler `POST /api/v1/auth/login` avec un email et un mot de passe.
2. Copier le champ `access_token` de la réponse.
3. Cliquer sur **Authorize**, en haut à droite, et le coller.
4. Les endpoints marqués d'un cadenas deviennent utilisables.

Le jeton d'accès dure 15 minutes. Passé ce délai, `POST /api/v1/auth/refresh`
en fournit un nouveau à partir du `refresh_token`.

### Conventions

* Les dates sont en **UTC**, au format ISO 8601.
* Les erreurs ont toutes la même forme :
  `{"error": {"code": "not_found", "message": "…"}}` — `code` est stable, `message`
  est en français et destiné à l'affichage.
"""

TAGS = [
    {
        "name": "authentification",
        "description": "Connexion, renouvellement du jeton, déconnexion, profil courant.",
    },
    {
        "name": "utilisateurs",
        "description": "Comptes de l'équipe et attribution des droits. Réservé aux "
        "administrateurs, sauf le changement de son propre mot de passe.",
    },
    {
        "name": "technique",
        "description": "Points de contrôle de l'API.",
    },
]


class HealthResponse(BaseModel):
    """Réponse du point de contrôle."""

    status: str
    environment: str
    database: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construit l'application. Les tests peuvent passer d'autres réglages."""
    settings = settings or get_settings()

    app = FastAPI(
        title="IAGORA API",
        version="0.1.0",
        summary="Agent IA de marketing et communication digitale — DATUM Academy.",
        description=DESCRIPTION,
        openapi_tags=TAGS,
        contact={"name": "DATUM Academy", "url": "https://datumacademy.com"},
        # La documentation générée n'est pas exposée en production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        swagger_ui_parameters={
            # Les sections restent repliées : la liste reste lisible quand les
            # modules se multiplieront.
            "docExpansion": "none",
            "filter": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
        },
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_error_handlers(app)
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    async def racine() -> Response:
        """Redirige vers la documentation.

        Sans cela, ouvrir http://localhost:8000 renvoie « 404 Not Found » et laisse
        croire que l'API n'a pas démarré. En production, où /docs est désactivé,
        on renvoie les informations utiles en JSON.
        """
        if settings.is_production:
            return JSONResponse(
                {"name": "IAGORA API", "version": app.version, "health": "/health"}
            )
        return RedirectResponse("/docs")

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["technique"],
        summary="État de l'API et de sa base",
        responses={503: {"description": "La base de données ne répond pas."}},
    )
    async def health() -> JSONResponse:
        """Indique si l'API et sa base répondent.

        Renvoie 503 quand la base est injoignable : l'API est alors démarrée mais
        incapable de travailler, et un orchestrateur doit le savoir.
        """
        base_ok = await check_database()
        corps = HealthResponse(
            status="ok" if base_ok else "degraded",
            environment=settings.ENVIRONMENT,
            database="ok" if base_ok else "unreachable",
        )
        code = status.HTTP_200_OK if base_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=code, content=corps.model_dump())

    logger.info(
        "API IAGORA démarrée · environnement=%s · passerelle sociale=%s",
        settings.ENVIRONMENT,
        settings.SOCIAL_GATEWAY,
    )
    return app


app = create_app()
