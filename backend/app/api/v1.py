"""Routeur de la version 1 de l'API.

Chaque module métier y accroche son routeur ; le tout est monté sous /api/v1 par
app.main.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.media.router import router as media_router
from app.modules.social_accounts.router import router as social_accounts_router
from app.modules.users.router import router as users_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(social_accounts_router)

# Les routeurs des modules suivants viendront ici, dans l'ordre de dépendance :
# notifications, comptes réseaux sociaux, génération de contenu,
# connecteurs, publications, calendrier, webinaires, newsletters, messagerie,
# tableau de bord, activité, base de connaissances, webhooks.
