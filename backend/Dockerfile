# Image de l'API IAGORA.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Les dépendances d'abord : cette couche est réutilisée tant que
# requirements.txt ne change pas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# L'application ne tourne pas en root.
RUN useradd --create-home --uid 1000 iagora && chown -R iagora:iagora /app
USER iagora

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
