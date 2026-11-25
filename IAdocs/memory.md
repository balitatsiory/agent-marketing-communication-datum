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
| 08/10 | Tables d'historique : nom préfixé **`history_`** (par exemple `history_publications`) | choix de l'utilisateur ; remplace `publication_history` et `publication_target_history` cités dans `architecture.md` |
| 25/11 | **Service d'envoi des courriels : SMTP IONOS** (`smtp.ionos.fr`), en SSL/TLS implicite sur le port 465, STARTTLS sur 587 en secours | tranche la question laissée ouverte dans `tasks.md` §6 ; la boîte existe déjà chez l'hébergeur du domaine, aucun service tiers à souscrire |
| 25/11 | Les identifiants d'envoi vivent **en base, chiffrés par Fernet** (`email_account_credentials`), et non dans `.env` | plusieurs comptes possibles, changement de mot de passe sans redéploiement, et la date de chaque remplacement est conservée |
| 25/11 | Un **seul compte d'envoi actif**, tenu par un index unique partiel et non par le service | une requête concurrente ne peut pas créer deux expéditeurs |
| 25/11 | **`aiosmtplib`** plutôt que `smtplib` | `smtplib` est bloquant : un serveur lent immobiliserait la boucle d'événements, donc toute l'API |
| 25/11 | **Une coquille unique** porte la bannière et la signature ; un modèle ne porte que son corps | changer le logo ne doit pas demander de rouvrir chaque modèle — et un modèle oublié enverrait l'ancien |
| 25/11 | Les cinq **modèles standards** vivent dans des fichiers `.html` et s'installent à la demande | du HTML dans un fichier se relit et se corrige ; noyé dans une migration, il ne se relit plus |
| 25/11 | Un envoi part **message par message**, jamais en copie cachée | le prénom de chacun, et les adresses des inscrits ne se montrent pas les unes aux autres |
| 25/11 | Les **cumuls d'un envoi sont déduits** du détail par destinataire | un total qui ne correspond pas au détail est invérifiable |
| 25/11 | La maquette de la boîte d'envois garde son URL en **`/newsletter/envois_prototype`** | demandée pour une démonstration ; la page branchée prend l'URL d'origine |
| 26/11 | Zoom par application **Server-to-Server OAuth** ; un compte = Account ID, Client ID, Client Secret (chiffré, `zoom_account_credentials`) et l'**adresse de l'hôte** | le droit de lister les utilisateurs n'est pas accordé ; ce type d'application n'a pas de « refresh token » : on redemande un jeton d'une heure |
| 26/11 | Trois droits : `manage_zoom_accounts`, `manage_webinars`, `create_zoom_meetings` | créer une réunion agit sur le compte Zoom de l'école et peut envoyer des courriels |
| 26/11 | Une réunion créée n'est **pas modifiable** depuis IAGORA (titre, date, durée, lien) | ni `meeting:update` ni `meeting:delete` ne sont accordés ; archiver une fiche ne touche pas Zoom |
| 26/11 | Publications liées par **adresse** (`webinar_publication_links`), sans clé vers `publications` | le module 08 n'est pas sur `main` (branche `feat/module-08-publications`) ; à remplacer quand il sera intégré |
| 26/11 | L'inscription peut se faire dans IAGORA (**formulaire public** `/inscription/:slug` : e-mail, prénom, nom), sur une page existante ou sur la page Zoom | revient sur l'hypothèse « inscriptions sur le site seulement » ; IAGORA doit être accessible publiquement pour que le formulaire serve |
| 26/11 | Newsletters : **seuls les inscrits ayant consenti** sont repris ; la case n'est jamais cochée d'avance | CDC S-05 ; s'inscrire sur la page Zoom ne vaut pas accord |
| 26/11 | Import du site : dates déduites enregistrées **« à confirmer »**, flyers rapatriés vers R2 sous `webinaires/{slug}/flyer-origine-{sha12}.{ext}` avec un slug normalisé | aucune date sûre dans les fichiers ; un « %C3%A9 » dans une clé rendrait l'image introuvable |
| 26/11 | Les maquettes 12a et 12b restent sous `/webinaires_prototype` | même règle que la boîte d'envois |
| 26/11 | La migration `0011` **réunit les deux lignées** parties de la `0008` (`0010` et `0010_ai_prompts`) | `main` avait deux têtes : `alembic upgrade head` échouait ; un test refuse désormais d'en avoir deux |
| 26/11 | Une adresse effacée est reconnue par une **empreinte à clé** (`erased_email_fingerprint`), jamais conservée | la reprise des inscrits depuis Zoom la recréait |
| 26/11 | Une fiche réservée pendant un appel à Zoom l'est en **`FOR NO KEY UPDATE`** | `FOR UPDATE` bloquait toute nouvelle inscription pendant l'appel |
| 26/11 | Avant de créer une réunion, IAGORA **reprend une réunion identique** (titre et heure) rattachée à aucune fiche | une réponse de Zoom perdue puis un nouvel essai créaient un doublon |
| 26/11 | Le formulaire public répond **toujours le même message**, sans promettre de courriel | Zoom peut refuser l'inscription après coup |
| 26/11 | Un webinaire **déjà validé ne passe plus** d'un lien fourni à « Zoom » | la réunion ne se crée qu'à la validation d'un brouillon |
| 26/11 | Export CSV des inscrits réservé à **`manage_webinars`**, **sans** les lignes effacées ni le lien Zoom personnel ; les valeurs commençant comme une formule sont neutralisées | le fichier sort d'IAGORA : le lien donne accès à la réunion, et un tableur exécuterait un prénom saisi dans le formulaire public |

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

**Noms des bases** — la décision du 25/09 note `stage_iagora` et `stage_iagora_test`, mais `backend/.env` utilise **`iagora`** et **`iagora_test`** (PostgreSQL sur le port **5433**). C'est le fichier `.env` qui fait foi : vérifié le 25/11/2026.

**Zoom (26/11/2026)** — le code est testé contre un **Zoom simulé** (`backend/tests/faux_zoom.py`) : aucun
appel au vrai Zoom n'a encore été fait. À confirmer avec le compte réel : la liste des réunions
(`scheduled`, `previous_meetings`) et l'ajout d'inscrit, que Zoom réserve aux hôtes sous licence payante.

**Migrations sur une base vide (26/11/2026)** — `alembic upgrade head` échoue à la révision **0004**
(`cannot insert multiple commands into a prepared statement`) : une base neuve ne se monte pas.

**Formulaire public** — aucune limite de débit : à ajouter **avant** de l'exposer sur Internet, chaque
inscription pouvant déclencher un appel à Zoom et un courriel.

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
