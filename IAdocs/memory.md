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
| `CONTRIBUTING.md`, `docs/TODO.md` | conventions de code ; chantiers non modélisés |

## 3. État au 22 septembre 2026

Conception du backend **terminée pour les publications** ; **aucun code applicatif écrit**.
Le prototype d'interface a été relu et corrigé. Un premier test de lecture des statistiques Meta a
été fait via n8n. Le feu vert pour coder n'a pas encore été donné.

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
- **PostgreSQL 16** est installé localement, service arrêté par défaut.
- **`gh` n'est pas installé** : les pull requests sont ouvertes à la main depuis GitHub.
- Dépôt GitHub : `balitatsiory/agent-marketing-communication-datum`.

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
