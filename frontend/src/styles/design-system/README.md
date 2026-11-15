# Design system IAGORA

Quatre décisions de mise en forme, relevées sur le thème **Phoenix
v1.24.0** de Prium, appliquées aux composants d'IAGORA avec les
couleurs de la charte Datum.

La structure vient de Phoenix. Les couleurs restent celles de Datum :
on n'a pas importé le bleu de Phoenix, on a rangé les teintes de
Datum dans ses cinq cases.

---

## Les quatre décisions

### 1. Une seule famille — Nunito Sans, 300 à 900

`--f-display` et `--f-body` pointent sur la même police. Ce qui
distingue un titre d'un paragraphe, c'est la graisse, pas la famille.

`--f-mono` (IBM Plex Mono) survit pour ce qui a réellement besoin
d'une chasse fixe caractère par caractère : identifiants, extraits de
code, gabarits de prompt. **Pas pour les nombres** : `.num` leur donne
`font-variant-numeric: tabular-nums`, ce qui les aligne en colonne
sans changer de police.

`--f-emoji` ferme chaque pile, pour qu'un emoji d'aperçu de
publication ne tombe jamais sur un carré vide.

> Instrument Serif et Karla restent déclarées dans `_fonts.scss` mais
> ne sont référencées nulle part. Une règle `@font-face` inutilisée ne
> déclenche aucun téléchargement : elles ne coûtent rien et restent
> là si vous voulez réintroduire la serif sur les titres.

### 2. Échelle modulaire 1.25, racine 16 px

Six crans, et rien entre les crans.

| Jeton     | rem        | px     | Pour quoi                                  |
|-----------|------------|--------|--------------------------------------------|
| `--t-2xs` | 0.64       | 10,24  | libellés capitales, graduations d'axe      |
| `--t-xs`  | 0.8        | 12,80  | métadonnées, cellules denses, légendes     |
| `--t-md`  | 1          | 16     | corps de texte — valeur par défaut          |
| `--t-lg`  | 1.25       | 20     | titres de carte, sous-titres                |
| `--t-xl`  | 1.5625     | 25     | chiffres clés, `h2`                         |
| `--t-2xl` | 1.953125   | 31,25  | titre de page, `h1`                         |

**Avant :** 24 tailles distinctes entre 9 et 30 px, réglées à l'œil
écran par écran, dont cinq valeurs non entières (9,975 · 10,925 ·
11,96 · 12,42 · 14,72) nées d'un empilement de `em` dans les modèles
de mail. **Après :** six jetons.

> Si une taille vous manque, ce n'est pas un barreau qui manque —
> c'est la hiérarchie qui doit passer par la graisse.

> ⚠ Conséquence assumée : le corps passe de 14 à 16 px et le plancher
> de 9 à 10,24 px. Les écrans denses gagnent en hauteur de ligne.

### 3. La hiérarchie passe par la graisse

| Jeton         | Valeur | Pour quoi                           |
|---------------|--------|-------------------------------------|
| `--w-light`   | 300    | réservé aux très grands corps        |
| `--w-regular` | 400    | texte courant                        |
| `--w-semi`    | 600    | libellés, en-têtes de tableau        |
| `--w-bold`    | 700    | titres de section, valeurs en avant  |
| `--w-extra`   | 800    | chiffres clés, titre de page         |

Sur la page widgets de Phoenix, 326 blocs de texte sur 1 100 sont en
12,8 px **gras ou semi-gras**. Le corps reste petit, c'est la graisse
qui dit l'importance : on garde la densité sans perdre la lecture.

### 4. Cinq rôles, chacun avec son fond doux

| Rôle      | Couleur Datum      | Sens                              |
|-----------|--------------------|-----------------------------------|
| `primary` | `--accent`         | l'action, le chemin principal     |
| `success` | `--ok`             | parti, validé, en ligne           |
| `warning` | `--wait`           | attend une action humaine         |
| `danger`  | `--err`            | a échoué, ou expire               |
| `info`    | `--lavender-deep`  | un repère, sans urgence           |
| `neutral` | `--muted`          | la même forme, sans signal        |

`info` est nouveau : il manquait à l'application.

Chaque rôle expose trois variables : `--role-X`, `--role-X-soft`
(le fond doux) et `--role-X-line` (le trait).

**Contrastes mesurés** (rapport WCAG) :

| Rôle    | sur blanc | sur son fond doux |
|---------|-----------|-------------------|
| primary | 4,56      | **3,50**          |
| success | 5,87      | 5,04              |
| warning | 4,90      | 4,27              |
| danger  | 5,74      | 4,70              |
| info    | 7,45      | 6,21              |

> ⚠ `primary` sur `primary-soft` ne vaut que **3,50:1**. Suffisant
> pour un glyphe d'icône (seuil 3:1 pour le non-texte), insuffisant
> pour du petit texte (seuil 4,5:1). Sur une pastille primary,
> prendre `--ink` pour le texte.

---

## S'en servir

### Poser un rôle

Une classe `.role-*` pose `--hue`, `--tint` et `--line`. Les
composants lisent ces trois variables sans jamais savoir quel rôle
ils portent — c'est ce qui les rend interchangeables.

```html
<span class="icon-chip role-success"><app-icon name="check" /></span>
```

### La pastille d'icône

En Angular, passez par le composant, qui type le rôle :

