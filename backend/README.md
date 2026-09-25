# Backend IAGORA

API FastAPI de la plateforme IAGORA. Conventions : [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
Architecture et décisions : [`../IAdocs/architecture.md`](../IAdocs/architecture.md).
Tables et colonnes : [`../IAdocs/base-de-donnees.md`](../IAdocs/base-de-donnees.md).

**Mode d'exécution retenu : tout en local** — PostgreSQL installé sur le poste, API
lancée dans le terminal. Docker reste disponible pour la démonstration et la
production (dernière section).

## Démarrage

### Une seule fois

**1. Démarrer PostgreSQL** (service `postgresql-x64-16`), dans un terminal administrateur :

```bash
net start postgresql-x64-16
```

**2. Créer l'utilisateur et les deux bases**, avec le mot de passe défini à l'installation :

```bash
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE USER iagora WITH PASSWORD 'iagora';" -c "CREATE DATABASE "stage_iagora" OWNER iagora;" -c "CREATE DATABASE "stage_iagora_test" OWNER iagora;"
```

Deux bases : `stage_iagora` pour le travail, `stage_iagora_test` pour les tests, qui la
vident à chaque exécution.

**3. Préparer l'environnement Python** :

```bash
cd backend
```

```bash
python -m venv .venv
```

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

**4. Copier la configuration**, puis générer les deux clés indiquées dans le fichier :

```bash
cp .env.example .env
```

**5. Créer les tables et les valeurs initiales** :

```bash
.\.venv\Scripts\alembic.exe upgrade head
```

**6. Créer le premier administrateur** — la création de comptes exige déjà le droit
« administrer », que personne ne possède au départ :

```bash
.\.venv\Scripts\python.exe -m app.cli create-admin --email prenom.nom@datum-academy.fr --first-name Prenom --last-name Nom
```

### Au quotidien

```bash
cd backend
```

```bash
.\.venv\Scripts\activate
```

```bash
uvicorn app.main:app --reload
```

Les journaux s'affichent **dans le terminal**, le code se recharge à chaque sauvegarde,
`Ctrl+C` arrête.

| Adresse | Contenu |
|---|---|
| http://localhost:8000 | redirige vers la documentation |
| http://localhost:8000/docs | Swagger : essayer les endpoints |
| http://localhost:8000/redoc | la même documentation, en lecture |
| http://localhost:8000/health | état de l'API et de la base |

### Outils

```bash
pytest
```

```bash
ruff format . ; ruff check . --fix
```

```bash
mypy app
```

```bash
alembic revision --autogenerate -m "description du changement"
```

```bash
alembic upgrade head
```

## Tester l'API dans le navigateur

**http://localhost:8000/docs** — documentation Swagger, générée à partir du code.

1. Déplier `POST /api/v1/auth/login`, cliquer sur **Try it out**, renseigner email et
   mot de passe, puis **Execute**.
2. Copier le champ `access_token` de la réponse.
3. Cliquer sur **Authorize**, en haut à droite, coller le jeton, valider.
4. Les endpoints marqués d'un **cadenas** deviennent utilisables.

Le jeton d'accès dure 15 minutes ; `POST /api/v1/auth/refresh` en fournit un nouveau à
partir du `refresh_token`. L'autorisation survit au rechargement de la page.

Chaque endpoint documente son résumé, son corps de requête avec un exemple, et **toutes
ses réponses d'erreur** (401, 403, 404, 409, 422) au format unique
`{"error": {"code", "message"}}`. En production, `/docs` et `/redoc` sont désactivés.

## Arborescence

```
backend/
├── app/
│   ├── main.py              création de l'app, CORS, erreurs, montage des routeurs
│   ├── cli.py               commandes : create-admin, db-doc
│   ├── core/                socle technique, sans aucune règle métier
│   │   ├── config.py        réglages lus depuis .env, avec contrôle au démarrage
│   │   ├── database.py      moteur, session par requête, convention de nommage
│   │   ├── security.py      mots de passe, JWT, chiffrement des jetons Meta
│   │   ├── deps.py          session, utilisateur courant, vérification des droits
│   │   ├── errors.py        erreurs métier et format unique des réponses
│   │   └── reference.py     accès aux tables de référence, avec cache
│   ├── api/v1.py            rassemble les routeurs sous /api/v1
│   ├── modules/             un dossier par domaine métier
│   │   ├── auth/            connexion, jetons de renouvellement
│   │   ├── users/           comptes et droits
│   │   └── social_accounts/ réseaux, comptes raccordés, statistiques
│   └── workers/             traitements de fond (plus tard)
├── alembic/                 migrations
└── tests/                   arborescence miroir de modules/
```

Chaque module contient les mêmes fichiers : `models.py` (tables), `schemas.py` (entrées
et sorties de l'API), `router.py` (endpoints), `service.py` (règles métier), et au
besoin `constants.py` et `exceptions.py`.

**Règle de dépendance :** un module appelle le `service.py` d'un autre, jamais son
`router.py` ni ses modèles. Le code partagé vit dans `core/`, les services externes
dans `integrations/`.

## Endpoints disponibles

| Méthode | Chemin | Droit requis |
|---|---|---|
| `POST` | `/api/v1/auth/login` | — |
| `POST` | `/api/v1/auth/refresh` | — |
| `POST` | `/api/v1/auth/logout` | — |
| `GET` | `/api/v1/auth/me` | être connecté |
| `GET` `POST` | `/api/v1/users` | administrer |
| `GET` `PATCH` `DELETE` | `/api/v1/users/{id_users}` | administrer |
| `POST` | `/api/v1/users/me/password` | être connecté |
| `GET` | `/api/v1/permissions` | être connecté |
| `GET` | `/health` | — |

## Étapes

| # | Étape | État |
|---|---|---|
| 0 | Arborescence | **fait** |
| 1 | Outillage : ruff, mypy, pytest, `.env.example` | **fait** |
| 2 | Socle : `config`, `database`, `errors`, `/health` | **fait** |
| 3 | Sécurité, modules `auth` et `users`, droits F-22 | **fait** |
| 4 | Migrations Alembic et valeurs initiales | **fait** |
| 5 | Tables des réseaux et de leurs statistiques | **fait** |
| 6 | Collecte des statistiques Meta | en cours |
| 7 | Module `publications` | à venir |

Domaines à venir : `publications`, `generation`, `media`, `messages`, `webinars`,
`calendar`, `activity`, `notifications`, `webhooks`, puis `settings`.

## Repères

| Élément | Emplacement |
|---|---|
| Base de travail | PostgreSQL local, port 5432, base `stage_iagora` |
| Base de test | `stage_iagora_test`, vidée par `pytest` |
| Secrets locaux | `backend/.env` — ignoré par git |
| Environnement Python | `backend/.venv` — ignoré par git |
| Structure des tables | `backend/alembic/versions/` |
| Dictionnaire de données | `IAdocs/base-de-donnees.md` |

### Se connecter à la base depuis DataGrip ou pgAdmin

| Réglage | Valeur |
|---|---|
| Hôte | `localhost` |
| Port | `5432` |
| Base | `stage_iagora` |
| Utilisateur | `iagora` |
| Mot de passe | celui choisi à la création de l'utilisateur |

### Régénérer le dictionnaire de données

Après chaque migration qui ajoute ou modifie une table :

```bash
.\.venv\Scripts\python.exe -m app.cli db-doc > ..\IAdocs\base-de-donnees.md
```

Les descriptions viennent des attributs `comment` déclarés dans les modèles, appliqués
en base par migration : un seul texte, trois usages (code, base, document).

## Plus tard : exécution en conteneur

Le `Dockerfile` et le `docker-compose.yml` sont conservés. Ils serviront pour la
démonstration et la mise en production : tout se lance d'une commande, sans installer
ni Python ni PostgreSQL.

Pour y revenir : décommenter les lignes `POSTGRES_*` de `.env`, remplacer `DATABASE_URL`
par la variante `@postgres:5432`, puis

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

La base du conteneur est publiée sur le port **5433**, afin de ne pas entrer en conflit
avec le PostgreSQL du poste.

Deux pièges déjà rencontrés :
- `docker compose restart` **ne relit pas** `.env` : utiliser `up -d --force-recreate backend` ;
- sans `-d`, les journaux défilent dans le terminal et `Ctrl+C` arrête les conteneurs ;
  avec `-d`, les suivre par `docker compose -f backend/docker-compose.yml logs -f backend`.
