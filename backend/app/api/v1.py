"""Routeur de la version 1 de l'API.

Chaque module métier y accroche son routeur ; le tout est monté sous /api/v1 par
app.main.
"""

from fastapi import APIRouter

api_v1_router = APIRouter()

# Les routeurs des modules viendront ici, dans l'ordre de dépendance :
# authentification, utilisateurs et droits, média, notifications, comptes
# réseaux sociaux, génération de contenu, connecteurs, publications, calendrier,
# webinaires, newsletters, messagerie, tableau de bord, activité, base de
# connaissances, webhooks.
