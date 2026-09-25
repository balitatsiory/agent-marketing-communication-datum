# Architecture — backend IAGORA

État au 25 septembre 2026 : **socle, `auth`, `users` et les tables de `social_accounts` sont
écrits et fonctionnent**. Le reste est conçu, pas encore codé.

## 0. Exécution

| | Aujourd'hui | Plus tard |
|---|---|---|
| PostgreSQL | **service Windows local**, port 5432, base `stage_iagora` | conteneur |
| API | **`uvicorn` dans le terminal**, `backend/.venv` | conteneur |
| Pourquoi | journaux visibles, rechargement immédiat, débogage depuis l'éditeur | démonstration et production en une commande |

`Dockerfile` et `docker-compose.yml` sont conservés et fonctionnels. Le passage de l'un à
l'autre se fait par `DATABASE_URL` dans `.env`. Détail des commandes : `backend/README.md`.

## 1. Vue d'ensemble

```
Prototype HTML/CSS  ──REST/JSON──►  FastAPI  ──►  PostgreSQL
                                      │
                                      ├──► LLM (texte) et génération d'images
                                      ├──► integrations/social ──► n8n (test) | Graph API (prod)
                                      └──◄ webhooks : Meta (messages), n8n (résultats)
```

FastAPI détient **les données et les règles métier**. n8n n'est qu'un exécuteur, utilisé en test.

## 2. Arborescence

```
backend/
├── app/
│   ├── main.py               création de l'app, CORS, montage des routeurs
│   ├── core/                 config, database, security, deps
│   ├── integrations/
│   │   ├── social/           base.py, n8n_gateway.py, meta_gateway.py, factory.py
│   │   ├── llm_client.py
│   │   └── storage.py
│   ├── modules/<domaine>/    models.py, schemas.py, router.py, service.py,
│   │                         constants.py, exceptions.py, dependencies.py
│   └── workers/              tâches planifiées
├── alembic/
├── tests/                    arborescence miroir de modules/
├── pyproject.toml
└── Dockerfile
```

**Domaines :** auth, users, publications, generation, calendar, messages, webinars,
social_accounts, activity, notifications, media, webhooks (settings plus tard).

**Responsabilités :** `router.py` lit la requête et appelle le service ; `service.py` porte les
règles métier et les transactions ; `models.py` décrit les tables ; `schemas.py` valide les échanges.
Un module appelle le **`service.py`** d'un autre, jamais son router ni ses modèles.

## 3. Couche sociale

`integrations/social/base.py` définit le contrat : publier, répondre, vérifier un compte.
Deux implémentations, choisies par `SOCIAL_GATEWAY` :

| Environnement | Valeur | Chemin |
|---|---|---|
| Test | `n8n` | webhooks n8n → Graph API |
| Production | `meta` | appel direct à Graph API |

Les modules ne connaissent jamais Meta directement : c'est ce qui rend OB-08 vérifiable.
**Apps Meta :** une seule tant que la production n'existe pas ; une seconde (Test App) avant la mise
en production, car une app n'a qu'une URL de webhook et l'auto-réponse de test ne doit pas atteindre
de vrais prospects.

## 4. Modèle de données

**PostgreSQL.** Les entités sont fortement reliées ; les parties variables tiennent en `JSONB`.
MongoDB a été écarté pour cette raison.

### Principes
- Clé primaire `id_<table>` en `BIGINT GENERATED ALWAYS AS IDENTITY`.
- Clé étrangère `id_<table_cible>`, ou `id_<table_cible>_<rôle>` s'il y en a plusieurs vers la même
  table (`id_users_author`, `id_users_approver`).
- Horodatages `timestamptz` **en UTC** ; affichage dans le fuseau de l'utilisateur.
- Identifiants externes dans `external_<source>_id`, **jamais** en clé primaire, avec contrainte
  d'unicité : c'est ce qui rend les webhooks idempotents.
- Suppression = archivage `deleted_at` ; anonymisation pour les données personnelles.

### Tables de référence
Toute valeur **affichée**, **porteuse de règles** ou **susceptible d'évoluer** vit dans une table de
référence à deux colonnes : `code` (technique, stable, utilisé par le code Python) et `label`
(affiché, modifiable). Les valeurs initiales sont posées par une migration Alembic.

`platforms` (avec `is_enabled`, `max_caption_length`), `formats` (`min_media_count`,
`max_media_count`), `platform_formats` (compatibilité réseau × format), `publication_statuses`,
`publication_target_statuses`, `publication_event_types`, `social_account_statuses`, `tones`.

Restent en `VARCHAR` + `CHECK` les valeurs purement techniques et figées : `messages.direction`,
`media.kind`, `language` (code ISO).

