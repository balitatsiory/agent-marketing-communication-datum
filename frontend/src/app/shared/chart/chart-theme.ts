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
 * Les valeurs vivent dans `_tokens.scss` ; ce sont elles qui font
 * foi. Les valeurs de repli ci-dessous ne servent qu'au rendu hors
 * navigateur, où aucun jeton n'est lisible.
 *
 * Elles ont été vérifiées : bande de luminosité, plancher de
 * saturation, séparation en protanopie, deutéranopie et tritanopie,
 * contraste sur le fond. Le pire écart entre deux séries voisines
 * vaut 8,7 en protanopie.
 *
 * Une réserve subsiste : l'orange YouTube reste sous 3:1 de
 * contraste sur fond blanc. Partout où il sert, la valeur doit être
 * écrite à côté de la marque ou reprise dans un tableau. Et comme
 * toujours, la couleur ne porte jamais seule l'information : la
 * légende nomme le réseau.
 */
export function networkSeriesColors(): Record<SocialNetworkCode, string> {
  return {
    linkedin: cssToken('--series-linkedin', '#3874ff'),
    facebook: cssToken('--series-facebook', '#a855f7'),
    instagram: cssToken('--series-instagram', '#d6336c'),
    tiktok: cssToken('--series-tiktok', '#1c7c3c'),
    youtube: cssToken('--series-youtube', '#e5780b'),
  };
}

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
    color: Object.values(networkSeriesColors()),
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
