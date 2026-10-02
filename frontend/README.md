# IAGORA — front-end Angular

Interface de pilotage de la publication et de la relation client sur les réseaux
sociaux de **Datum Academy**. Angular 20, composants autonomes, signaux.

> **Données statiques.** Aucun appel réseau : tout vient de `src/app/core/data/`.
> Le backend FastAPI (`../backend/`) n'est pas encore branché.

## Lancer

```bash
npm install --prefix frontend
npm start --prefix frontend
```

`http://localhost:4200` — redirige vers `/publications`.

| Commande | Effet |
|---|---|
| `npm start` | serveur de développement, rechargement à chaud |
| `npm run build` | construction de production dans `dist/` |
| `npm test` | tests unitaires (Karma) |

Angular 20 demande Node `^20.19`, `^22.12` ou `>= 24`. La version 21 du CLI exige
Node ≥ 22.22.3 : c'est pourquoi le projet est sur la 20.

## Direction visuelle

Charte reprise du site public **[Datum Academy](https://www.datumacademy.com/fr/about)**,
typographie reprise du prototype déjà validé (`../prototype/`).

| | |
|---|---|
| Accent | `#167FA4` — le `--bs-primary` du site Datum |
| Aplats profonds | `#0A4D64`, `#073C4E` |
| Lavande | `#D3C5FE` — décorative seulement, voir plus bas |
| Encre | `#212529` |
| Titrage | **Instrument Serif**, au-dessus de 20 px uniquement |
| Texte | **Karla** |
| Chiffres, libellés | **IBM Plex Mono** |
| Logo | monogramme Datum, repris au tracé près, recoloré par `currentColor` |

Les polices sont auto-hébergées dans `public/fonts/` : aucun appel réseau.

**Toutes** les couleurs sont des jetons déclarés dans `src/styles/_tokens.scss`.
Aucune valeur hexadécimale ne doit apparaître ailleurs : changer l'accent partout
revient à changer `--accent`.

### Trois écarts assumés par rapport à la charte Datum

1. **La lavande `#D3C5FE` ne sert pas d'état.** Le site public l'emploie comme
   `--bs-warning`, mais elle ne tient que 1,3:1 sur du blanc : illisible pour du
   texte. Elle reste disponible en `--lavender` pour du décor ; l'état
   « programmée » passe par un ambre lisible.
2. **Le vert de succès est assombri** de `#198754` à `#157347`. L'original ne
   tenait que 3,9:1 sur son propre fond clair, en capitales de 10 px.
3. **Le rouge d'erreur est assombri** de `#dc3545` à `#c42532`, pour la même raison.

Contrastes mesurés dans le navigateur : texte courant ≥ 14:1, `muted` ≥ 4,9:1,
texte sur accent 4,6:1, invites de champ 4,8:1 — tous au-dessus du seuil AA.

**Point ouvert :** `--border-2` (`#b3c6cd`, le `--bs-gray-600` de Datum) ne tient
que 1,8:1 sur blanc. C'est la bordure des champs et des boutons, pour lesquels la
norme AA demande 3:1. Le corriger impose de descendre vers `#7d98a3`, nettement
plus marqué — arbitrage visuel laissé ouvert.

## Écrans

| Route | Écran | Maquette | État |
|---|---|---|---|
| `/tableau-de-bord` | Tableau de bord | hors maquette | construit |
| `/connexion` | Connexion | 2a | construit |
| `/publications` | Publications — grille, filtres, détail | 13b | construit |
| `/publications/nouvelle` | Créer une publication | 3a | construit |
| `/publications/generer` | Générer une publication + retouche du visuel | 4a + 4a1 | construit |
| `/calendrier` | Calendrier éditorial + Kanban | 7a + 8b | construit |
| `/messages` | Messagerie unifiée | 10a | construit |
| `/newsletter/envois` | Boîte d'envois newsletter | hors maquette | construit |
| `/newsletter/modeles` | Modèles de mail versionnés | hors maquette | construit |
| `/webinaires` | Webinaires + pop-up de publication | 12a + 12b | construit |
| `/reseaux` | Réseaux & plateformes | 6b | construit |
| `/historique` | Historique des activités | 7b | page d'attente |
| `/notifications` | Notifications | 11a | page d'attente |
| `/utilisateurs` | Habilitations et utilisateurs | F-22 | construit |
| `/parametres` | Paramètres | non maquettée | page d'attente |

Les écrans en attente ont une route et une place dans la navigation : le parcours
se vérifie de bout en bout, sans lien mort.

## Médias, graphiques et détail d'une publication

### L'import de médias est réel

Sur **Créer une publication**, les fichiers sont lus par le navigateur :
`URL.createObjectURL`, aperçu du média lui-même, et la durée d'une vidéo
relevée sur le fichier par un élément `<video>` temporaire. Les URL
d'objet sont révoquées au retrait d'un média et à la destruction du
composant — sans quoi le navigateur garde les fichiers en mémoire.

Rien ne quitte le poste : il n'y a pas encore de backend.

### Le média commande le format

Les cinq étapes suivent l'ordre de décision réel — média, puis format —
parce que **c'est le média qui dit quels formats sont possibles** :

| Média importé | Formats ouverts |
|---|---|
| aucun | aucun, avec la raison affichée |
| une vidéo | Reel, Vidéo, Story |
| une image | Image, Story |
| deux images ou plus | Carrousel, Image, Story |

Retirer un média qui ferme le format retenu rebascule sur le premier
format encore possible, plutôt que de laisser l'étape vide.

### Le résumé avant envoi

« Envoyer » ouvre une pop-up de relecture : aperçu du média, description
et son compte de caractères, format, **nombre d'images si carrousel**,
**durée si vidéo**, plateformes retenues, et la programmation donnée
**deux fois — Antananarivo et GMT**. Les plateformes raisonnent en UTC :
afficher les deux évite de découvrir après coup qu'une publication est
partie trois heures trop tôt.

### Le détail d'une publication s'adapte à son statut

| Statut | Ce que montre la pop-up |
|---|---|
| brouillon | légende, historique, et **Supprimer le brouillon** |
| programmée, approuvée, à valider | **emplacement du média**, bloc réactions encore vide, historique, et **Confirmer la publication** |
| publiée | emplacement du média, et **vues et réactions jour par jour** en barres survolables |

L'historique dit qui a créé, envoyé en validation, approuvé, programmé,
modifié ou confirmé — NF-02 et S-07 demandent de conserver auteur, date
et résultat de toute diffusion. Chaque étape porte un filet de couleur
selon sa nature.

### Les deux graphiques

`shared/time-bar-chart/` — vues et réactions jour par jour, en barres
jumelées. **Deux échelles distinctes** : les réactions valent quelques
dizaines quand les vues se comptent en milliers ; sur une échelle commune
la série des réactions serait une ligne plate contre l'axe. La légende
donne le maximum de chacune, pour qu'on ne compare pas deux hauteurs qui
ne se comparent pas.

`shared/multi-line-chart/` — une courbe par réseau, échelle verticale
commune. Les couleurs sont déclarées en `--series-*` dans
`styles/_tokens.scss` et **ne sont pas celles des plateformes** : côte à
côte, leurs rouges et leurs bleus se battraient entre eux et avec la
charte. La couleur ne porte jamais seule l'information — légende et
infobulle nomment toujours le réseau.

Les deux repèrent le point survolé par la **largeur rendue**, pas par les
unités du `viewBox` : avec `preserveAspectRatio="none"` le SVG est étiré
et les deux ne coïncident pas.

## Tableau de bord

OB-07 demande « un tableau de bord unique », F-19 à F-21 « performance par
canal et par période, participation aux événements ». Aucune maquette ne
lui correspond dans l'export v2.1 : la composition est une proposition.
C'est l'écran d'accueil après connexion.

| Bloc | Contenu |
|---|---|
| **À traiter** | ce qui bloque : publications à valider, messages non lus et hors délai, comptes à reconnecter, envois à reprendre |
| **Compteurs** | publiées, programmées, à valider, messages non lus |
| **Abonnés** | courbe sur 7 ou 30 jours, progression totale et gain par réseau |
| **Webinaires** | à venir, passés, brouillons ; taux de présence ; deux prochaines séances |
| **Publications qui ont porté** | les cinq meilleures, au choix par vues ou par réactions |
| **Par canal** | publications parties et audience, réseau par réseau |

Le bloc « à traiter » n'est pas décoratif : OB-04 dit qu'aucune publication
ne part sans validation humaine. Cette file est la traduction de cette
règle à l'écran, et chaque ligne mène directement là où l'action se fait.

### Deux précautions de lecture

**L'échelle de la courbe ne part pas de zéro.** Sur 18 500 abonnés, une
progression de 500 serait invisible autrement. La légende sous le
graphique donne les deux bornes, pour qu'on ne lise pas la pente pour plus
qu'elle ne vaut.

**Les vues ne sont pas ventilées par réseau.** `viewCount` est un cumul
porté par la publication : une publication partie sur trois réseaux ne
porte qu'un seul total. Attribuer ce total à chacun ferait des barres qui
additionnent trois fois la même audience. Le bloc « par canal » compte
donc les publications parties et l'audience du compte — deux faits
réellement par réseau — et le dit explicitement. Ventiler les vues
demandera un relevé réseau par réseau côté backend.

### Ce qui n'y est pas

Le suivi par campagne, que F-21 mentionne : le cahier des charges signale
lui-même que **la notion de campagne n'est pas encore modélisée**. Rien
n'a été inventé pour combler ce trou.

## Habilitations et utilisateurs

Trois colonnes : la liste des comptes, le détail du compte ouvert, et le
**journal de ses modifications** à droite.

### Pas de rôle — et c'est le cahier des charges qui le dit

> **F-22** — « Aucun rôle n'est figé dans le code : un administrateur
> attribue les droits — créer, valider, publier, consulter, administrer. »

La maquette fournie montrait un rôle, un bouton « Changer de rôle », une
colonne « hérité du rôle » et des exceptions. **Cette mécanique n'existe
pas dans IAGORA** : il n'y a rien à hériter, chaque droit se coche compte
par compte. La colonne « hérité » a donc été retirée, et la liste affiche
un résumé des droits là où la maquette affichait un rôle.

Les cinq droits viennent de `backend/app/modules/users/constants.py` et de
la migration `0002_droits` — mêmes codes, même ordre :

| Droit | Code | Exigence |
|---|---|---|
| Consulter | `read` | F-22 |
| Créer | `create` | F-22 · OB-04 |
| Valider | `review` | F-07 · règle métier 2 |
| Publier | `publish` | F-22 · NF-07 |
| Administrer | `admin` | F-22 · F-23 |

Chaque ligne porte sa référence et ce qu'elle ouvre concrètement : un
administrateur ne devrait pas avoir à deviner ce qu'il accorde.

### Journal des modifications

NF-02 et S-07 imposent de conserver auteur, date et résultat de toute
action sensible — attribuer un droit en fait partie. Le volet de droite
liste les entrées du compte ouvert, avec un filet de couleur par nature :
accent pour un droit, ambre pour la sécurité, gris pour le compte.

### Écarts par rapport à la maquette

| Demandé | Fait |
|---|---|
| Retirer le bloc « Sessions » | retiré — il reste méthode, double facteur, dernière connexion |
| Retirer « Changer de rôle » | retiré, comme toute la mécanique de rôle |
| Ajouter « Réinitialiser le mot de passe » | ajouté, **désactivé** sur un compte Google SSO ou une invitation en attente, avec la raison affichée |

Une modification de droit n'est pas appliquée à la volée : la ligne passe
en ambre, porte la mention « modifié », et un bouton « Annuler les
modifications » apparaît tant que rien n'est enregistré.

## Réseaux & plateformes

Un bloc par compte, avec les trois chiffres que les API de plateforme
rendent directement : **publications**, **abonnés**, **vues du profil**.

Le taux d'engagement de la maquette 6b a été retiré : il suppose la portée
de chaque publication, que les quatre réseaux n'exposent ni de la même
façon ni avec la même définition. Mieux vaut trois chiffres comparables
qu'un quatrième qui ne veut pas dire la même chose d'un réseau à l'autre.

Chaque bloc porte un bouton **Voir la page** vers le profil public. Deux
règles sur ces adresses :

1. **Jamais de lien passé par `l.facebook.com/l.php?u=…`.** Cette
   redirection porte un identifiant de suivi `fbclid` et une signature
   `h=` qui expire : le lien finit par casser. On enregistre l'adresse
   canonique de destination.
2. **Pas d'adresse devinée.** Quand elle n'est pas connue — TikTok ici —
   le bouton est désactivé et le pied du bloc affiche « adresse de profil
   à renseigner ». Un bouton inerte vaut mieux qu'un lien mort.

Le pied de chaque bloc rappelle la fraîcheur des statistiques. Un compte
dont le jeton a expiré passe en bordure pointillée, ses chiffres en gris,
avec la date de la dernière collecte et un bouton de reconnexion.

## La newsletter

Deux écrans sous **Événements › Newsletter**, un sous-menu repliable qui
ajoute un **troisième niveau** à la barre latérale. Il reste le seul, et
c'est délibéré : au-delà, une barre latérale devient un labyrinthe.
Arriver sur un de ces écrans par une URL directe ouvre les deux niveaux.

### Boîte d'envois

Quatorze envois, séparés en cinq catégories dans l'ordre du cycle de vie
d'un événement :

| Catégorie | Quand |
|---|---|
| Confirmation d'inscription | à la minute où quelqu'un s'inscrit |
| Rappel | J-7, J-1 et H-2 avant la séance |
| Modification ou annulation | déclenché à la main — c'est une mauvaise nouvelle, elle se relit |
| Compte rendu | dans les 48 h, avec les points clés |
| Visionnage | dès la mise en ligne de la rediffusion |

Ce découpage n'est pas décoratif : ces courriels ne se relisent pas de la
même façon. Un rappel se vérifie en volume, une annulation une par une.

Les envois se rattachent aux webinaires de `webinars.data.ts`. Ouvrir une
ligne montre ce qui est **réellement parti**, variables déjà substituées,
avec l'acheminement, l'engagement et, le cas échéant, le motif d'échec.

### Modèles de mail

Six modèles, groupés par les mêmes catégories, chacun avec son historique
de versions. La version en service porte un point vert ; regarder une
version antérieure affiche un avertissement — sans lui, on croirait relire
ce qui part aujourd'hui aux destinataires.

L'aperçu montre le rendu réel avec les `{{variables}}` **non substituées**
et surlignées : c'est justement ce qu'il faut relire avant de publier une
version.

### Le composant d'aperçu de courriel

`shared/email-preview/` rend un courriel aux couleurs de Datum et sert les
deux écrans. Largeur fixe de 560 px, pas de grille, pas de `flex` pour la
structure du message : c'est ce qu'acceptent les clients de messagerie.

Chaque courriel se termine par une **signature électronique** — sceau,
« L'équipe communication », organisation, horodatage et empreinte abrégée.
Les valeurs sont illustratives : la signature réelle sera produite côté
serveur, pas dans le navigateur.

## Les webinaires

Six événements : deux à venir, un brouillon, trois passés. Ils reprennent
ceux déjà cités ailleurs — le webinaire SEO du 15 septembre dont la
messagerie réclame la rediffusion, celui sur le RAG du 8 octobre annoncé
dans les publications.

**La pop-up d'un webinaire passé porte trois onglets**, là où un webinaire
à venir n'a que le détail — avant l'événement, il n'y a rien à publier
après coup :

| Onglet | Contenu |
|---|---|
| **Détail** | la maquette 12b : chiffres, description, graphique d'inscriptions, inscrits, animation, rappels |
| **Poster le visuel de promo** | quatre déclinaisons du flyer (16:9, 4:5, 1:1, story 9:16), aperçu, légende, choix des réseaux |
| **Poster compte rendu & rediffusion** | miniature de la rediffusion, compte rendu rédigé, points saillants, hashtags, lien et audience |

Choisir un format coche les réseaux auxquels il est destiné — **en ne
retenant que les comptes réellement raccordés**. Un format story vise
Instagram et TikTok, mais TikTok n'est pas connecté : il serait sinon coché
dans l'état, absent de la liste, donc impossible à décocher, et nommé dans
la confirmation.

Les deux boutons « Publier » **ne publient rien** : le message de
confirmation le dit explicitement plutôt que de laisser croire à un envoi.

### Le bouton de lecture de la rediffusion

Il est **figuratif**, et le gabarit le traite comme tel : c'est un `<span>`
en `aria-hidden`, ni cliquable ni atteignable au clavier. Le bloc entier est
l'aperçu de ce que verra le public — miniature, durée, barre de
progression — pas un lecteur. La légende sous l'aperçu le dit aussi.
Le vrai lien de la rediffusion vit dans la colonne de droite.

La miniature (`flyers/webinar-seo-replay-16-9.svg`) est dessinée comme une
capture de l'enregistrement : la diapositive sur les Core Web Vitals,
l'intervenant en médaillon, et un assombrissement central pour que le
bouton blanc se détache.

## La messagerie unifiée

Douze conversations statiques, toutes sur les webinaires et les formations
de Datum Academy, et accrochées aux publications de `publications.data.ts` :
le webinaire SEO du 15 septembre, celui sur le RAG du 8 octobre, la formation
Cloud AWS, le module Kubernetes, les portes ouvertes du 10 octobre et la
certification Oracle.

La répartition suit la maquette : 6 messages privés, 5 commentaires,
1 mention ; 4 Instagram, 3 Facebook, 3 LinkedIn, 2 TikTok. Les compteurs des
filtres sont calculés, pas écrits en dur.

**Ouvertures et clics ne sont pas mesurés**, et c'est délibéré. Ils
demandent un pixel de suivi et une réécriture des liens — donc une
infrastructure à part, que le protocole SMTP ne fournit pas. L'écran
s'en tient à ce qu'un serveur d'envoi rend réellement : **destinataires,
messages remis, rejets**. Un envoi programmé ou interrompu avant départ
affiche des tirets plutôt que des zéros : rien n'a été tenté, donc rien
n'a rebondi.

Le volet de droite a trois états, chacun porté par les données :

| État | Ce qu'il montre |
|---|---|
| brouillon d'agent | le texte proposé, les boutons approuver / modifier / rejeter, et la mention « rien n'est envoyé sans cette action » |
| sans brouillon | une note, et la réponse manuelle seule |
| fenêtre fermée | un bandeau rouge, le champ désactivé, et un renvoi vers la plateforme |

Ce dernier état applique la règle E-03 : Meta n'accepte une réponse depuis
une application tierce que dans les 24 h qui suivent le dernier message reçu.
Deux conversations du jeu sont dans ce cas, pour que l'état soit visible sans
manipulation.

Les anciennetés (« 22 min », « 1 j ») sont écrites en clair plutôt que
calculées : sur un jeu figé, une date relative à l'horloge dériverait au fil
des jours et finirait par mentir.

## Les visuels de l'écran de génération

`public/flyers/` contient six flyers réellement dessinés, et non des
placeholders rayés : trois pour les propositions (4:5 et 1:1) et trois
versions verticales 9:16 pour la pop-up de retouche.

Quatre autres (`webinar-seo-*.svg`) déclinent la promotion du webinaire SEO
aux couleurs de Datum — et non à celles d'AWS : ici le sujet est Datum
lui-même. Un cinquième sert de miniature à la rediffusion.

Les trois versions du visuel AWS diffèrent vraiment, pour que les pastilles `v1 / v2 / v3`
et l'historique des retouches disent la vérité :

| | |
|---|---|
| `v1` | premier jet, texte posé à même le fond |
| `v2` | voile sombre ajouté — « contraste du texte renforcé » |
| `v3` | palette bleu nuit `#232F3E` / orange `#FF9900` appliquée |

Ce sont des SVG, donc n'importe quelle taille d'affichage reste nette. Leur
typographie est une pile sans-serif système et non les polices de
l'application : une image chargée par `<img>` n'a pas accès aux polices de
la page. Un vrai flyer a de toute façon sa propre typographie.

La palette bleu nuit / orange est celle du sujet traité (une formation AWS),
pas celle de Datum : c'est ce que décrit la maquette 4a1, et c'est ce que
montrent les pastilles « palette utilisée ». Remplacer ces fichiers par vos
propres visuels suffit — seuls les chemins dans
`core/data/generation.data.ts` sont à ajuster.

## Structure

```
src/
├── styles/
│   ├── _tokens.scss        charte Datum — la seule source de couleurs
│   ├── _fonts.scss         @font-face des polices auto-hébergées
│   ├── _base.scss          remise à zéro, typographie, utilitaires
│   └── _components.scss    boutons, champs, cartes, statuts, tableaux
└── app/
    ├── core/
    │   ├── models/         types métier
    │   ├── data/           jeux de données statiques
    │   └── services/       PublicationStore, Session, SidebarState
    ├── shared/             Icon, NetworkLogo, BrandLogo, StatusBadge
    ├── layout/             AppShell, Sidebar, Topbar
    └── features/           un dossier par écran
```

**Langue.** Identifiants, types et noms de fichiers en **anglais** ;
commentaires et textes affichés en **français**. Les URL sont en français :
elles sont visibles par l'utilisateur, au même titre qu'un titre d'écran.
C'est la règle de `../CONTRIBUTING.md`.

**La barre du haut appartient à l'écran**, pas à la coquille : ses actions
changent d'un écran à l'autre. Chaque page rend son `<app-topbar>` et reçoit ses
actions par projection de contenu.

## Brancher le backend

Les trois points de contact sont isolés :

| Service | À remplacer par |
|---|---|
| `PublicationStore` | `GET /api/v1/publications` |
| `Session` | `POST /api/v1/auth/login` + garde de route |
| `generation.data.ts` | `POST /api/v1/generation` |
| `InboxStore` | `GET /api/v1/messages` + `POST .../replies` |
| `webinars.data.ts` | `GET /api/v1/webinars` + `POST .../publish` |
| `newsletter-sends.data.ts` | `GET /api/v1/newsletter/sends` |
| `mail-templates.data.ts` | `GET /api/v1/mail-templates` |
| `users.data.ts` | `GET /api/v1/users` + `GET /api/v1/users/{id}/changes` |
| `followerHistory` | relevé quotidien à conserver — aucune plateforme ne rend cet historique de façon fiable au-delà de quelques semaines |
| `social-networks.data.ts` | `GET /api/v1/social-accounts` |

Le filtrage des publications peut rester côté client tant que le volume le
permet ; seule la façon de charger les données change.
