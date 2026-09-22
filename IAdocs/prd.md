# PRD — IAGORA, agent IA de marketing et communication digitale

> **Autorité.** Ce document **résume** le cahier des charges IAGORA v2.1 (13 septembre 2026) et la
> fiche de stage, qui restent les documents de référence. En cas de contradiction, le cahier des
> charges l'emporte. Les codes `OB-xx`, `F-xx`, `E-xx`, `NF-xx` et `S-xx` renvoient à ses exigences.

## 1. Problème

DATUM Academy communique manuellement : connexion à chaque réseau l'un après l'autre, réécriture du
texte pour chaque plateforme, suivi sans outil commun. Trois conséquences :

1. **Présence irrégulière** — elle s'interrompt quand l'activité s'intensifie, c'est-à-dire au
   moment où il faudrait communiquer le plus.
2. **Temps disproportionné** — reformater un texte ou envoyer une invitation prend du temps pour
   peu de valeur.
3. **Aucune mesure consolidée** — rien ne dit quelles publications produisent un effet.

## 2. Utilisateurs

| Rôle | Rapport au système | Attente |
|---|---|---|
| Chargé de communication | utilisateur principal | produire, adapter, programmer ; suivre les événements ; passer du temps sur la décision éditoriale plutôt que sur la manipulation |
| Apprenants, entreprises, partenaires | destinataires | information régulière et exacte, sans sollicitation redondante |
| Prospects | destinataires | découvrent l'offre, peuvent écrire (traité par les extensions) |

Aucun rôle n'est figé dans le code : **un administrateur attribue les droits** — créer, valider,
publier, consulter, administrer (F-22). IAGORA est un **outil interne** à DATUM Academy : pas
d'inscription libre, pas de facturation, pas de multi-organisation.

## 3. Objectifs et critères de réussite

| Réf. | Objectif | Critère observable |
|---|---|---|
| OB-01 | Réduire le temps de publication | une annonce part sur tous les canaux en une seule opération |
| OB-02 | Rendre la présence régulière | un calendrier éditorial alimenté et tenu dans la durée |
| OB-03 | Fiabiliser l'information | les contenus s'appuient sur les documents de référence, pas sur la mémoire du rédacteur |
| OB-04 | Conserver la maîtrise éditoriale | **aucune publication ne part sans validation humaine** |
| OB-05 | Automatiser le suivi des événements | lien de visio, invitations, rappels et présence sans action manuelle |
| OB-06 | Rendre les communications traçables | qui a été contacté, quand, avec quel message, avec quel résultat |
| OB-07 | Mesurer les résultats | un tableau de bord unique |
| OB-08 | Rester extensible | ajouter un canal = écrire un connecteur, sans toucher à l'existant |

## 4. Périmètre

**Couvert :** génération et adaptation de contenus (texte, hashtags, visuels) ; programmation et
publication multi-réseaux ; événements et webinaires ; newsletters et liste de diffusion ; tableaux
de bord ; administration des utilisateurs, des droits et des comptes de plateformes.

**Extensions proposées par le stagiaire** (abandonnables sans conséquence) : messagerie unifiée avec
réponse assistée (E-01 à E-03), retouche conversationnelle (E-04), banque d'images (E-05, E-06),
base de connaissances interne (E-07, E-08).

**Exclu :** valorisation des activités sur le site web, comptes rendus de réunions, prospection
commerciale (lot « Agent IA Commercial 2.0 »), et **toute publication sans intervention humaine**.

**Ordre de réalisation retenu :** Meta d'abord (Facebook, Instagram), puis LinkedIn et TikTok.
Le prototype les affiche déjà, à titre de représentation.

## 5. Exigences par domaine

### 5.1 Contenu — F-01 à F-04
Un brief court produit une proposition **par plateforme**, avec hashtags et visuel. Tout est
modifiable avant soumission. Trois propositions sont présentées, chacune retouchable.

### 5.2 Publication — F-05 à F-09
Diffusion vers plusieurs réseaux en une opération, programmation avec calendrier, **validation
obligatoire** (F-07), historique de ce qui a été publié, où et quand (F-08), et extensibilité par
connecteur (F-09).

**Cycle de vie :** `draft → pending_review → approved → scheduled → publishing → published`,
avec `partially_published`, `failed` et `removed`. Chaque réseau visé a **son propre statut**.

### 5.3 Événements — F-10 à F-14
Création d'un webinaire avec lien de visioconférence, report dans l'agenda, confirmation à chaque
inscription, rappels automatiques, liste des inscrits et présence.
⚠️ **Point ouvert :** aujourd'hui l'inscription et l'email de confirmation sont gérés par le site
datumacademy.com. Voir `IAdocs/memory.md`.

### 5.4 Newsletters — F-15 à F-18
Liste de diffusion alimentée par les inscrits, envoi après validation, désinscription respectée,
historique des envois. Nécessite un service d'envoi dédié, non choisi.

### 5.5 Mesure — F-19 à F-21
Performance par canal et par période, participation aux événements, suivi par campagne.
La notion de **campagne** n'est pas encore modélisée.

### 5.6 Administration — F-22, F-23
Création des comptes et attribution des droits ; raccordement et reconnexion des comptes de
plateformes, avec l'état de chacun visible.

### 5.7 Messagerie — E-01 à E-03 (extension)
Messages regroupés, réponse proposée par l'IA et **jamais envoyée sans action humaine**, délai de
réponse de la plateforme affiché et envoi bloqué au-delà (24 h Messenger et Instagram, 48 h TikTok,
aucun envoi automatisé sur LinkedIn).

## 6. Règles métier transverses

1. **Rien ne part sans validation** (OB-04, F-07, NF-01).
2. **Modifier le contenu d'une publication approuvée la renvoie en validation.** Un simple report de
   date ne la renvoie pas.
3. **Une cible n'est jamais supprimée** : elle est annulée (`cancelled`) ou retirée (`removed`).
4. **Archivage** (`deleted_at`) réservé aux brouillons, idées et échecs : une publication en ligne
   reste visible et comptée dans les statistiques.
5. **Données personnelles** : anonymisation, pas archivage ; une durée de conservation par catégorie
   (S-03, S-04).
6. **Traçabilité** : auteur, valideur, date et résultat conservés pour toute diffusion (NF-02, S-07).
7. **Réversibilité** : une publication programmée peut être annulée avant exécution (NF-07).
8. **Langue** : contenus produits en français (NF-06).

## 7. Ce qui définit la première version

Une version est jugée utile quand une personne peut, sans quitter IAGORA :
rédiger avec l'aide de l'IA → faire valider → programmer sur Facebook et Instagram → constater la
publication → retrouver l'historique → répondre à un message reçu.

Le reste (newsletters, statistiques avancées, LinkedIn, TikTok, base de connaissances) vient ensuite.

## 8. Questions ouvertes

Elles sont suivies dans `IAdocs/tasks.md` et `IAdocs/memory.md` : périmètre webinaires face au site
Datum, droits et écran Utilisateurs (9a ou 9b), fournisseur LLM et génération d'images, service
d'envoi d'emails, indicateurs attendus, traitement des commentaires, durées de conservation.
