# Backend — API IAGORA

API **FastAPI** de la plateforme IAGORA : authentification, utilisateurs et droits
pour l'instant, les autres modules viendront s'ajouter sous `app/modules/`.

- Python **3.12+**, FastAPI, SQLAlchemy 2 (asynchrone), Alembic
- PostgreSQL 16 avec l'extension `pgvector`, lancé dans Docker

## Prérequis

- Python 3.12 ou plus récent
- Docker Desktop (seulement pour la base de données)

## Démarrer en local

En développement, **seule la base tourne dans Docker** ; l'API tourne
directement sur le poste, avec rechargement automatique.

### 1. Lancer la base de données

Depuis la **racine du dépôt** :

```bash
docker compose up -d db
```

Ce qui est créé :

- le conteneur `iagora-db`, joignable sur `127.0.0.1:5433` (et non 5432, pour
  ne pas entrer en conflit avec un PostgreSQL déjà installé sur le poste) ;
- la base `iagora` et la base de test `iagora_test`, toutes deux avec
  l'extension `vector` (utilisateur `iagora`, mot de passe `iagora`).

> Le script `docker/postgres/init/` n'est joué qu'à la **première** création du
> volume. Pour le rejouer : `docker compose down -v` (les données sont perdues).

### 2. Créer l'environnement Python

Depuis le dossier `backend/` :

```powershell
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell)
# source .venv/bin/activate         # Linux / macOS
pip install -r requirements-dev.txt
```

`requirements-dev.txt` inclut `requirements.txt` et ajoute les outils de
développement (ruff, mypy, pytest).

### 3. Configurer le fichier `.env`

```powershell
copy .env.example .env               # cp .env.example .env sous Linux / macOS
```

Deux clés **doivent** être remplacées : l'API refuse de démarrer tant qu'elles
gardent leur valeur d'exemple.

```bash
# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"

# TOKEN_ENCRYPTION_KEY (clé Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

| Variable | Rôle | Valeur par défaut |
|---|---|---|
| `ENVIRONMENT` | `local`, `test` ou `production` | `local` |
| `DATABASE_URL` | Base de travail | `postgresql+asyncpg://iagora:iagora@127.0.0.1:5433/iagora` |
| `TEST_DATABASE_URL` | Base utilisée par pytest | `…/iagora_test` |
| `JWT_SECRET_KEY` | Signature des jetons d'accès | **à générer** |
| `ACCESS_TOKEN_MINUTES` | Durée du jeton d'accès | `15` |
| `REFRESH_TOKEN_DAYS` | Durée du jeton de renouvellement | `7` |
| `TOKEN_ENCRYPTION_KEY` | Chiffrement des secrets de plateformes | **à générer** |
| `CORS_ORIGINS` | Origines autorisées, séparées par des virgules | `http://localhost:4200,http://127.0.0.1:4200` |

### 4. Appliquer les migrations

```bash
alembic upgrade head
```

### 5. Charger les comptes de développement (facultatif)

```bash
python -m scripts.seed_dev
```

Le script refuse de s'exécuter si `ENVIRONMENT` n'est pas `local`.

| Adresse | Mot de passe | Sert à tester |
|---|---|---|
| `admin@iagora.example.com` | `Dev-Admin-2026` | le parcours administrateur |
| `simple@iagora.example.com` | `Dev-Simple-2026` | le refus 403 (authentifié, sans droit) |
| `desactive@iagora.example.com` | `Dev-Desac-2026` | la connexion d'un compte suspendu |
| `archive@iagora.example.com` | `Dev-Archi-2026` | l'exclusion des listes d'un compte archivé |

Voir [scripts/README.md](scripts/README.md).

### 6. Lancer l'API

```bash
uvicorn app.main:app --reload
```

| Adresse | Contenu |
|---|---|
| http://localhost:8000 | redirige vers la documentation |
| http://localhost:8000/docs | **Swagger** — tester les routes |
| http://localhost:8000/redoc | documentation ReDoc |
| http://localhost:8000/health | état de l'API et de la base |
| http://localhost:8000/openapi.json | spécification à importer dans Postman / EchoAPI |

Pour appeler une route protégée depuis Swagger : `POST /api/v1/auth/login`,
copier `access_token`, puis le coller via le bouton **Authorize**.

Le frontend Angular (`http://localhost:4200`) est déjà autorisé par `CORS_ORIGINS`.

## Démarrage rapide (récapitulatif)

```powershell
# racine du dépôt
docker compose up -d db

# backend/
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env               # puis générer les deux clés
alembic upgrade head
python -m scripts.seed_dev
uvicorn app.main:app --reload
```

## Tests et qualité

La base Docker doit tourner : les tests utilisent `TEST_DATABASE_URL`.

```bash
pytest              # tests
ruff check .        # lint
ruff format .       # formatage
mypy                # typage strict sur app/
```

## Migrations

```bash
alembic revision -m "description"   # nouvelle migration (dans alembic/versions/)
alembic upgrade head                # appliquer
alembic downgrade -1                # annuler la dernière
alembic current                     # version actuelle de la base
```

Les données fictives ne vont **jamais** dans une migration : une migration part
en production. Elles vont dans `scripts/seed_dev.py`.

## Structure

```
backend/
├── app/
│   ├── main.py            point d'entrée : CORS, erreurs, routeurs, /health
│   ├── api/v1.py          routeur /api/v1, chaque module y accroche le sien
│   ├── core/              réglages, base, sécurité, erreurs, pagination
│   └── modules/
│       ├── auth/          connexion, jetons
│       └── users/         utilisateurs et droits
├── alembic/               migrations
├── scripts/               données de développement
├── tests/
├── Dockerfile
└── requirements*.txt
```

Chaque module suit le même découpage : `models.py`, `schemas.py`, `service.py`,
`router.py`.

## Problèmes fréquents

- **`JWT_SECRET_KEY a gardé sa valeur d'exemple`** ou **`TOKEN_ENCRYPTION_KEY
  n'est pas une clé Fernet valide`** : générer les clés (étape 3).
- **`/health` renvoie 503 / `database: unreachable`** : la base n'est pas
  lancée (`docker compose ps`) ou `DATABASE_URL` ne pointe pas sur le port `5433`.
- **Le port 5433 est déjà pris** : changer le port publié dans
  `docker-compose.yml` et dans `DATABASE_URL` / `TEST_DATABASE_URL`.
- **La base de test n'existe pas** : le volume a été créé avant le script
  d'amorçage ; `docker compose down -v` puis `docker compose up -d db`.
