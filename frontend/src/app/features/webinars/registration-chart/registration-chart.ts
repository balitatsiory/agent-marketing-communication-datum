import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import type { EChartsOption } from 'echarts';

import { DailyCount } from '../../../core/api/webinars.api';
import { Chart } from '../../../shared/chart/chart';
import { cssToken } from '../../../shared/chart/chart-theme';

/**
 * Inscriptions jour par jour, en barres ECharts.
 *
 * Une seule série : le titre de la section la nomme, une seule teinte suffit.
 * Le survol porte sur toute la colonne du jour, si bien qu'un jour sans
 * inscription se lit aussi.
 */
@Component({
  selector: 'app-registration-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Chart],
  template: `<div class="plot" role="img" [attr.aria-label]="summary()" [appChart]="option()"></div>`,
  styles: `
    :host {
      display: block;
    }
    .plot {
      width: 100%;
      height: 170px;
    }
  `,
})
export class RegistrationChart {
  /** Un point par jour, dans l'ordre. */
  readonly series = input.required<readonly DailyCount[]>();

  /** Ce que dit le graphique, pour qui ne le voit pas. */
  protected readonly summary = computed(() => {
    const total = this.series().reduce((somme, point) => somme + point.count, 0);
    const pic = this.series().reduce<DailyCount | null>(
      (meilleur, point) => (!meilleur || point.count > meilleur.count ? point : meilleur),
      null,
    );
    return pic
      ? `Inscriptions par jour : ${inscriptions(total)} sur ${this.series().length} jours, ` +
          `au plus ${pic.count} le ${jour(pic.day, 'long')}.`
      : 'Aucune inscription.';
  });

  protected readonly option = computed<EChartsOption>(() => {
    const points = this.series();
    return {
      grid: { left: 30, right: 6, top: 10, bottom: 24 },
      tooltip: {
        trigger: 'axis',
        // La pop-up défile : sans cela l'infobulle serait rognée au bord.
        confine: true,
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const survole = Array.isArray(params) ? params[0] : params;
          const point = points[survole.dataIndex];
          return `${jour(point.day, 'long')}<br /><b>${inscriptions(point.count)}</b>`;
        },
      },
      xAxis: {
        type: 'category',
        data: points.map((point) => jour(point.day, 'short')),
        axisLabel: { hideOverlap: true },
      },
      // Des personnes : pas de graduation à 0,5.
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          type: 'bar',
          name: 'Inscriptions',
          data: points.map((point) => point.count),
          barMaxWidth: 18,
          barCategoryGap: '20%',
          itemStyle: { color: cssToken('--accent', '#167fa4'), borderRadius: [4, 4, 0, 0] },
          emphasis: { itemStyle: { color: cssToken('--accent-deep', '#0a4d64') } },
        },
      ],
    };
  });
}

/** « 27 oct. » sur l'axe, « mardi 27 octobre 2026 » dans l'infobulle. */
function jour(valeur: string, forme: 'short' | 'long'): string {
  // Midi UTC : le jour compté par l'API ne glisse dans aucun fuseau.
  return new Date(`${valeur}T12:00:00Z`).toLocaleDateString('fr-FR', {
    timeZone: 'UTC',
    day: 'numeric',
    month: forme,
    ...(forme === 'long' ? { weekday: 'long', year: 'numeric' } : {}),
  });
}

function inscriptions(nombre: number): string {
  return `${nombre} inscription${nombre > 1 ? 's' : ''}`;
}
