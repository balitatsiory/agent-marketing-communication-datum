# Agent marketing & communication — Datum

Automatisation de la publication et de la relation client sur les réseaux sociaux
de **Datum Academy**, et prototype de l'interface de pilotage.

> **Stage de 4 mois — Datum Academy.**
> <!-- À compléter : dates exactes, encadrant, intitulé de la convention. -->

## Les trois volets

### 1. Publication automatisée

Un workflow n8n publie sur Instagram et Facebook à partir d'une URL de média et
d'une légende, en gérant les trois formats : image, reel et story. Il enchaîne
la création du conteneur Meta, l'attente de traitement puis la publication.

→ `workflows/publication-reseaux-sociaux.json` — 45 nœuds, API Facebook Graph.

### 2. Messagerie unifiée

Un webhook n8n reçoit les messages Messenger et Instagram, répond au défi de
vérification de Meta, normalise les événements, écarte les échos et les
messages vides, route par plateforme et répond.

→ `workflows/meta-messagerie-webhook.json` — 10 nœuds.

### 3. Interface de pilotage

Prototype HTML/CSS de 10 écrans, construit à partir des wireframes : calendrier
éditorial, file de messages à valider, gestion des réseaux, historique des
activités, génération de publications assistée.

**C'est une maquette de validation**, pas une base de code applicative : elle
sert à faire valider les parcours et l'ergonomie avant tout développement.

→ `prototype/` — voir [prototype/README.md](prototype/README.md).

### 4. Backend

API **FastAPI** qui détient les données et les règles : authentification, droits,
comptes de réseaux sociaux et statistiques. PostgreSQL, migrations Alembic,
documentation Swagger générée. En cours de développement.

→ `backend/` — voir [backend/README.md](backend/README.md).

## Démarrer

Le projet a **deux piles Docker indépendantes** : n8n d'un côté, le backend et sa base
de l'autre. L'une peut tourner sans l'autre.

### n8n — publication et messagerie

```bash
cp .env.example .env      # puis renseigner l'URL du tunnel
```

```bash
docker compose up -d --build
```

n8n est disponible sur http://localhost:5678
Les workflows du dossier `workflows/` s'importent depuis l'interface.

Redémarrage, tunnel public, pièges connus : [docs/exploitation-n8n.md](docs/exploitation-n8n.md).

### Backend — API et base de données

```bash
cp backend/.env.example backend/.env
```

Générer ensuite les deux clés demandées dans le fichier, puis :

```bash
docker compose -f backend/docker-compose.yml up -d --build
```

```bash
docker compose -f backend/docker-compose.yml exec backend alembic upgrade head
```

Créer le premier administrateur — la création de comptes exige déjà le droit
« administrer », que personne ne possède au premier démarrage :

```bash
docker compose -f backend/docker-compose.yml exec backend python -m app.cli create-admin --email prenom.nom@datum-academy.fr --first-name Prenom --last-name Nom
```

| Service | Adresse |
|---|---|
| API | http://localhost:8000 |
| **Documentation Swagger** | http://localhost:8000/docs |
| PostgreSQL | `localhost:5433`, base `iagora`, utilisateur `iagora` |

Arrêter sans perdre les données : `docker compose -f backend/docker-compose.yml down`.

### Prototype d'interface

Aucun serveur nécessaire : ouvrir `prototype/index.html`.

## Structure

```
.
├── docker-compose.yml          stack n8n (reste à la racine : le nom du
├── Dockerfile                  volume n8n_data en dépend)
├── .env.example                modèle de configuration — .env est ignoré
│
├── backend/                    API FastAPI, base PostgreSQL, migrations
├── workflows/                  les workflows n8n, exportés en JSON
├── prototype/                  maquette d'interface HTML/CSS
├── IAdocs/                     contexte du projet : besoins, architecture,
│                               règles, design, tâches, dictionnaire de données
├── maquette-design-export/     export brut de l'outil de design, par version
└── docs/                       exploitation de la stack
```

## État d'avancement

- [x] Stack n8n dockerisée et documentée
- [x] Workflow de publication Instagram / Facebook (image, reel, story)
- [x] Webhook de messagerie Meta — jetons de page à renseigner
- [x] Prototype d'interface — 10 écrans sur 12
- [ ] Écran Utilisateurs — arbitrage entre deux maquettes
- [ ] Écran Paramètres — non maquetté
- [x] Backend : socle, authentification, droits, comptes de réseaux
- [ ] Backend : collecte des statistiques Meta
- [ ] Backend : publications