```html
<app-icon-chip name="check" role="success" />
<app-icon-chip name="warn" role="warning" size="lg" />
<app-icon-chip name="megaphone" role="primary" solid />
```

Il réutilise `<app-icon>` tel quel et n'ajoute que la pastille :
toute icône ajoutée à `ICON_SET` y devient utilisable sans rien
changer. Aucune dépendance d'icônes n'est installée.

### La tuile de chiffre à icône

Motif de la page CRM › Analytics de Phoenix : une icône de la couleur
du rôle, un grand chiffre, sa légende. Pas de carte par cellule — un
simple trait les sépare, et c'est le bloc qui porte le cadre.

```html
<div class="stat-figures">
  <div class="stat-figure role-success">
    <span class="stat-figure__icon"><app-icon name="check" /></span>
    <span class="stat-figure__value">1 121</span>
    <span class="stat-figure__label">Messages remis</span>
    <span class="stat-figure__note">hors rejets</span>
  </div>
</div>
```

Les mesures de Phoenix tombent exactement sur l'échelle : son chiffre
est à 31,25 px graisse 800 (`--t-2xl` + `--w-extra`), sa légende à
12,8 px (`--t-xs`).

Donnez un rôle **différent par chiffre** quand ils n'ont pas le même
sens : un rejet n'est pas un envoi réussi, et la couleur doit le dire
avant la lecture. En service sur `/newsletter/envois`.

À distinguer de `.stats` / `.stat` (dans `_components.scss`), qui
reste le motif par défaut : une carte par chiffre, libellé au-dessus,
sans icône. `.stat-figures` est le motif « vitrine ».

### Les mixins, dans un SCSS de composant

```scss
@use '../../../styles/design-system/type' as type;

.card__label { @include type.caps-label; }
.card__value { @include type.key-figure; }
.page__title { @include type.page-title; }
```

Préférez les mixins aux classes utilitaires dans les composants : le
gabarit reste lisible, et la règle vit à côté du reste du style.

### Un graphique

```html
<div class="plot" [appChart]="followerOption()"></div>
```
```scss
.plot { width: 100%; height: 220px; }  /* une hauteur est obligatoire */
```
```ts
import { Chart } from '../../shared/chart/chart';
// …
protected readonly followerOption = computed<EChartsOption>(() => ({
  xAxis: { type: 'category', data: this.days() },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: this.values(), areaStyle: {} }],
}));
```

La directive prend en charge l'initialisation après rendu, le
redimensionnement du conteneur, la destruction de l'instance et
l'exécution hors zone Angular. Ne refaites aucun des quatre.

Les couleurs, graisses et tailles du graphique viennent du thème,
qui lit les jetons CSS : **n'écrivez aucune couleur dans une option
ECharts.**

---

## Après un `git pull`

```bash
npm install   # echarts, ajouté aux dépendances
```

Les polices sont versionnées dans `public/fonts/`, comme les trois
autres familles du projet : rien à télécharger. `npm run fonts:nunito`
ne sert qu'à les régénérer (montée de version, nouveau
sous-ensemble).

---

## Licences

Ce qui est repris ici, et à quelles conditions.

| Élément | Licence | Ce que ça implique |
|---|---|---|
| **Nunito Sans** | SIL OFL 1.1 | Libre, usage commercial et auto-hébergement compris. Le texte de la licence doit accompagner les fichiers redistribués : il est versionné dans `public/fonts/nunito-sans-OFL.txt`. |
| **Apache ECharts** | Apache 2.0 | Libre, y compris en production commerciale. |
| **Les icônes** | — | Celles d'`ICON_SET`, déjà dans le dépôt. Aucune dépendance d'icônes n'a été ajoutée. |
| **Font Awesome** | — | **Non utilisé.** Phoenix s'en sert ; nous non. À titre indicatif : sur sa page widgets, 479 icônes sont en style Solid et 8 en Brands, tous deux gratuits, mais 7 sont en style Regular, réservé à l'abonnement Pro payant. |
| **Le thème Phoenix** | commercial (Prium) | **Aucun fichier repris.** Ni sa feuille de style, ni son HTML, ni ses composants. Seules ses décisions de mise en forme — une échelle, une hiérarchie, un motif de pastille — qui ne se possèdent pas. Aucune licence requise. |

---

## Règles qui tiennent le système

1. **Aucune valeur hexadécimale hors `_tokens.scss`.** Règle déjà en
   vigueur dans le projet ; elle s'étend aux options ECharts.
2. **Aucune taille de police hors de l'échelle.** Pas de `font-size`
   en px dans un composant, pas de `em` imbriqués.
3. **Un rôle, pas une couleur.** Un composant demande `warning`, pas
   `#8a6d1f`.
4. **La couleur ne porte jamais seule l'information.** Un badge
   nomme son état, une légende nomme sa série.
5. **Rien sous `--t-2xs`.**

## Les fichiers

```
src/styles/design-system/
  _type.scss       échelle, graisses, interlignes, mixins
  _roles.scss      les cinq rôles et leurs fonds doux
  _icon-chip.scss  la pastille
  _stat-figure.scss la tuile de chiffre à icône
  README.md        ce document

src/app/shared/
  semantic-role.ts      le type SemanticRole, partagé
  icon-chip/icon-chip.ts  <app-icon-chip>
  chart/chart.ts          la directive [appChart]
  chart/chart-theme.ts    le thème ECharts et les palettes de séries
```
