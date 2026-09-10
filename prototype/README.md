# IAGORA — prototype HTML / CSS

Prototype cliquable construit à partir des wireframes `v2.1/Login Wireframes standalone.html`
(Claude Design). HTML + CSS, sans framework et sans étape de build.

## Lancer

Double-cliquez `index.html` : tout fonctionne en `file://`, y compris les polices.
Pour servir en local à la place :

```bash
python -m http.server 8123 --directory prototype
```

## Direction visuelle

| | |
|---|---|
| Palette | **Cuivre & Papier** — accent `#a8542c` sur fond papier `#faf7f3` |
| Titrage | **Instrument Serif** — au-dessus de 20 px uniquement |
| Texte | **Karla** |
| Chiffres, libellés | **IBM Plex Mono** |
| Icônes | monochromes, tracé SVG héritant de `currentColor` — logos de réseaux compris |

Les polices sont auto-hébergées dans `fonts/` (sous-ensembles latin + latin-ext).
Aucun appel réseau : le prototype fonctionne hors ligne.

Toutes les couleurs et mesures sont des variables CSS déclarées en tête de
`css/styles.css`. Changer l'accent partout = changer `--accent`.

## Pages

| Fichier | Écran | Maquette |
|---|---|---|
| `index.html` | Connexion | 2a |
| `creer-publication.html` | Créer une publication | 3a |
| `generer-publication.html` | Générer une publication + pop-up de retouche | 4a + 4a1 |
| `publications.html` | Publications | 13b |
| `calendrier.html` | Calendrier éditorial + vue Kanban | 7a + 8b |
| `messages.html` | Messagerie unifiée | 10a |
| `webinaires.html` | Webinaires + pop-up détail | 12a + 12b |
| `reseaux.html` | Gestion des réseaux | 6b |
| `historique.html` | Historique des activités | 7b |
| `notifications.html` | Notifications | 11a |
| `utilisateurs.html` | *en attente* — arbitrage 9a / 9b | — |
| `parametres.html` | *non maquetté* | — |

Chaque page porte en bas à droite une pastille rappelant la maquette d'origine.
Elle se retire en supprimant `<div class="proto-flag">…</div>`.

## Structure

```
prototype/
├── index.html            connexion
├── *.html                un fichier par écran
├── css/styles.css        variables + composants partagés
├── js/app.js             sidebar, icônes, pop-ups
├── fonts/                polices auto-hébergées + fonts.css
└── README.md
```

### La sidebar

Elle n'est écrite qu'une fois, dans `js/app.js` (tableau `NAV`). Chaque page
contient seulement `<nav class="sidebar"></nav>` et déclare la rubrique active
via `<body data-page="publications">`. Ajouter une entrée = ajouter une ligne
dans `NAV`.

C'est la variante **5b** : catégories repliables, pas d'en-têtes de section.
Elle se replie en rail de 68 px ; l'état du rail et des catégories est mémorisé
dans le `localStorage` du navigateur.

« Tableau de bord » et « Inscriptions » ont été retirés de la navigation :
aucune maquette ne leur correspond dans l'export v2.1.

### Icônes

Déclarées dans `ICONS` (navigation) et `NETS` (réseaux) dans `js/app.js`,
posées dans le HTML par `<i data-ico="bell"></i>` ou `<i data-net="linkedin"></i>`
et remplacées par le SVG au chargement.

## Écarts assumés par rapport aux wireframes

- Les wireframes utilisaient **Kalam**, une police manuscrite qui sert à signaler
  « ce n'est pas fini ». Remplacée par la typographie retenue.
- Les maquettes mélangeaient deux jeux de données (« Ma marque » / « Studio social »
  d'un côté, Datum Academy de l'autre). Tout a été harmonisé sur **Datum Academy**.
- Les icônes étaient des cercles vides (placeholders) : remplacées par des icônes
  dessinées.
