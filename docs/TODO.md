# Reste à faire — backend IAGORA

Chantiers identifiés pendant la conception, pas encore modélisés.
Chaque entrée renvoie à l'exigence du cahier des charges IAGORA v2.1 (CDC) qu'elle sert.

Légende : `[ ]` à faire · `[~]` en cours de discussion · `[x]` fait

---

## 1. Statistiques et tableau de bord — CDC F-19, F-20, F-21, OB-07

Les écrans affichent des statistiques partout (vues, commentaires, abonnés,
engagement, « meilleur créneau », pics d'inscriptions) sans qu'aucune table ne
les porte.

### 1.1 Statistiques des publications (F-19)
- [ ] Choisir les indicateurs de la première version : vues, portée, j'aime,
      commentaires, partages, enregistrements, vues vidéo.
- [ ] Vérifier dans la documentation Meta les indicateurs réellement disponibles
      par format (image, carrousel, reel, story) et par réseau.
- [ ] Vérifier les permissions nécessaires (API Insights de Meta) et leur
      passage par la validation de l'application (App Review).
- [ ] Table `publication_target_metrics` : une **photo** des indicateurs d'une
      cible publiée à un instant donné (`id_publication_targets`,
      `collected_at`, une colonne par indicateur, `raw JSONB`).
      On garde toutes les photos pour tracer l'évolution.
- [ ] Fréquence de collecte : par exemple toutes les heures pendant 48 h après
      publication, puis une fois par jour pendant 30 jours.
- [ ] Les stories disparaissent au bout de 24 h : leurs statistiques doivent être
      collectées **avant** expiration.

### 1.2 Statistiques des comptes
- [ ] Table `social_account_metrics` : abonnés, vues du profil, engagement,
      une ligne par compte et par jour (écran `reseaux.html`).
- [ ] Afficher la date de dernière collecte quand un compte est à reconnecter
      (« statistiques datant du 2 septembre »).

### 1.3 Participation aux événements (F-20)
- [ ] Nombre d'inscrits, taux de présence, **origine des inscriptions**.
- [ ] L'origine suppose que le site datumacademy.com enregistre les paramètres
      UTM : question posée à l'encadrement.

### 1.4 Campagnes (F-21)
- [ ] Notion de **campagne** absente du modèle : table `campaigns` à laquelle se
      rattachent publications, webinaires et newsletters, pour consulter leurs
      indicateurs ensemble.

### 1.5 Restitution
- [ ] Endpoints du tableau de bord : par canal, par période, par campagne.
- [ ] « Meilleur créneau » et « pic d'audience » : à calculer plus tard à partir
      des statistiques accumulées. Hors première version.
- [ ] Règle de comptage : une publication visant deux réseaux compte pour
      **une** publication et **deux** envois. Ne pas additionner les compteurs
      par réseau pour obtenir le nombre de publications.

---

## 2. Commentaires et mentions — CDC E-01

La messagerie du prototype affiche « Messages privés », « Commentaires » et
« Mentions ». Le modèle ne couvre que les messages privés.

- [ ] Table `comments` rattachée à la cible publiée (`id_publication_targets`) :
      `external_meta_id` (unique), commentaire parent pour les réponses,
      identifiant et nom de l'auteur, texte, statut, date de réception.
- [ ] Mentions Instagram : origine et rattachement à définir (une mention ne
      vise pas forcément une de nos publications).
- [ ] Vérifier dans la documentation Meta les champs de webhook à activer pour
      les commentaires et mentions (Page Facebook, compte Instagram).
- [ ] Vérifier les règles de réponse : réponse publique à un commentaire,
      réponse privée à un commentaire et son délai.
- [ ] Mettre à jour le workflow n8n `meta-messagerie-webhook.json`, qui ne
      traite aujourd'hui que les messages privés.
- [ ] Données personnelles : anonymisation des auteurs, durée de conservation
      (S-04).
- [ ] Alerte « pic de commentaires » (`notifications.html`) : dépend de ce
      chantier et du chantier 1.

---

## 3. Génération de visuels — CDC F-03, E-04, E-05

Des modèles Hugging Face ont été évalués dans l'état de l'art
(`flyers-generator` : SenseNova-U1, Ideogram), ainsi que l'API Unsplash pour la
banque d'images (E-05).

- [ ] Arrêter le modèle retenu et son mode d'hébergement : API Hugging Face
      (payante à l'usage) ou exécution locale (GPU nécessaire).
- [ ] Mesurer le temps de génération : le CDC NF-08 le laisse à fixer avec
      l'encadrement.
- [ ] Chiffrer le coût par visuel (contrainte « coûts variables » du CDC).
- [ ] Contenus internes et service tiers (NF-05) : vérifier si l'hébergement
      local est requis.
- [ ] Table `media` : ajouter `is_generated_by_ai`, `prompt`, `model`.
- [ ] Retouche conversationnelle (E-04) : chaque retouche crée une nouvelle
      version dérivée d'une autre → `publication_versions.id_publication_versions_parent`.
- [ ] Banque d'images (E-05) : conserver la mention d'attribution exigée.
- [ ] Les formats vidéo (reel, vidéo) ne se génèrent pas : l'IA produit le texte
      et éventuellement une image de couverture, la vidéo est fournie par
      l'utilisateur.

---

## 4. Autres chantiers identifiés

| Chantier | CDC | Remarque |
|---|---|---|
| Droits par utilisateur (créer, valider, publier, consulter, administrer) au lieu d'un rôle unique | F-22, S-02 | `users.role` à remplacer par `permissions` + `user_permissions`, avec historique des modifications de droits |
| Base de connaissances (documents de référence, recherche avant rédaction) | E-07, E-08, OB-03, NF-03 | extension `pgvector`, tables documents et extraits ; écran de gestion des documents absent du prototype |
| Consommation de l'IA (qui, quand, modèle, jetons, coût) | contrainte « coûts variables » | remplace l'affichage du coût dans la messagerie |
| Webinaires : création du lien Zoom, agenda, confirmation, rappels, présence | F-10 à F-14 | dépend des réponses de l'encadrement sur le site datumacademy.com |
| Newsletters et liste de diffusion, désinscription | F-15 à F-18, S-05 | nécessite un service d'envoi dédié (non choisi) |
| Modèles de messages d'événement validés une seule fois | CDC 6.2 | table de modèles avec valideur et date |
| Service d'envoi d'emails | F-12, F-13, F-16 | aussi utile pour « mot de passe oublié » et la création des comptes |
| Fenêtre de réponse des messageries | E-03 | `conversations.reply_window_expires_at` ; 24 h Messenger et Instagram, 48 h TikTok, aucun envoi automatisé sur LinkedIn |
| Réponses envoyées hors d'IAGORA | OB-06 | enregistrer les « échos » Meta au lieu de les ignorer dans le workflow n8n |
| Distinguer utilisateur, système et IA dans les historiques | NF-02 | colonne `actor_type` |
| Fuseau horaire par utilisateur | — | `users.timezone` ; stockage en UTC |
| Durées de conservation par catégorie de données | S-04 | à décider |
| Transmission des inscrits au lot Commercial 2.0 | CDC 5.4 | format et déclenchement à définir avec l'autre stagiaire |
