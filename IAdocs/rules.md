# Règles de code — IAGORA

> **Source complète :** [`CONTRIBUTING.md`](../CONTRIBUTING.md) à la racine du dépôt.
> Ce fichier en est le résumé opérationnel. Si les deux divergent, `CONTRIBUTING.md` fait foi et
> doit être corrigé. Si un outil (ruff, mypy) contredit les deux, **l'outil a raison**.

## Langue

| Élément | Langue |
|---|---|
| Identifiants, tables, colonnes, URL, codes de statut | **anglais** |
| Commentaires, docstrings, documentation, messages de commit | **français** |
| Messages d'erreur destinés à l'utilisateur | **français** |

Jamais de mélange dans un même identifiant.

## Structure

Un dossier par domaine dans `app/modules/` : `models.py`, `schemas.py`, `router.py`, `service.py`
(obligatoires), puis `constants.py`, `exceptions.py`, `dependencies.py` si besoin.

- `router.py` : lit la requête, appelle le service, renvoie la réponse. **Pas de SQL, pas de règle métier.**
- `service.py` : règles métier, transactions, appels aux intégrations. **Ne connaît pas HTTP.**
- Un module appelle le `service.py` d'un autre, **jamais** son router ni ses modèles.
- Le code partagé va dans `core/` ou `integrations/`, jamais recopié.
- Aucun module n'appelle Meta ou n8n directement : tout passe par `integrations/social/`.

## Nommage Python

`snake_case` pour les variables et fonctions, `PascalCase` pour les classes, `UPPER_SNAKE_CASE` pour
les constantes. Pas d'abréviations (`publication`, pas `pub`). Booléens en `is_`, `has_`, `can_`.

Verbes : `get_` (lève une erreur si absent), `find_` (renvoie `None`), `list_`, `create_`, `update_`,
`archive_`, `count_`, puis les verbes métier (`approve_publication`).

Suffixes : `_at` (date-heure UTC), `_on` (date), `_count`, `_minutes`, `_seconds`, `_url`.
Préfixe `id_` pour les identifiants.

**Un domaine de bout en bout :** dossier `publications/` · table `publications` · modèle
`Publication` · schémas `PublicationCreate/Update/Read` · service `create_publication` · routeur
`/api/v1/publications` · exception `PublicationNotFoundError` · tests `tests/modules/publications/`.

## Base de données

| Règle | Exemple |
|---|---|
| Table : `snake_case`, anglais, **pluriel** | `publications`, `social_accounts` |
| Table enfant : préfixée par le parent au singulier | `publication_versions` |
| Clé primaire : `id_<table>` en `BIGINT GENERATED ALWAYS AS IDENTITY` | `id_publications` |
| Clé étrangère : `id_<table_cible>`, ou `id_<table_cible>_<rôle>` | `id_users_author` |
| Horodatage : suffixe `_at`, **UTC**, `timestamptz` | `scheduled_at` |
| Identifiant externe : `external_<source>_id`, unique, jamais clé primaire | `external_meta_id` |
| Colonnes communes | `id_<table>`, `created_at`, `updated_at`, + `deleted_at` si archivable |

**Valeurs fermées :** table de référence (`code` + `label`) dès qu'une valeur est affichée, porte des
règles ou peut évoluer. `VARCHAR` + `CHECK` seulement pour le technique et figé (`media.kind`,
`messages.direction`).

**Jamais de mot réservé PostgreSQL** comme nom de table ou de colonne (`user`, `order`, `group`…) :
le pluriel nous en protège déjà.

**Historiques** : en ajout seul, droits `UPDATE`/`DELETE` retirés. Statut courant et ligne
d'historique écrits **dans la même transaction**, par une seule fonction de service.

**Contraintes** nommées par convention SQLAlchemy : `pk_`, `fk_`, `uq_`, `ix_`, `ck_`.

**Migrations Alembic** : une par changement, fichier `YYYYMMDD_HHMM_<description>.py`, relue avant
commit, **jamais modifiée** une fois fusionnée. Toute modification de `models.py` s'accompagne de sa
migration dans la même PR.

## API

`/api/v1`, noms au pluriel en kebab-case, actions métier en `POST /{id}/action`.
Clés JSON en `snake_case`, dates ISO 8601 UTC. Listes : `{items, total, page, page_size}`.
Erreurs : `{"error": {"code": "publication_not_found", "message": "…"}}`.
Codes : `201` création, `204` archivage, `401`, `403`, `404`, `409` (état ou conflit), `422`.

## Style

Ruff (format + lint), mypy, pytest. **Lignes de 100 caractères**, **annotations de type
obligatoires**, imports absolus. Pas d'appel bloquant dans du code `async` (`httpx.AsyncClient`,
`asyncio.sleep`). Pas de `print` : un logger par fichier. Pas de valeur magique : `constants.py`.
Un commentaire explique **pourquoi**, pas **quoi**. TODO signés : `# TODO(balita): …`.

## Configuration et journaux

Variables en `UPPER_SNAKE_CASE`, lues **uniquement** via `core/config.py`, ajoutées à
`.env.example`. Aucun secret dans Git. Jamais dans les journaux : mots de passe, jetons, emails ou
noms d'inscrits, contenu des messages privés — on journalise les **identifiants**.

## Tests

`tests/modules/<module>/test_service.py` et `test_router.py`.
Nom : `test_<action>_<condition>_<résultat_attendu>`. Aucun appel réel à Meta, n8n ou au LLM.
Tout bug corrigé s'accompagne d'un test qui l'aurait détecté.

## Git

Branches `feature/`, `fix/`, `docs/`, `refactor/`, `chore/` + sujet en kebab-case.
Commits : `type(module): description` en français, à l'impératif.
PR : un sujet, description « quoi / pourquoi / comment tester ».

**Avant chaque PR :** `ruff format` · `ruff check` · `mypy app` · `pytest` · migration incluse ·
`.env.example` à jour · aucun secret · nommage conforme.

## Règles de travail avec l'assistant

1. **Pas de code applicatif sans feu vert explicite** de l'utilisateur.
2. Les modifications du prototype se font dans le **dossier principal du dépôt**, pas dans un
   worktree, et **sans écraser** les modifications locales en cours.
3. Le dossier principal est sur `main` : on n'y commite pas ; une PR passe par une branche dédiée.
4. Toute décision prise est reportée dans `IAdocs/memory.md`.
