# Image de l'API IAGORA.
FROM python:3.12-slim

# Python : pas de fichiers .pyc, sortie non tamponnée (les journaux arrivent tout de suite).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Les dépendances sont copiées seules : cette couche est réutilisée tant que
# requirements.txt ne change pas, ce qui accélère les reconstructions.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Outils de développement (ruff, mypy, pytest) : installés seulement quand
# docker-compose le demande. L'image de production reste sans eux.
ARG INSTALL_DEV=false
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

# Puis le code.
COPY . .

# L'application ne tourne pas en root.
RUN useradd --create-home --uid 1000 iagora && chown -R iagora:iagora /app
USER iagora

EXPOSE 8000

# --reload est utile en développement ; il sera retiré pour la production.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
