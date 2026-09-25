"""Routeur de la version 1 de l'API.

Chaque module métier y ajoute son routeur ; tout est monté sous /api/v1 par app.main.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.users.router import permissions_router
from app.modules.users.router import router as users_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(permissions_router)

# Les routeurs des prochains modules viendront ici : publications, media,
# social_accounts, messages, webinars, calendar, activity, notifications, webhooks.
