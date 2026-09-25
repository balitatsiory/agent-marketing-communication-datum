# Guide de contribution — backend IAGORA

Ce document fixe les règles communes pour que n'importe qui puisse lire, reprendre
et faire évoluer le code sans deviner les conventions. En cas de doute : **suivre
ce qui existe déjà dans le module voisin**, puis proposer une modification de ce
guide si la règle manque.

Sommaire :
1. [Langue](#1-langue)
2. [Structure d'un module](#2-structure-dun-module)
3. [Nommage Python](#3-nommage-python)
4. [Base de données](#4-base-de-données)
5. [API REST](#5-api-rest)
6. [Style de code](#6-style-de-code)
7. [Configuration et secrets](#7-configuration-et-secrets)
8. [Logs et données personnelles](#8-logs-et-données-personnelles)
9. [Tests](#9-tests)
10. [Git : branches, commits, pull requests](#10-git--branches-commits-pull-requests)
11. [Checklist avant pull request](#11-checklist-avant-pull-request)

---

## 1. Langue

| Élément | Langue | Exemple |
|---|---|---|
| Identifiants (variables, fonctions, classes, tables, colonnes, URL, clés JSON) | **anglais** | `scheduled_at`, `PublicationService` |
| Valeurs techniques (statuts, codes d'erreur) | **anglais** | `pending_review`, `publication_not_found` |
| Commentaires, docstrings, documentation | **français** | `# Meta refuse les légendes > 2 200 caractères` |
| Messages de commit, descriptions de PR | **français** | `feat(publications): ajoute la validation` |
| Messages d'erreur lisibles par l'utilisateur | **français** | `"La publication est déjà publiée."` |

Pas de mélange dans un même identifiant (`get_publication_programmees` est interdit).

---

## 2. Structure d'un module

Le code est rangé **par domaine** : un dossier par domaine métier dans `app/modules/`.

```
app/modules/publications/
├── models.py         tables SQLAlchemy du domaine
├── schemas.py        modèles Pydantic (entrée / sortie de l'API)
├── router.py         endpoints FastAPI — fins, sans logique métier
├── service.py        logique métier — seul point d'entrée pour les autres modules
├── constants.py      statuts, formats, limites (enums)
├── exceptions.py     erreurs métier du domaine
└── dependencies.py   dépendances FastAPI propres au domaine (si besoin)
```

Seuls `models.py`, `schemas.py`, `router.py` et `service.py` sont obligatoires ; les
autres fichiers sont créés quand ils servent.

**Responsabilités :**

| Fichier | Fait | Ne fait pas |
|---|---|---|
| `router.py` | lit la requête, appelle le service, renvoie la réponse | requêtes SQL, règles métier |
| `service.py` | règles métier, transactions, appels aux intégrations | connaître HTTP (`Request`, codes de statut) |
| `models.py` | décrire les tables | logique métier |
| `schemas.py` | valider et formater les données échangées | accès base de données |

**Règles entre modules :**
- Un module peut appeler le **`service.py`** d'un autre module.
- Un module **n'importe jamais** le `router.py`, ni les `models.py` d'un autre module
  pour faire ses propres requêtes.
  Exemple : `publications` écrit dans l'historique via `activity.service.log_activity(...)`,
  pas en insérant directement dans `activity_logs`.
- Le code partagé va dans `app/core/` (config, base, sécurité) ou
  `app/integrations/` (Meta, n8n, LLM, stockage) — jamais copié entre modules.
- Les modules n'appellent jamais Meta ou n8n directement : ils passent par
  `app/integrations/social/`.

---

## 3. Nommage Python

### Règles générales (PEP 8)

| Élément | Convention | Exemple |
|---|---|---|
| Variables, fonctions, méthodes, modules | `snake_case` | `scheduled_at`, `publish_now()` |
| Classes | `PascalCase` | `PublicationVersion` |
| Constantes | `UPPER_SNAKE_CASE` | `MAX_CAPTION_LENGTH` |
| Membres d'enum | `UPPER_SNAKE_CASE`, valeur en `snake_case` | `PENDING_REVIEW = "pending_review"` |
| Éléments privés au module | préfixe `_` | `_build_caption()` |

### Règles de sens

- **Pas d'abréviations** sauf les usuelles (`id`, `url`, `api`, `db`, `llm`) :
  `publication` et non `pub`, `message` et non `msg`.
- **Booléens** : préfixe `is_`, `has_`, `can_`, `should_` → `is_active`, `has_media`.
- **Fonctions** : commencent par un verbe.

  | Verbe | Usage |
  |---|---|
  | `get_` | un élément, lève une erreur s'il n'existe pas |
  | `find_` | un élément, renvoie `None` s'il n'existe pas |
  | `list_` | plusieurs éléments |
  | `create_` / `update_` / `archive_` | écriture |
  | `count_` | un nombre |
  | verbe métier | `approve_publication`, `schedule_publication`, `import_registrations` |

- **Collections au pluriel**, éléments au singulier :
  `for publication in publications`.
- **Suffixes selon le type** :

  | Suffixe | Type | Exemple |
  |---|---|---|
  | `_at` | date + heure (UTC) | `published_at` |
  | `_on` | date seule | `planned_on` |
  | préfixe `id_` | identifiant (voir §4) | `id_publications`, `id_users_author` |
  | `_count` | nombre | `registration_count` |
  | `_minutes`, `_seconds` | durée (unité explicite) | `duration_minutes` |
  | `_url` | lien | `replay_url` |

### Nommage d'un domaine de bout en bout

Exemple avec les publications — chaque nouveau domaine suit le même schéma :

| Couche | Nom |
|---|---|
| Dossier | `app/modules/publications/` |
| Table | `publications` |
| Modèle SQLAlchemy | `Publication` |
| Schémas Pydantic | `PublicationCreate`, `PublicationUpdate`, `PublicationRead`, `PublicationListItem` |
| Fonctions du service | `create_publication`, `get_publication`, `list_publications`, `approve_publication` |
| Exception | `PublicationNotFoundError` |
| Routeur | préfixe `/api/v1/publications`, tag `publications` |
| Fonction d'endpoint | même nom que la fonction du service appelée |
| Tests | `tests/modules/publications/test_service.py`, `test_router.py` |

---

## 4. Base de données

PostgreSQL, SQLAlchemy 2, migrations Alembic.

### Tables

| Règle | Exemple |
|---|---|
| `snake_case`, anglais, **pluriel** | `publications`, `social_accounts` |
| Table enfant : préfixée par le parent au singulier | `publication_versions`, `webinar_registrations` |
| Table d'association : les deux noms, le premier au singulier | `publication_version_media` |

### Colonnes

| Règle | Exemple |
|---|---|
| `snake_case`, singulier | `title`, `caption` |
| Clé primaire : `id_<table>`, déclarée `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | `id_users`, `id_publications` |
| Clé étrangère : `id_<table_cible>` | `id_social_accounts`, `id_publications` |
| Clé étrangère avec un rôle, ou plusieurs vers la même table : `id_<table_cible>_<rôle>` | `id_users_author`, `id_users_approver` |
| Horodatage : suffixe `_at`, **toujours en UTC** avec fuseau (`timestamptz`) | `scheduled_at` |
| Booléen : préfixe `is_` / `has_` | `is_generated_by_ai` |
| Statut : clé étrangère vers une **table de référence** | `id_publication_statuses` |
| Valeurs techniques figées : `VARCHAR` + contrainte `CHECK` (pas d'enum PostgreSQL) | `media.kind`, `messages.direction` |
| Codes et statuts : anglais, `snake_case` | `draft`, `pending_review`, `published` |
| Données souples : `JSONB`, nommée `metadata`, `payload` ou `details` | `activity_logs.metadata` |

**Colonnes présentes dans toutes les tables :** `id_<table>`, `created_at`, `updated_at`.

### Valeurs fermées : table de référence ou contrainte CHECK ?

Une **table de référence** dès que la valeur est **affichée à l'écran**, **porte des règles** ou
**peut évoluer**. Elle a deux colonnes : `code` (technique, stable, utilisé par le code Python, on
ne le renomme jamais) et `label` (affiché, modifiable librement), plus au besoin `sort_order`,
`is_enabled` et les règles propres à la valeur. Les valeurs initiales sont posées par une migration
Alembic, pour que toutes les bases soient identiques.

Exemples : `publication_statuses`, `publication_target_statuses`, `publication_event_types`,
`platforms`, `formats`, `platform_formats`, `social_account_statuses`, `tones`.

Un `VARCHAR` + `CHECK` **seulement** pour une valeur purement technique et figée, jamais affichée
telle quelle : `media.kind` (image, vidéo), `messages.direction` (entrant, sortant), `language`
(code ISO).

Dans les deux cas, le code Python s'appuie sur le **`code`**, jamais sur l'identifiant numérique,
et les codes sont repris dans un `Enum` Python du module (`constants.py`) pour éviter les fautes de
frappe.

> `GENERATED ALWAYS` interdit d'insérer une valeur d'identifiant à la main. Lors d'un
> import ou d'une reprise de données, il faut écrire explicitement
> `OVERRIDING SYSTEM VALUE`, puis remettre la séquence à niveau.
> Les identifiants venant de l'extérieur (Meta, site Datum) ne sont **jamais** des clés
> primaires : ils vont dans une colonne `external_<source>_id` avec une contrainte
> d'unicité, par exemple `external_meta_id`.
**Tables archivables** (publications, webinaires, comptes…) : `deleted_at` en plus.
Une ligne archivée a `deleted_at` renseigné ; les requêtes standard l'excluent.

> **Exception — données personnelles** (inscrits aux webinaires, interlocuteurs des
> conversations) : sur demande d'effacement, on **anonymise** (nom, email vidés)
> au lieu d'archiver.

### Noms des contraintes et index

Configurés une fois dans `app/core/database.py` (convention de nommage SQLAlchemy),
pour que les migrations Alembic soient stables et lisibles :

| Type | Format | Exemple |
|---|---|---|
| Clé primaire | `pk_<table>` | `pk_publications` |
| Clé étrangère | `fk_<table>_<colonne>_<table_cible>` | `fk_publications_id_users_author_users` |
| Unicité | `uq_<table>_<colonne>` | `uq_users_email` |
| Index | `ix_<table>_<colonne>` | `ix_publications_scheduled_at` |
| Check | `ck_<table>_<nom>` | `ck_publications_status` |

> **Limite de 63 caractères.** PostgreSQL tronque tout identifiant à 63 octets, **sans
> prévenir** : la contrainte existe alors sous un autre nom que celui déclaré, et la
> migration qui la supprimerait échoue. Quand la convention dépasse cette longueur, on
> donne un nom court à la main, par exemple `fk_social_accounts_status` au lieu de
> `fk_social_accounts_id_social_account_statuses_social_account_statuses` (70 caractères).
> Le test `tests/test_naming.py` vérifie automatiquement cette limite, ainsi que le
> pluriel des tables et la forme des clés primaires.

### Migrations Alembic

- **Une migration par changement logique**, avec un message clair :
  `add_webinar_registrations`.
- Fichier nommé `YYYYMMDD_HHMM_<description>.py`.
- Les migrations autogénérées sont **relues** avant commit (Alembic rate les
  renommages et certains changements de type).
- **Ne jamais modifier une migration déjà fusionnée** dans `main` : en créer une nouvelle.
- Toute modification de `models.py` est accompagnée de sa migration dans la même PR.

---

## 5. API REST

### URL

| Règle | Exemple |
|---|---|
| Préfixe versionné | `/api/v1/...` |
| Noms au **pluriel**, en `kebab-case` | `/api/v1/social-accounts` |
| Pas de verbe pour le CRUD | `GET /publications`, `POST /publications` |
| Actions métier : sous-ressource en `POST` | `POST /publications/{id_publications}/approve` |
| Imbrication limitée à un niveau | `/webinars/{id_webinars}/registrations` |
| Endpoints publics / webhooks séparés | `/api/v1/webhooks/meta`, `/api/v1/webhooks/n8n/...` |

### Méthodes et codes de retour

| Action | Méthode | Code en cas de succès |
|---|---|---|
| Lire | `GET` | `200` |
| Créer | `POST` | `201` |
| Modifier partiellement | `PATCH` | `200` |
| Archiver | `DELETE` | `204` |
| Action métier | `POST` | `200` |

| Erreur | Code |
|---|---|
| Données invalides | `422` |
| Non authentifié | `401` |
| Rôle insuffisant | `403` |
| Ressource introuvable ou archivée | `404` |
| Action impossible dans l'état actuel (ex. approuver une publication déjà publiée) | `409` |

### Format JSON

- Clés en **`snake_case`**, identiques aux colonnes : `scheduled_at`, `id_social_accounts`.
- Dates en **ISO 8601 UTC** : `"2026-09-17T15:00:00Z"`. Le front convertit
  en heure locale.
- Listes paginées, toujours la même enveloppe :
  `{ "items": [...], "total": 42, "page": 1, "page_size": 20 }`
  avec les paramètres `?page=1&page_size=20` (maximum 100).
- Filtres en paramètres de requête, mêmes noms que les champs :
  `?status=published&id_social_accounts=...`
- Erreurs, toujours le même format :
  `{ "error": { "code": "publication_not_found", "message": "Publication introuvable." } }`
  — `code` est stable (le front s'en sert), `message` est en français.

---

## 6. Style de code

### Outils (source de vérité)

| Outil | Rôle | Commande |
|---|---|---|
| **ruff format** | mise en forme automatique | `ruff format .` |
| **ruff check** | lint + tri des imports | `ruff check . --fix` |
| **mypy** | vérification des types | `mypy app` |
| **pytest** | tests | `pytest` |

La configuration est dans `pyproject.toml`. **Si l'outil et ce guide divergent,
l'outil a raison** — et le guide doit être corrigé.

### Règles

- **Longueur de ligne : 100 caractères.**
- **Annotations de type obligatoires** sur toutes les fonctions (paramètres et retour).
- **Imports** : absolus (`from app.modules.activity import service as activity_service`),
  triés par ruff — bibliothèque standard, puis dépendances, puis `app`.
- **Asynchrone** : les endpoints et services qui accèdent à la base ou au réseau
  sont `async`. Pas d'appel bloquant (`requests`, `time.sleep`) dans du code `async` :
  utiliser `httpx.AsyncClient`, `asyncio.sleep`.
- **Chaînes** : f-strings. Jamais de f-string dans une requête SQL.
- **Pas de `print`** : utiliser le logger (voir §8).
- **Pas de valeur magique** : les limites et statuts vont dans `constants.py`.
- **Fonctions courtes** : au-delà d'environ 40 lignes, découper.
- **Pas de code mort ni de code commenté** : Git garde l'historique.

### Commentaires et docstrings

- Docstring (français) sur chaque fonction **publique** d'un `service.py` : ce qu'elle
  fait, les erreurs levées. Format Google (`Args:`, `Returns:`, `Raises:`).
- Un commentaire explique **pourquoi**, pas **quoi** :
  - ✅ `# Meta met jusqu'à 60 s à traiter une vidéo : on interroge le statut du conteneur`
  - ❌ `# boucle sur les publications`
- TODO toujours signés et, si possible, liés à un ticket :
  `# TODO(balita): gérer LinkedIn quand l'intégration sera ouverte`

---

## 7. Configuration et secrets

- Variables d'environnement en `UPPER_SNAKE_CASE`, regroupées par préfixe :
  `DATABASE_URL`, `JWT_SECRET_KEY`, `META_APP_ID`, `META_APP_SECRET`,
  `N8N_BASE_URL`, `LLM_API_KEY`, `SOCIAL_GATEWAY` (`n8n` | `meta`).
- Lues **uniquement** via `app/core/config.py` — jamais `os.environ` ailleurs.
- Toute nouvelle variable est ajoutée à **`.env.example`**, avec un commentaire et une
  valeur factice.
- **Aucun secret dans Git** : `.env` est ignoré. Les jetons Meta sont chiffrés en base.

---

## 8. Logs et données personnelles

- Un logger par fichier : `logger = logging.getLogger(__name__)`.
- Niveaux : `debug` (détail de développement), `info` (événement métier normal :
  publication envoyée), `warning` (anomalie récupérée : nouvelle tentative Meta),
  `error` (échec à traiter).
- **Jamais dans les logs** : mots de passe, jetons, secrets, emails ou noms
  d'inscrits, contenu des messages privés. Logger les **identifiants**
  (`id_webinar_registrations`)
  plutôt que les données.

---

## 9. Tests

- Arborescence miroir du code : `tests/modules/<module>/test_service.py`,
  `tests/modules/<module>/test_router.py`.
- Nom : `test_<action>_<condition>_<résultat_attendu>`
  → `test_approve_publication_already_published_raises_conflict`.
- Fixtures partagées dans `tests/conftest.py`.
- **Aucun appel réel** à Meta, n8n ou au LLM : les intégrations sont simulées.
- Tout bug corrigé s'accompagne d'un test qui l'aurait détecté.

---

## 10. Git : branches, commits, pull requests

### Branches

- `main` est protégée : on n'y pousse jamais directement.
- Format : `<type>/<sujet-court>` en `kebab-case`.

| Type | Usage | Exemple |
|---|---|---|
| `feature/` | nouvelle fonctionnalité | `feature/publication-approval` |
| `fix/` | correction de bug | `fix/meta-token-refresh` |
| `docs/` | documentation | `docs/contributing` |
| `refactor/` | réorganisation sans changement de comportement | `refactor/social-gateway` |
| `chore/` | outillage, dépendances, config | `chore/ruff-config` |

### Commits

Format [Conventional Commits](https://www.conventionalcommits.org/fr/),
description **en français**, à l'impératif présent :

```
<type>(<module>): <description courte>
```

- `feat(publications): ajoute l'approbation d'une publication`
- `fix(social_accounts): renouvelle le jeton Meta avant expiration`
- `chore(deps): met à jour FastAPI`

Types : `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
Un commit = un changement cohérent.

### Pull requests

- **Petites** : un sujet par PR.
- Description : **quoi**, **pourquoi**, **comment tester**.
- Toute PR qui touche un module met à jour sa migration, ses tests et
  `.env.example` si nécessaire.

---

## 11. Checklist avant pull request

- [ ] `ruff format .` et `ruff check .` sans erreur
- [ ] `mypy app` sans erreur
- [ ] `pytest` passe
- [ ] Migration Alembic incluse et relue si `models.py` a changé
- [ ] `.env.example` à jour si une variable a été ajoutée
- [ ] Aucun secret, jeton ou donnée personnelle dans le code ou les logs
- [ ] Nommage conforme à ce guide
- [ ] Description de PR : quoi, pourquoi, comment tester
