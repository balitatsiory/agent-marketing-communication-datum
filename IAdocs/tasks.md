# Tâches et avancement — IAGORA

Mis à jour le **22 septembre 2026**.
Le **détail des chantiers non modélisés** vit dans [`docs/TODO.md`](../docs/TODO.md) ; ce fichier-ci
donne l'état d'avancement et ce qui vient ensuite.

Légende : `[x]` fait · `[~]` en cours · `[ ]` à faire · `[?]` bloqué par une décision

## 1. Livrables du stage

| N° | Livrable | État |
|---|---|---|
| 1 | Étude des besoins et cahier des charges | `[x]` v2.1 soumise à validation |
| 2 | Architecture technique de l'agent | `[~]` conception faite, document à rédiger |
| 3 | Développement du prototype fonctionnel | `[~]` prototype d'interface fait, backend non démarré |
| 4 | Intégration des réseaux et outils | `[~]` publication via n8n, lecture des statistiques en test |
| 5 | Tableau de bord de supervision | `[?]` trois variantes proposées, en attente d'arbitrage |
| 6 | Documentation technique | `[~]` `CONTRIBUTING.md`, `IAdocs/` |
| 7 | Guide utilisateur | `[ ]` |
| 8 | Rapport final et soutenance | `[ ]` |

## 2. Conception du backend — fait

- [x] Framework, rangement par domaine, API REST (GraphQL écarté)
- [x] PostgreSQL retenu, NoSQL écarté ; JSONB pour le souple
- [x] Conventions de nommage et de code → `CONTRIBUTING.md`, `IAdocs/rules.md`
- [x] Stratégie d'intégration : n8n en test, Graph API en production
- [x] Modèle de données des publications : tables de référence, cibles par réseau, versions,
      médias, historiques en ajout seul
- [x] Modèle des utilisateurs, sessions, messagerie, historique, notifications
- [x] Règles métier : validation, report, annulation, archivage selon le statut, verrou optimiste

## 3. Prototype — corrections appliquées

- [x] Outil interne : « Créer un compte » et « facturation » retirés
- [x] « Publier » → « Envoyer à valider »
- [x] Format « Vidéo » ajouté ; fuseau de l'utilisateur affiché
- [x] Colonne « Idées » supprimée ; colonnes « Approuvées » et « Échecs » ajoutées
- [x] Compteur « en attente de validation » aligné sur le Kanban
- [x] Filtre Statut complet + « Afficher les archivées » ; publications distinguées des envois
- [x] Fenêtre de détail d'une publication : historique et lien par réseau
- [x] Messagerie : mention du webinaire retirée, score de confiance et coût retirés,
      conversation hors délai avec « Répondre dans Instagram »
- [x] Relances : plus de nouvelle tentative annoncée pour un jeton expiré
- [x] Webinaires : ville des inscrits retirée, vrai lien d'inscription, QR code et
      « Promouvoir ce webinaire » retirés
- [x] Réseaux : boutons de connexion retirés
- [x] Calendrier recentré sur les webinaires, pastilles cliquables

## 4. Intégration Meta — en cours

- [x] Workflow n8n de lecture des statistiques de compte (`workflows/statistiques-comptes-meta.json`)
- [x] Premier essai : la chaîne fonctionne ; la page de test n'a pas assez d'audience pour que Meta
      renvoie des valeurs
- [ ] Vérifier la présence de l'autorisation `read_insights` sur le jeton (`debug_token`)
- [ ] Refaire la mesure sur un compte ayant de l'audience, ou en lecture seule sur la vraie page
- [ ] Figer les noms de champs retenus, puis la table `social_account_metrics`
- [ ] Même travail pour les statistiques **par publication** (`publications.html`)

## 5. Le code — état au 25 septembre 2026

Le backend tourne **en local** (PostgreSQL du poste, `uvicorn` dans le terminal).
Démarrage et commandes : `backend/README.md`. Tables et colonnes : `IAdocs/base-de-donnees.md`.

- [x] **Outillage** : `pyproject.toml` (ruff, mypy strict, pytest), `.env.example`, `Dockerfile`
- [x] **Socle** : `config` avec contrôle au démarrage, `database` avec la convention de nommage,
      `errors` au format unique, `/health`, racine qui redirige vers la documentation
- [x] **Sécurité** : bcrypt, JWT, chiffrement Fernet des jetons de plateformes
- [x] **`auth`** : connexion, renouvellement **avec rotation**, déconnexion, `/auth/me`
- [x] **`users`** : comptes, droits F-22 attribuables un par un, archivage, garde-fous
      (ni son propre compte, ni le dernier administrateur)
- [x] **`social_accounts`** : tables `platforms`, `social_account_statuses`, `social_accounts`,
      `social_account_metrics` — modèles et migrations, sans service ni endpoints
- [x] **Migrations** : 5 appliquées, valeurs initiales comprises (droits, réseaux, statuts)
- [x] **Commentaires SQL** sur les 8 tables et 73 colonnes, et leur document généré
- [x] **Swagger** : bouton Authorize, sections, exemples, erreurs documentées
- [x] **Tests** : 32, dont les conventions de nommage en base
- [ ] **Collecte des statistiques Meta** — étape en cours
- [ ] **`publications`** : tables de référence, versions, cibles, historiques
- [ ] `media`, `messages`, `webinars`, `calendar`, `activity`, `notifications`, `webhooks`

### Outillage encore absent
- [ ] Tests **avec base de données** (fixtures, session annulée après chaque test)
- [ ] Enveloppe de pagination `{items, total, page, page_size}`
- [ ] Intégration continue GitHub Actions (`ruff`, `mypy`, `pytest`)

## 6. Décisions attendues

**De l'encadrement :**
- [?] Webinaires : qui crée l'événement et envoie les confirmations, IAGORA ou le site ? Un webhook
      du site à chaque inscription est-il possible ? Le site peut-il enregistrer les UTM ?
- [?] Droits : quels profils ? Un valideur peut-il valider sa propre publication ? Écran 9a ou 9b ?
- [?] Tableau de bord : variante A, B ou C ? Quels indicateurs en première version ?
- [?] LLM : quel fournisseur ? Génération d'images dès la V1 ? Quel budget ? Hébergement local exigé ?
- [?] Newsletters et emails : quel service d'envoi ?
- [?] Messagerie : traite-t-on les commentaires, ou seulement les messages privés ?
- [?] Conservation : historique 12 mois, notifications 30 jours ?

**De l'équipe projet :**
- [?] Actions à mettre dans la fenêtre de détail d'une publication
- [?] Formats Reels et Vidéo dans « Générer » : conservés en texte seulement ?
- [?] Où replacer le point d'entrée « connecter un compte »
- [?] Création des comptes : invitation par email ou mot de passe provisoire
- [?] Fil d'Ariane de Notifications ; place de « Gestion des réseaux » dans le menu

## 7. Corrections en attente sur le prototype

- [ ] `webinaires.html` : « OCT. 02 jeudi » → vendredi
- [ ] `notifications.html` : nom de l'échec TikTok, à aligner sur le calendrier
- [ ] `webinaires.html` : « LinkedIn Live + Zoom » → Zoom seul, si confirmé
- [ ] `messages.html` : retirer « Dakar » de l'en-tête de conversation, si confirmé
