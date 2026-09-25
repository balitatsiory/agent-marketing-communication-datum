"""Fixtures partagées par tous les tests.

Les réglages sont posés ici, avant tout import de l'application : `app.core.database`
crée le moteur dès son chargement et a donc besoin d'une URL valide. Aucune connexion
n'est ouverte tant qu'une requête n'est pas exécutée.
"""

import os

os.environ["ENVIRONMENT"] = "test"
# La base de test est imposée : un test ne doit jamais pouvoir écrire dans la base de
# travail, même si un fichier .env est présent. TEST_DATABASE_URL permet de la changer.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://iagora:iagora@localhost:5432/stage_iagora_test",
)
# Ces deux clés sont imposées, et non « par défaut » : les tests doivent tourner avec
# des valeurs connues, même lorsqu'un fichier .env est présent dans l'environnement.
os.environ["JWT_SECRET_KEY"] = "cle-de-signature-reservee-aux-tests"
# Clé Fernet valide (32 octets encodés en base64), réservée aux tests.
os.environ["TOKEN_ENCRYPTION_KEY"] = "Y2xlLWRlLXRlc3QtaWFnb3JhLTMyLW9jdGV0cyEhISE="
os.environ.setdefault("ACCESS_TOKEN_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_DAYS", "7")
os.environ.setdefault("SOCIAL_GATEWAY", "n8n")
os.environ.setdefault("N8N_BASE_URL", "http://localhost:5678")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8123")
