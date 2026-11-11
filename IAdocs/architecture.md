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
`max_media_count`), `platform_formats` (compatibilité réseau × format, et `format_duration_hours`, proposée), `publication_statuses`,
`publication_event_types`, `delivery_statuses` (statuts d'une cible), `delivery_event_types`
(événements d'une cible), `social_account_statuses`, `tones`.

Restent en `VARCHAR` + `CHECK` les valeurs purement techniques et figées : `messages.direction`,
`media.kind`, `language` (code ISO).

### État courant et historique
La ligne porte **l'état actuel** (statut, et sur la cible la date en vigueur `current_scheduled_at_denormalized`) ; deux tables **en ajout seul** portent
**tout le passé** :

- `history_publications` : type d'événement, statut après, `id_users_changed_by`
  (vide = aucune personne : planificateur ou réseau), `created_at`, `commentaires_users` ;
- `history_publication_targets` : même principe par réseau, avec `new_scheduled_at` (nouvelle date posée par l'événement : seulement pour `created`, `scheduled`, `rescheduled` et `retried`, vide sinon), `new_description_publication_targets` (texte de la légende posé par `description_edited` ou `description_edited_on_platform`, vide sinon), `id_users_changed_by` (vide = aucune personne), `commentaires_users` et l'erreur Meta dans `error_message_json` (JSONB).

Chaque ligne dit l'**événement** et le **statut obtenu après** : un événement n'est pas un statut
(`sent` donne `publishing`, `unscheduled` donne `awaiting_scheduling`).

Les dates passées (`published_at`, `approved_at`, approbateur) **ne sont pas stockées** : elles se
déduisent de l'historique. Seuls le statut courant et, sur la cible, la date en vigueur
(`current_scheduled_at_denormalized`) sont recopiés sur la ligne, parce qu'ils sont lus en
permanence. Une **seule fonction de service** modifie la ligne et écrit l'historique, dans la même
transaction. Les droits `UPDATE` et `DELETE` sont retirés sur les tables d'historique.

### Publications : statuts, événements et règles
> **Validé le 15 octobre** : les tables `publications` (4 colonnes), `history_publications`,
> `history_publication_targets`, `publication_targets`, `publication_event_types` et
> `delivery_event_types`, ainsi que les valeurs de `delivery_statuses` et de
> `publication_statuses`. **Reste proposé** : le droit `validate_own_publications` (migration de
> la table `permissions`), et le statut et l'événement `cancelled` (annulation avant envoi), confirmés
> en principe le 15 octobre mais pas encore validés « vert ».

**Deux niveaux.** `publications` porte le contenu commun (format) ; `publication_targets` porte un
réseau (un compte social) avec sa légende, son statut et sa date en vigueur. Une publication
**naît à la première soumission** : il n'y a pas de brouillon enregistré côté serveur, et
`publications.created_at` est l'heure de soumission. L'auteur est celui de la ligne
`created_submitted`.

**Statuts d'une publication** (`publication_statuses`, 9 validés, plus `cancelled` proposé) : `needs_correction` (à corriger, remplace
`draft`), `pending_review` (en relecture), `approved`, `scheduled`, `publishing`, `published`,
`partially_published`, `failed`, `removed`, et `cancelled` (annulée ; proposé).

**Événements d'une publication** (`publication_event_types`, 12 validés, plus `cancelled` proposé) : `created_submitted` (première
soumission seulement), `submitted` (nouvelle soumission après correction), `approved`,
`correction_requested`, `content_modified` (contenu modifié après approbation : retour en
relecture), `scheduled`, `sent`, `published`, `partially_published`, `failed`, `retried`, `removed`, et `cancelled` (annulée avant envoi ; proposé).

**Statuts d'une cible** (`delivery_statuses`, 6 validés, plus `cancelled` proposé) : `awaiting_scheduling` (en attente de
programmation, remplace `draft` ; peut porter une date souhaitée), `scheduled`, `publishing`,
`published`, `failed`, `removed`, et `cancelled` (annulée ; proposé).

**Événements d'une cible** (`delivery_event_types`, 11 validés, plus `cancelled` proposé) : `created`, `scheduled`, `rescheduled`,
`retried`, `sent`, `published`, `failed`, `removed`, `description_edited`,
`description_edited_on_platform` (description modifiée sur le réseau ; la cible reste publiée),
`unscheduled` (retirée de la programmation ; la cible repasse en `awaiting_scheduling`), `cancelled` (annulée avant envoi, la cible est terminée ; proposé).

**Statut de la publication une fois programmée = résumé de ses cibles** : aucune n'est partie →
`scheduled` ; au moins une est partie et d'autres ne sont pas terminées → `publishing` ; toutes
terminées → `published` (toutes publiées), `partially_published` (mélange) ou `failed` (toutes en
échec). Une relance fait repasser `partially_published` en `publishing`. Une cible `cancelled` à côté de cibles publiées : statut de la publication à trancher.

