import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';

import { WebinarDto, WebinarStatsDto } from '../../../core/api/webinars.api';
import { CountUp } from '../../../shared/count-up/count-up';
import { Icon } from '../../../shared/icon/icon';
import { longSchedule, monthLabel } from '../webinar-format';

/** Une colonne du graphique chronologique. */
interface Column {
  readonly label: string;
  readonly short: string;
  readonly count: number;
  readonly share: number;
}

/** Au-delà de deux ans, une colonne par mois deviendrait illisible. */
const MOIS_MAX = 24;

/**
 * Pop-up des statistiques.
 *
 * Chaque graphique ne porte qu'une série : une seule teinte suffit, le titre
 * la nomme, et la valeur est écrite à côté ou au survol.
 */
@Component({
  selector: 'app-webinar-stats',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CountUp, Icon],
  templateUrl: './webinar-stats.html',
  styleUrl: './webinar-stats.scss',
})
export class WebinarStatsDialog {
  readonly stats = input.required<WebinarStatsDto>();
  readonly closed = output<void>();
  /** Demande d'ouverture de la fiche du prochain webinaire. */
  readonly opened = output<number>();

  protected readonly asTable = signal(false);
  protected readonly hovered = signal<Column | null>(null);

  protected readonly byYear = computed(() => {
    const mois = this.stats().by_month;
    if (!mois.length) return false;
    return ecartEnMois(mois[0].month, mois[mois.length - 1].month) >= MOIS_MAX;
  });

  /** Colonnes continues : un mois (ou une année) sans événement reste visible. */
  protected readonly columns = computed<readonly Column[]>(() => {
    const mois = this.stats().by_month;
    if (!mois.length) return [];
    const comptes = new Map<string, number>();
    const annuel = this.byYear();
    for (const { month, count } of mois) {
      const cle = annuel ? month.slice(0, 4) : month;
      comptes.set(cle, (comptes.get(cle) ?? 0) + count);
    }
    const premier = mois[0].month;
    const dernier = mois[mois.length - 1].month;
    const cles: string[] = [];
    if (annuel) {
      for (let an = +premier.slice(0, 4); an <= +dernier.slice(0, 4); an++) cles.push(String(an));
    } else {
      for (let i = 0; i <= ecartEnMois(premier, dernier); i++) cles.push(decaler(premier, i));
    }
    const maximum = Math.max(...comptes.values());
    return cles.map((cle) => {
      const count = comptes.get(cle) ?? 0;
      return {
        label: annuel ? cle : monthLabel(cle),
        short: annuel ? cle : `${cle.slice(5)}/${cle.slice(2, 4)}`,
        count,
        share: count / maximum,
      };
    });
  });

  protected readonly typeMaximum = computed(() =>
    Math.max(1, ...this.stats().by_type.map((item) => item.count)),
  );
  protected readonly categoryMaximum = computed(() =>
    Math.max(1, ...this.stats().by_category.map((item) => item.count)),
  );
  protected readonly accountMaximum = computed(() =>
    Math.max(1, ...this.stats().accounts.map((item) => item.total)),
  );

  protected schedule(webinaire: WebinarDto): string {
    return longSchedule(webinaire);
  }
}

function ecartEnMois(debut: string, fin: string): number {
  const rang = (mois: string): number => +mois.slice(0, 4) * 12 + +mois.slice(5, 7);
  return rang(fin) - rang(debut);
}

function decaler(mois: string, pas: number): string {
  const rang = +mois.slice(0, 4) * 12 + +mois.slice(5, 7) - 1 + pas;
  return `${Math.floor(rang / 12)}-${String((rang % 12) + 1).padStart(2, '0')}`;
}
