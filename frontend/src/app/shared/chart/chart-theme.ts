import { SocialNetworkCode } from '../../core/models/social-network';

/**
 * Thème ECharts d'IAGORA.
 *
 * ECharts dessine dans un canvas : il ne sait pas résoudre une
 * couleur écrite `var(--accent)`. Le thème lit donc les jetons sur
 * `:root` au moment où il est construit, et les transmet en valeurs
 * littérales. Conséquence pratique : les graphiques suivent la
 * charte sans qu'aucune couleur soit écrite deux fois.
 *
 * Licence : Apache ECharts est sous Apache 2.0, libre en usage
 * commercial. Aucun fichier de Phoenix n'est repris ici — seules
 * ses décisions de mise en forme le sont.
 */

/** Lit un jeton CSS sur `:root`, avec une valeur de repli hors navigateur. */
export function cssToken(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export const IAGORA_CHART_THEME_NAME = 'iagora';

/**
 * Couleurs de série par réseau, résolues en valeurs littérales.
 *
 * ⚠ Ces cinq teintes sont celles de `_tokens.scss`. Passées au
 * contrôle de lisibilité, deux d'entre elles ne se séparent pas :
 * `--series-linkedin` (#8a6d1f) et `--series-tiktok` (#157347)
 * n'ont que 5,0 d'écart perceptuel en vision protanope, et 13,2 en
 * vision normale — sous le seuil de 15 en dessous duquel deux
 * séries voisines deviennent difficiles à distinguer. Le doré
 * LinkedIn tombe en plus sous le plancher de saturation : il est lu
 * comme un gris.
 *
 * `ACCESSIBLE_NETWORK_SERIES` plus bas corrige cela. Le choix entre
 * les deux appartient à l'équipe : il touche à la charte, pas au
 * code. En attendant, toute légende doit nommer le réseau — la
 * couleur ne porte jamais seule l'information.
 */
export function networkSeriesColors(): Record<SocialNetworkCode, string> {
  return {
    instagram: cssToken('--series-instagram', '#167fa4'),
    facebook: cssToken('--series-facebook', '#5b4b8a'),
    linkedin: cssToken('--series-linkedin', '#8a6d1f'),
    tiktok: cssToken('--series-tiktok', '#157347'),
    youtube: cssToken('--series-youtube', '#a8432c'),
  };
}

/**
 * Variante validée des couleurs de série.
 *
 * Mêmes familles de teintes que ci-dessus — Facebook reste violet,
 * TikTok reste vert — poussées dans un registre plus lumineux. Le
 * pire écart entre deux séries voisines remonte à 8,7 en vision
 * protanope et 22,6 en vision normale ; la saturation et la bande
 * de luminosité passent sur les cinq.
 *
 * L'orange YouTube reste sous 3:1 de contraste sur fond blanc :
 * partout où il sert, la valeur doit être écrite à côté de la barre
 * ou reprise dans un tableau. C'est ce que fait `barChartOption`.
 *
 * Pour l'adopter : remplacer l'appel à `networkSeriesColors()` par
 * celui-ci dans les composants de graphique, puis reporter les
 * valeurs dans `_tokens.scss` pour que le reste de l'interface
 * suive.
 */
export const ACCESSIBLE_NETWORK_SERIES: Readonly<Record<SocialNetworkCode, string>> = {
  linkedin: '#3874ff',
  facebook: '#a855f7',
  instagram: '#d6336c',
  tiktok: '#1c7c3c',
  youtube: '#e5780b',
};

/**
 * Construit le thème. À appeler une fois, après que la feuille de
 * style globale est appliquée — sinon les jetons ne sont pas encore
 * lisibles et ce sont les valeurs de repli qui sortent.
 */
export function buildIagoraChartTheme(): Record<string, unknown> {
  const ink = cssToken('--ink', '#212529');
  const muted = cssToken('--muted', '#5d6d76');
  const border = cssToken('--border', '#dee2e6');
  const grid = cssToken('--ground-2', '#eaf1f4');
  const surface = cssToken('--surface', '#ffffff');
  const accent = cssToken('--accent', '#167fa4');
  const family = cssToken('--f-body', 'system-ui, sans-serif');

  /* Deux crans de l'échelle : 10,24 px pour les graduations,
     12,8 px pour tout ce qui doit se lire sans effort. */
  const axisSize = 10.24;
  const labelSize = 12.8;

  const axis = {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: muted, fontFamily: family, fontSize: axisSize, fontWeight: 600 },
    splitLine: { lineStyle: { color: grid, width: 1 } },
  };

  return {
    /* L'ordre compte : une série garde sa couleur quel que soit son
       rang. Ne jamais recycler au-delà de la cinquième — au-delà,
       regrouper en « Autres » ou faire plusieurs graphiques. */
    color: Object.values(ACCESSIBLE_NETWORK_SERIES),
    backgroundColor: 'transparent',
    textStyle: { fontFamily: family, fontSize: labelSize, color: ink },

    title: {
      textStyle: { color: ink, fontFamily: family, fontSize: 16, fontWeight: 700 },
      subtextStyle: { color: muted, fontFamily: family, fontSize: labelSize },
    },

    /* Marques fines, extrémités arrondies côté valeur. */
    line: {
      smooth: false,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 2 },
      itemStyle: { borderWidth: 2, borderColor: surface },
    },
    bar: {
      barMaxWidth: 18,
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    },

    categoryAxis: { ...axis, splitLine: { show: false } },
    valueAxis: axis,

    legend: {
      textStyle: { color: ink, fontFamily: family, fontSize: labelSize, fontWeight: 600 },
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 16,
    },

    tooltip: {
      backgroundColor: ink,
      borderWidth: 0,
      padding: [8, 11],
      textStyle: { color: surface, fontFamily: family, fontSize: labelSize },
      axisPointer: { lineStyle: { color: accent, width: 1, type: 'dashed' } },
    },

    grid: { left: 48, right: 18, top: 16, bottom: 28, containLabel: false },

    /* Une série vide doit le dire, pas afficher un cadre muet. */
    emptyCircleStyle: { color: border },
  };
}