**Expiration des stories (proposé).** Une story disparaît du réseau d'elle-même : ce n'est ni un statut
ni un événement, la cible reste `published`. La durée de vie est portée par
`platform_formats.format_duration_hours` (entier, en heures, nullable : 24 pour la ligne réseau × `story`,
vide quand le format n'expire pas). Elle est propre à chaque couple réseau × format. L'écran affiche
« Expirée » quand ce couple a une durée et que la date de l'événement `published` de la cible, lue dans
`history_publication_targets`, a plus de cette durée. Le couple se retrouve par le compte de la cible
(`social_accounts` → `platforms`) et le format de la publication. Aucune colonne ni ligne de journal n'est
ajoutée sur les publications ; « Expirée » reste distinct de « Retirée » (`removed`, geste d'une personne).

**Annulation avant envoi (proposé : `cancelled`).** Annuler abandonne ce qui n'est pas encore parti.
C'est une opération locale : rien n'est engagé côté réseau avant l'heure, donc aucun appel au réseau.
Elle est définitive (pour renvoyer, on recrée une publication), demandée avec confirmation à l'écran,
et un motif facultatif va dans `commentaires_users`.

- **Cible** : `cancelled` depuis `awaiting_scheduling` ou `scheduled`. Une cible `failed` ne s'annule
  pas : l'échec reste visible. Une cible `publishing` ne peut plus être annulée.
- **Publication** : `cancelled` depuis `needs_correction`, `pending_review`, `approved` ou
  `scheduled`. L'annulation de la publication annule en cascade ses cibles non parties, chacune avec
  sa ligne de journal. Quand toutes les cibles sont annulées une à une, la publication passe d'elle-même à `cancelled`.
- **Course avec le planificateur** : l'annulation et l'envoi sont des changements conditionnels (« seulement
  si la cible est encore `scheduled` ») ; le premier arrivé gagne, l'autre reçoit un refus.
- **Qui** : l'auteur tant que la publication est `needs_correction` ou `pending_review` (il retire sa
  propre soumission) ; une personne ayant `publish`, jusqu'à l'envoi. Aucun autre droit n'est
  nécessaire : `validate_own_publications` ne sert pas à annuler.

**Qui peut modifier quoi, selon l'étape**

| Étape | Autorisé | Écrit dans les journaux |
|---|---|---|
| Soumission | date **obligatoire**, strictement dans le futur | publication : `created_submitted` → `pending_review` ; cibles : `created` → `awaiting_scheduling`, `new_scheduled_at` = date souhaitée (auteur : l'auteure) |
| `needs_correction` | l'auteur modifie tout (description, médias, format, date) | rien tant qu'il n'a pas renvoyé ; à la nouvelle soumission, en un seul instant : `submitted` + un `description_edited` ou `rescheduled` par cible modifiée |
| `pending_review` | l'auteur modifie la description et la date ; médias, format et comptes verrouillés. Le relecteur : `approved` ou `correction_requested` | `description_edited`, `rescheduled` (cibles toujours `awaiting_scheduling`) |
| Approbation | droit `canApprove` (voir plus bas) | `approved` puis aussitôt `scheduled` (même instant, auteur = l'approbateur) sur la publication, et `scheduled` sur chaque cible (`new_scheduled_at` = date) si la date est future ; sinon la publication reste `approved` et une personne ayant `publish` la programme à la main (événement `scheduled`, pas `rescheduled`) |
| `approved` / `scheduled` | description : si l'utilisateur peut approuver → `description_edited` seul ; sinon `content_modified` (publication → `pending_review`) + `description_edited` (statut de la cible inchangé) + `unscheduled` par cible programmée. Date : `rescheduled`, statut inchangé, sans nouvelle validation, droit `publish`. Médias ou format : on retire (`removed` sur la publication et ses cibles) et on recrée | voir colonne « Autorisé » |
| `publishing` | tout est verrouillé | — |
| Annulation avant envoi | l'auteur en `needs_correction` ou `pending_review` ; droit `publish` jusqu'à l'envoi | cible : `cancelled` → `cancelled` ; publication : `cancelled` → `cancelled`, avec cascade sur les cibles non parties |
| Cible `published` | description corrigée sur le réseau puis dans l'application : `description_edited_on_platform` (droit `publish`), statut `published` inchangé, pas de nouvelle validation, aucune ligne côté publication | — |
| Cible `failed` | description corrigeable seulement par quelqu'un qui peut approuver (`description_edited`, statut `failed`) ; puis `retried` : la cible repasse en `scheduled` avec `new_scheduled_at` (maintenant ou date choisie) et la publication en `publishing`. Seule une cible `failed` peut être relancée | `retried` |

Les médias d'une publication (`publication_media`) ne sont jamais modifiés.

**Auteur des lignes.** Toute ligne déclenchée par une personne, y compris celles écrites en
cascade, porte cette personne. `id_users_changed_by` reste vide **uniquement** pour `sent`,
`published`, `partially_published` et `failed` (planificateur ou réseau). Pas de contrainte `CHECK`
en base : la règle est tenue par la fonction de service.

**Droits.** Codes de la table `permissions` (libellé français entre parenthèses) : `create`
(Créer), `review` (Valider), `publish` (Publier), `read` (Lire), `admin` (Administrer), tous
existants, et `validate_own_publications` (Valider ses propres publications), nouveau, ajouté
par migration de la table `permissions`. `review` : relire, approuver, demander une correction.
`publish` : programmation manuelle, report après approbation, correction sur le réseau (la
relance d'une cible en échec et le retrait d'une publication lui sont proposés, à confirmer), annulation avant envoi (proposée, avec `cancelled` ; ouverte aussi à l'auteur avant l'approbation). Une seule règle : `canApprove(utilisateur, publication)` = a `review`
**et** (n'est pas l'auteur **ou** a `validate_own_publications`).

**Verrou optimiste à l'approbation.** `publications` n'a pas de `updated_at` : la page de
relecture retient comme version le plus grand `id` du journal des cibles de la publication. À
l'approbation, le serveur ouvre une transaction, verrouille la ligne de la publication, vérifie
qu'elle est bien en `pending_review`, puis compare cette version à la dernière ; si elle est
différente il répond `409` (« version périmée, actualise »). La demande de correction ne fait
aucun contrôle de version.

**Scénario A : parcours sans accroc**

| Quand | Journal | Événement → statut | Auteur |
|---|---|---|---|
| 14 oct 09:20 | publications | `created_submitted` → `pending_review` | Marie |
| 14 oct 09:20 | cibles 101, 102, 103 | `created` → `awaiting_scheduling` (`new_scheduled_at` = 20 oct 09:00) | Marie |
| 14 oct 10:05 | publications | `approved` → `approved`, puis `scheduled` → `scheduled` | Paul |
| 14 oct 10:05 | cibles | `scheduled` → `scheduled` (`new_scheduled_at` = 20 oct 09:00) | Paul |
| 20 oct 09:00 | cibles, puis publications | `sent` → `publishing` | vide |
| 20 oct 09:01 | cibles 101 et 103 | `published` → `published` | vide |
| 20 oct 09:02 | cible 102, puis publications | `published` → `published` | vide |

**Scénario B : correction.** Paul refuse : `correction_requested` → `needs_correction`, avec
`commentaires_users`. Marie corrige la description et la date ; rien n'est écrit tant qu'elle n'a
pas renvoyé. À l'envoi, au même instant : `submitted` → `pending_review`, plus un
`description_edited` et un `rescheduled` sur la cible concernée.

**Scénario C : modification après approbation.** Marie, qui n'a pas `review`, change la
description d'une cible programmée : `content_modified` → `pending_review` sur la publication,
`description_edited` (statut de la cible inchangé) et `unscheduled` → `awaiting_scheduling` sur
chaque cible programmée. Paul approuve de nouveau (`approved`, `scheduled`). Si Paul fait lui-même
la modification, seul `description_edited` est écrit.

**Scénario D : échec et relance.** Le 20 oct à 09:02, la cible LinkedIn : `failed` → `failed`
(erreur dans `error_message_json`) ; les autres sont publiées : publication `partially_published`.
Paul corrige la légende (`description_edited`, statut `failed`), puis relance : cible
`retried` → `scheduled` (`new_scheduled_at` = maintenant), publication `retried` → `publishing`.
Dès que la cible est publiée, la publication passe à `published`.

### Tables existantes

| Domaine | Tables | État |
|---|---|---|
| `users` | `users`, `permissions`, `user_permissions` | **en base** |
| `auth` | `refresh_tokens` | **en base** |
| `social_accounts` | `platforms`, `social_account_statuses`, `social_accounts`, `social_account_metrics` | **en base** |
| `publications` | publications, cibles, deux journaux, tables de référence | conçues |
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
concurrente (verrou optimiste sur `updated_at` ; pour valider une publication, qui n'a pas de
`updated_at`, la version est le plus grand `id` du journal de ses cibles).

GraphQL écarté : le front est en HTML/JS sans framework. Ajout possible plus tard via Strawberry,
en réutilisant les services.

## 6. Traitements de fond

| Tâche | Rôle |
|---|---|
| Planificateur de publications | prend les cibles `scheduled` échues, les passe en `publishing` (événement `sent`, ce qui évite le double envoi), appelle la couche sociale, puis recalcule le statut de la publication d'après ses cibles |
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
