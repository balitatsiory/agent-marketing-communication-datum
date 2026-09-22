# Direction UI/UX — IAGORA

Le prototype cliquable est dans `prototype/`. Il est issu des wireframes v2.1
(`maquette-design-export/v2.1/`). Aucun framework, aucune étape de build : il s'ouvre en `file://`.

## 1. Identité visuelle

| | |
|---|---|
| Palette | **Cuivre & Papier** — accent `#a8542c` sur fond papier `#faf7f3` |
| Titrage | **Instrument Serif**, au-dessus de 20 px uniquement |
| Texte | **Karla** |
| Chiffres, libellés, horodatages | **IBM Plex Mono** |
| Icônes | monochromes, tracé SVG héritant de `currentColor`, logos de réseaux compris |

Toutes les couleurs et mesures sont des **variables CSS** déclarées en tête de `css/styles.css` :
changer l'accent partout revient à changer `--accent`. Les polices sont auto-hébergées dans
`fonts/` — aucun appel réseau, le prototype fonctionne hors ligne.

## 2. Structure des écrans

- **Barre latérale** (variante 5b) : catégories repliables, repli en rail de 68 px, état mémorisé
  dans le `localStorage`. Définie une seule fois dans `js/app.js` (tableau `NAV`) ; chaque page
  déclare seulement sa rubrique active via `<body data-page="…">`.
- **Barre supérieure** : fil d'Ariane à gauche, actions à droite.
- **En-tête de page** : titre, sous-titre chiffré, filtres.
- **Colonne de filtres** à gauche pour les listes longues ; **panneau de détail** à droite pour le
  calendrier ; **fenêtre modale** pour le détail d'un objet (publication, webinaire, retouche).

## 3. Composants et conventions

| Composant | Usage |
|---|---|
| `chip` | filtre rapide, sélection exclusive dans un groupe |
| `fopt` (case à cocher) | filtre cumulable |
| `toggle-row` / `plat-row` | activation d'un réseau ou d'une option |
| `kcard` | carte du Kanban ; cliquable, mène à l'objet |
| `pcard` | vignette de publication |
| `status` | pastille d'état : `status-live`, `status-plan`, `status-draft`, `status-fail` |
| `ev` | pastille du calendrier ; `ev-web` (événement ou e-mail), `ev-wait`, `ev-block`, `ev-sel`, `ev-ghost` |
| `modal-back` / `modal` | fenêtre, fermée par la croix, Échap ou un clic à côté |

Règles : une couleur d'accent unique, pas de dégradé, bordures fines, coins arrondis discrets,
`font-variant-numeric: tabular-nums` sur les chiffres.

## 4. Règles d'écriture

- **Français**, phrases courtes, pas de jargon technique dans l'interface.
- Les libellés d'état viennent de la base (`label` des tables de référence), jamais écrits en dur.
- Les dates s'affichent dans le **fuseau de l'utilisateur**, avec le fuseau rappelé quand on
  programme quelque chose.
- Un chiffre **absent** s'affiche « — », jamais « 0 » : la mesure indisponible et la mesure nulle
  sont deux choses différentes.
- Les actions irréversibles sont explicites et confirmées (retirer d'un réseau, annuler un
  événement).

## 5. Principes de conception retenus

1. **La validation est visible.** Le bouton principal de la création est « **Envoyer à valider** »,
   pas « Publier ». Le Kanban montre le cycle complet : Brouillons → À valider → Approuvées →
   Programmés → Publiés → Échecs.
2. **Un échec n'est jamais silencieux.** Il a sa colonne, sa notification, sa ligne d'historique et
   son action de réparation (« Reconnecter »).
3. **L'IA propose, l'humain dispose.** Chaque réponse ou texte généré est présenté comme une
   proposition, avec la mention « rien n'est envoyé sans cette action ».
4. **Les contraintes des plateformes sont montrées avant l'erreur** : format « Vidéo » limité à
   Facebook, longueur de légende, délai de réponse de 24 h dépassé.
5. **Une publication ≠ un envoi.** Une publication visant deux réseaux compte pour une publication
   et deux envois ; les compteurs le disent.
6. **Rien n'est affiché sans source.** Une statistique qui n'est pas encore collectable ne doit pas
   apparaître comme acquise.

## 6. Écrans

| Fichier | Écran | Maquette |
|---|---|---|
| `index.html` | Connexion | 2a |
| `creer-publication.html` | Créer une publication | 3a |
| `generer-publication.html` | Générer + retouche | 4a, 4a1 |
| `publications.html` | Publications + fenêtre de détail | 13b |
| `calendrier.html` | Calendrier et Kanban | 7a, 8b |
| `messages.html` | Messagerie unifiée | 10a |
| `webinaires.html` | Webinaires + détail | 12a, 12b |
| `reseaux.html` | Réseaux et plateformes | 6b |
| `historique.html` | Historique des activités | 7b |
| `notifications.html` | Notifications | 11a |
| `tableau-de-bord-a/b/c.html` | Trois variantes à arbitrer | — |
| `utilisateurs.html` | **en attente** : 9a ou 9b | — |
| `parametres.html` | **non maquetté** | — |

## 7. Décisions appliquées au prototype

Outil interne (ni inscription libre, ni facturation) · « Publier » → « Envoyer à valider » · format
« Vidéo » ajouté, réservé à Facebook · fuseau de l'utilisateur affiché · colonne « Idées » supprimée,
colonnes « Approuvées » et « Échecs » ajoutées · filtre Statut complet avec « Afficher les
archivées » · distinction publications / envois · fenêtre de détail d'une publication avec son
historique et un lien par réseau · ville des inscrits retirée et vrai lien d'inscription ·
score de confiance et coût de l'IA retirés · conversation hors délai : « Répondre dans Instagram » ·
calendrier centré sur les webinaires, chaque pastille menant à sa publication ou à son webinaire.

## 8. Points ouverts

- **Écran Utilisateurs** : maquette 9a (tableau, rôles et réseaux) ou 9b (cartes, invitations).
- **Paramètres** : à dessiner (organisation, signature, fuseau, quotas, charte de marque).
- **Tableau de bord** : variante A, B ou C.
- **Point d'entrée pour connecter un premier compte** : retiré de l'écran Réseaux, à replacer.
- **Formats dans Générer** : garder Reels et Vidéo (texte seulement) ou les retirer.
- **Fil d'Ariane** de Notifications et **place de « Gestion des réseaux »** dans le menu.
