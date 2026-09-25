# Contexte du projet — à lire en premier

Ce fichier existe pour qu'une personne — ou un assistant — reprenne le projet sans relire tout
l'historique. Il consigne **ce qui a été décidé, quand et pourquoi**, ainsi que les faits vérifiés.

## 1. Le projet en cinq lignes

**IAGORA** est l'agent IA de marketing et communication digitale de **DATUM Academy**, développé
pendant le stage M2 de **Balita** (ITUniversity / BIHAR). Encadrement : **Arame Niang** et
**Nazim Kazar**. Un second lot, « Agent IA Commercial 2.0 — Prospection et Recrutement », est mené
en parallèle par **Anjara** ; les inscrits aux événements d'IAGORA lui sont transmis (CDC §5.4).

## 2. Documents de référence

| Document | Rôle |
|---|---|
| Fiche de stage | fait autorité sur le périmètre et les huit livrables |
| `Cahier_des_charges_IAGORA_v2-1.docx` (13/09/2026) | livrable n° 1, codes OB/F/E/NF/S |
| `prototype/` | prototype cliquable, issu des wireframes v2.1 |
| `IAdocs/` | ce dossier : PRD, architecture, règles, design, tâches, contexte |
| `IAdocs/base-de-donnees.md` | dictionnaire de données, **généré depuis la base** après chaque migration |
| `backend/README.md` | démarrage, commandes du quotidien, repères |
| `CONTRIBUTING.md`, `docs/TODO.md` | conventions de code ; chantiers non modélisés |

## 3. État au 25 septembre 2026

Le **backend est démarré et fonctionne** : socle, authentification, droits, et les tables des
réseaux sociaux. Il tourne **en local** (PostgreSQL du poste + `uvicorn`), pas en conteneur.

| Ce qui marche | Détail |
|---|---|
| API | FastAPI sur `http://localhost:8000`, documentation Swagger sur `/docs` |
| Base | PostgreSQL local, base **`stage_iagora`**, 9 tables, 5 migrations appliquées |
| Authentification | connexion, renouvellement avec rotation, déconnexion, `/auth/me` |
| Droits | 5 droits (F-22) attribuables un par un, vérifiés à chaque endpoint |
| Réseaux | tables `platforms`, `social_account_statuses`, `social_accounts`, `social_account_metrics` |
| Qualité | 32 tests, `ruff` et `mypy --strict` sans erreur |

**Reste à faire immédiatement :** la collecte des statistiques Meta
(`integrations/social/meta_gateway.py`), qui reprendra les six appels du workflow n8n
`workflows/statistiques-comptes-meta.json`.

Le prototype d'interface a été relu et corrigé. Le module `publications` n'est pas commencé.

## 4. Décisions actées

| Date | Décision | Raison |
|---|---|---|
| 17/09 | **FastAPI**, rangement **par domaine** | typage et documentation générée ; 12 domaines à garder lisibles |
| 17/09 | **API REST**, GraphQL écarté | front en HTML/JS sans framework |
| 17/09 | **n8n en test, Graph API en production** | prototypage rapide, puis moins de dépendances |
| 17/09 | **PostgreSQL**, NoSQL écarté | entités très reliées ; JSONB pour le souple |
| 17/09 | Suppression = **archivage** | l'historique référence les objets |
| 17/09 | **Meta d'abord** (Facebook, Instagram) | LinkedIn et TikTok restent au périmètre, plus tard |
| 18/09 | Clés **`id_<table>` en BIGINT identity** ; FK `id_<table_cible>[_<rôle>]` | choix de l'équipe |
| 18/09 | Statut **`idea` supprimé** ; ajout de `publishing` et `removed` | le cycle commence à `draft` ; éviter le double envoi ; garder visible un post retiré |
| 18/09 | **Tables de référence** `code` + `label` | ajouter une valeur sans migration, libellés affichables, règles portées par la donnée |
| 18/09 | **Historique en table, en ajout seul** ; JSON écarté | requêtes transverses, intégrité, immutabilité |
| 18/09 | Dates passées **déduites** de l'historique | éviter deux sources pour la même information |
| 18/09 | **Archivage selon le statut** ; une publication en ligne reste visible | sinon les statistiques deviennent fausses |
| 18/09 | IAGORA est un **outil interne** | ni multi-organisation, ni facturation, ni inscription libre |
| 21/09 | `null` ≠ `0` pour les statistiques | Meta renvoie un ensemble vide quand la donnée n'existe pas |
| 24/09 | **Python 3.12** dans l'image, **pip + requirements**, SQLAlchemy **asynchrone** | outillage classique, facile à expliquer en soutenance |
| 24/09 | pytest en `--import-mode=importlib` + `pythonpath = ["."]` | deux `test_router.py` dans des dossiers différents feraient échouer la collecte |
| 24/09 | Nom de contrainte **raccourci à la main au-delà de 63 caractères** | PostgreSQL tronque sans prévenir ; `tests/test_naming.py` le vérifie |
| 25/09 | **Commentaires SQL sur chaque table et colonne**, déclarés dans les modèles | la base se documente elle-même ; `IAdocs/base-de-donnees.md` en est généré |
| 25/09 | **Exécution en local**, Docker plus tard | l'utilisateur veut garder la main : journaux dans son terminal, rechargement immédiat, débogage depuis l'éditeur |
| 25/09 | Bases **`stage_iagora`** et **`stage_iagora_test`** | noms choisis par l'utilisateur ; tirets bas, donc pas de guillemets en SQL |
| 25/09 | L'API **refuse de démarrer** si une clé est restée à sa valeur d'exemple | une clé Fernet invalide ne se verrait qu'au premier chiffrement, des semaines plus tard |
| 25/09 | La racine `/` **redirige vers `/docs`** | un 404 sur `http://localhost:8000` laissait croire que l'API n'avait pas démarré |

