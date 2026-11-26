"""Routeur de la version 1 de l'API.

Chaque module métier y accroche son routeur ; le tout est monté sous /api/v1 par
app.main.
"""

from fastapi import APIRouter

from app.modules.ai_models.router import router as ai_models_router
from app.modules.auth.router import router as auth_router
from app.modules.email_accounts.router import router as email_accounts_router
from app.modules.media.router import router as media_router
from app.modules.newsletter.router import router as newsletter_router
from app.modules.notifications.router import router as notifications_router
from app.modules.publications.router import router as publications_router
from app.modules.social_accounts.router import router as social_accounts_router
from app.modules.users.router import router as users_router
from app.modules.webinars.router import public_router as public_registration_router
from app.modules.webinars.router import router as webinars_router
from app.modules.zoom_accounts.router import router as zoom_accounts_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(publications_router)
api_v1_router.include_router(social_accounts_router)
api_v1_router.include_router(ai_models_router)
api_v1_router.include_router(email_accounts_router)
api_v1_router.include_router(newsletter_router)
api_v1_router.include_router(zoom_accounts_router)
api_v1_router.include_router(webinars_router)
api_v1_router.include_router(public_registration_router)

# Les routeurs des modules suivants viendront ici, dans l'ordre de dépendance :
# notifications, comptes réseaux sociaux, génération de contenu,
# connecteurs, publications, calendrier, messagerie,
# tableau de bord, activité, base de connaissances, webhooks.