### État courant et historique
La ligne porte **l'état actuel** (statut, `scheduled_at`) ; deux tables **en ajout seul** portent
**tout le passé** :

- `publication_history` : type d'événement, statut après, `scheduled_at` après, `id_users`
  (vide = système), `changed_at`, `comment`, `details JSONB` ;
- `publication_target_history` : même principe par réseau, avec l'erreur Meta dans `details`.

Les dates passées (`published_at`, `approved_at`, approbateur) **ne sont pas stockées** : elles se
déduisent de l'historique. Seul le statut courant est recopié sur la ligne, parce qu'il est lu en
permanence. Une **seule fonction de service** modifie la ligne et écrit l'historique, dans la même
transaction. Les droits `UPDATE` et `DELETE` sont retirés sur les tables d'historique.

### Tables existantes

| Domaine | Tables | État |
|---|---|---|
| `users` | `users`, `permissions`, `user_permissions` | **en base** |
| `auth` | `refresh_tokens` | **en base** |
| `social_accounts` | `platforms`, `social_account_statuses`, `social_accounts`, `social_account_metrics` | **en base** |
| `publications` | publications, versions, cibles, historiques, tables de référence | conçues |
| `messages`, `webinars`, `activity`, `notifications`, `media` | — | conçues ou à concevoir |

Le détail colonne par colonne vit dans **`IAdocs/base-de-donnees.md`**, généré depuis la base à
partir des commentaires SQL. Chaque table et chaque colonne porte sa description : elle s'affiche
aussi dans DataGrip et pgAdmin.

**Pas encore modélisés :** webinaires, statistiques des publications, campagnes, base de
connaissances, newsletters. Voir `docs/TODO.md`.

### Contraintes : la limite des 63 caractères
PostgreSQL tronque tout identifiant à 63 octets, sans prévenir. Quand la convention de nommage
produit un nom plus long, on le raccourcit à la main — par exemple `fk_social_accounts_status`.
`tests/test_naming.py` vérifie automatiquement cette limite, le pluriel des tables, l'absence de
mot réservé et la forme des clés primaires.

## 5. API

REST, préfixe `/api/v1`, URL au pluriel en kebab-case, JSON en `snake_case`, dates ISO 8601 UTC.
Actions métier en sous-ressource : `POST /publications/{id}/approve`.
Pagination `{items, total, page, page_size}` ; erreurs `{error: {code, message}}` où `code` est
stable et `message` en français. `409` en cas de transition impossible ou de modification
concurrente (verrou optimiste sur `updated_at`).

GraphQL écarté : le front est en HTML/JS sans framework. Ajout possible plus tard via Strawberry,
en réutilisant les services.

## 6. Traitements de fond

| Tâche | Rôle |
|---|---|
| Planificateur de publications | prend les publications `scheduled` échues, les passe en `publishing` (ce qui évite le double envoi), appelle la couche sociale |
| Collecte des statistiques | par heure les 48 premières heures, puis par jour ; stories avant leur expiration |
| Renouvellement des jetons | signale les comptes à reconnecter avant expiration |
| Rappels d'événements | J-7, J-1, H-2 |

APScheduler au départ ; Celery et Redis si la charge le justifie.

## 7. Sécurité

Jetons Meta **chiffrés** (Fernet) et jamais journalisés (S-01). Authentification par JWT court +
jeton de renouvellement stocké **haché** et révocable. Droits attribués par un administrateur, toute
modification enregistrée (F-22, S-02). Webhooks Meta vérifiés par signature `X-Hub-Signature-256`.
Aucune donnée personnelle dans les journaux.

## 8. Environnements

| | Développement | Production |
|---|---|---|
| Exécution | Docker Compose (backend, PostgreSQL, n8n) | à définir |
| Couche sociale | n8n | Graph API directe |
| App Meta | app unique, mode développement | app validée + Test App pour le test |
| Base | PostgreSQL local | PostgreSQL dédié |

## 9. Décisions et raisons

| Décision | Raison |
|---|---|
| FastAPI plutôt que Flask | typage, validation Pydantic, documentation générée, asynchrone |
| Rangement par domaine | 12 domaines : un dossier par domaine reste lisible |
| PostgreSQL, pas NoSQL | données très reliées ; JSONB couvre le besoin de souplesse |
| Clés BIGINT identity, pas UUID | choix de l'équipe ; lisibilité des identifiants |
| Tables de référence | ajouter une valeur sans migration, libellés affichables, règles portées par la donnée |
| Historique en table, pas en colonne JSON | requêtes transverses, intégrité, immutabilité garantie par la base |
| n8n en test, Meta en prod | prototypage rapide d'un côté, moins de dépendances de l'autre |