## 5. Faits vérifiés

**Site datumacademy.com** — l'inscription aux webinaires s'y fait (application Laravel), avec deux
formulaires séparés, en ligne et en présentiel. Champs : prénom, nom, email, activité
professionnelle, entreprise **ou** université, questions. **Ni ville, ni source (UTM), ni case de
consentement.** Le site envoie lui-même l'email de confirmation contenant le lien Zoom.
→ Contradiction avec F-10 à F-13, qui confient cela à IAGORA. **Question ouverte.**

**API Meta (vérifié le 21/09, version v26.0)**
- Instagram : `impressions` est **obsolète** pour les contenus créés après le 2 juillet 2024 ;
  utiliser **`views`**. Indicateurs disponibles : `views`, `reach`, `likes`, `comments`, `saved`,
  `shares`, `total_interactions`, plus les indicateurs propres aux reels et aux stories.
- Facebook : `post_impressions` et ses variantes `_unique` sont **obsolètes depuis la v25**.
- Statistiques de Page : exigent **`read_insights` et `pages_read_engagement`**, et la tâche
  **ANALYZE** sur la Page.
- Instagram : certains indicateurs n'existent pas en dessous de **100 abonnés**.
- Données jusqu'à **48 h** de retard, conservées **2 ans**. Stories : statistiques **24 h** seulement.
- Fenêtres de réponse : **24 h** Messenger et Instagram, **48 h** TikTok, **aucun** envoi automatisé
  sur LinkedIn.
- Erreurs utiles : `190` jeton expiré · `4`, `17`, `613` quota · `10` audience insuffisante.

**Premier test de collecte (21/09)** — la chaîne n8n fonctionne ; la page de test n'a que 1 et 3
abonnés, donc Meta ne renvoie ni `page_views_total`, ni `page_impressions`, ni `reach`. À refaire
sur un compte ayant de l'audience, après avoir vérifié `read_insights`.

## 6. Environnement de travail

- Poste **Windows**, dépôt `D:\Datum\stage-project\agent-marketing-communication-datum`.
- **n8n** tourne dans Docker (`docker compose up -d`), accessible sur `http://localhost:5678` ;
  les webhooks publics passent par un tunnel cloudflared dont l'URL change à chaque démarrage.
- **`gh` n'est pas installé** : les pull requests sont ouvertes à la main depuis GitHub.
- Dépôt GitHub : `balitatsiory/agent-marketing-communication-datum`.

### Le backend, en local

| Élément | Valeur |
|---|---|
| PostgreSQL | service Windows `postgresql-x64-16`, port **5432**, à démarrer à la main |
| Base de travail | **`stage_iagora`**, propriétaire `iagora` |
| Base de test | **`stage_iagora_test`**, vidée par `pytest` |
| Environnement Python | `backend/.venv`, **Python 3.13** (l'image Docker vise 3.12) |
| Configuration | `backend/.env`, ignoré par git ; modèle dans `.env.example` |
| Démarrer | depuis `backend/` : `.\.venv\Scripts\activate` puis `uvicorn app.main:app --reload` |
| Premier administrateur | `python -m app.cli create-admin --email … --first-name … --last-name …` |
| Migrations | `alembic upgrade head` · nouvelle : `alembic revision --autogenerate -m "…"` |
| Dictionnaire de données | `python -m app.cli db-doc > ..\IAdocs\base-de-donnees.md` |

**Docker reste en place** (`backend/Dockerfile`, `backend/docker-compose.yml`) pour la
démonstration et la production. Deux pièges déjà rencontrés : `docker compose restart` ne relit
pas `.env` (utiliser `up -d --force-recreate`), et `up -d` masque les journaux (les suivre avec
`logs -f backend`).

## 7. Façon de travailler retenue

1. **Pas de code applicatif sans feu vert explicite.**
2. On avance **point par point**, chaque décision est validée avant la suivante.
3. Les modifications se font dans le **dossier principal** (pour être testées tout de suite), sans
   écraser les fichiers en cours de modification.
4. On ne commite pas sur `main` : une PR passe par une branche dédiée.
5. Toute décision nouvelle est ajoutée ici, avec sa date et sa raison.

## 8. Ce qui reste bloqué

Voir `IAdocs/tasks.md` §6. Les plus structurantes : le partage des rôles avec le site Datum pour les
webinaires, les droits des utilisateurs, le fournisseur LLM et la génération d'images, et le choix
des indicateurs du tableau de bord.
