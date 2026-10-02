import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  PUBLICATION_FORMAT_LABELS,
  PUBLICATION_STATUS_LABELS,
  Publication,
  PublicationStatus,
} from '../../../core/models/publication';
import { PublicationStore } from '../../../core/services/publication-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';
import { StatusBadge } from '../../../shared/status-badge/status-badge';

/** Une case du calendrier mensuel. */
interface CalendarDay {
  readonly date: Date;
  /** Numéro du jour, affiché dans la case. */
  readonly dayNumber: number;
  /** Faux pour les jours de débord du mois précédent ou suivant. */
  readonly isInMonth: boolean;
  readonly isToday: boolean;
  readonly publications: readonly Publication[];
}

/** Une colonne du tableau Kanban. */
interface KanbanColumn {
  readonly status: PublicationStatus;
  readonly label: string;
  readonly publications: readonly Publication[];
}

/** Colonnes retenues : le flux de production, sans les états terminaux. */
const KANBAN_STATUSES: readonly PublicationStatus[] = [
  'draft',
  'review',
  'approved',
  'scheduled',
  'published',
];

/** Calendrier éditorial — maquettes 7a (mois) et 8b (Kanban). */
@Component({
  selector: 'app-editorial-calendar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon, NetworkLogo, StatusBadge],
  templateUrl: './editorial-calendar.html',
  styleUrl: './editorial-calendar.scss',
})
export class EditorialCalendar {
  private readonly store = inject(PublicationStore);

  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly statusLabels = PUBLICATION_STATUS_LABELS;
  protected readonly weekdayNames = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'];

  protected readonly view = signal<'month' | 'kanban'>('month');
  protected readonly selected = signal<Publication | null>(null);

  /** Premier jour du mois affiché. */
  private readonly cursor = signal(startOfMonth(new Date()));

  protected readonly monthLabel = computed(() =>
    this.cursor().toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' }),
  );

  /**
   * Grille du mois : six semaines de sept jours, lundi en tête.
   *
   * Six semaines toujours, pour que la hauteur ne saute pas d'un mois
   * à l'autre.
   */
  protected readonly weeks = computed<readonly (readonly CalendarDay[])[]>(() => {
    const first = this.cursor();
    const todayKey = dateKey(new Date());
    const byDay = this.publicationsByDay();

    // Reculer jusqu'au lundi qui ouvre la grille.
    const start = new Date(first);
    const offset = (first.getDay() + 6) % 7;
    start.setDate(first.getDate() - offset);

    const weeks: CalendarDay[][] = [];
    const cursor = new Date(start);

    for (let week = 0; week < 6; week += 1) {
      const days: CalendarDay[] = [];
      for (let day = 0; day < 7; day += 1) {
        const date = new Date(cursor);
        const key = dateKey(date);
        days.push({
          date,
          dayNumber: date.getDate(),
          isInMonth: date.getMonth() === first.getMonth(),
          isToday: key === todayKey,
          publications: byDay.get(key) ?? [],
        });
        cursor.setDate(cursor.getDate() + 1);
      }
      weeks.push(days);
    }

    return weeks;
  });

  /** Publications programmées du mois affiché, par ordre chronologique. */
  protected readonly monthPublications = computed(() => {
    const first = this.cursor();
    return this.store
      .everything()
      .filter((publication) => {
        const iso = publication.scheduledAt ?? publication.publishedAt;
        if (!iso) return false;
        const date = new Date(iso);
        return date.getFullYear() === first.getFullYear() && date.getMonth() === first.getMonth();
      })
      .sort((left, right) => sortKey(left).localeCompare(sortKey(right)));
  });

  protected readonly kanbanColumns = computed<readonly KanbanColumn[]>(() =>
    KANBAN_STATUSES.map((status) => ({
      status,
      label: PUBLICATION_STATUS_LABELS[status],
      publications: this.store.everything().filter((publication) => publication.status === status),
    })),
  );

  /** Index des publications par jour, pour ne pas filtrer dans chaque case. */
  private readonly publicationsByDay = computed(() => {
    const index = new Map<string, Publication[]>();
    for (const publication of this.store.everything()) {
      const iso = publication.scheduledAt ?? publication.publishedAt;
      if (!iso) continue;
      const key = dateKey(new Date(iso));
      const bucket = index.get(key);
      if (bucket) bucket.push(publication);
      else index.set(key, [publication]);
    }
    return index;
  });

  protected shiftMonth(delta: number): void {
    const next = new Date(this.cursor());
    next.setMonth(next.getMonth() + delta);
    this.cursor.set(startOfMonth(next));
  }

  protected goToToday(): void {
    this.cursor.set(startOfMonth(new Date()));
  }

  protected timeOf(publication: Publication): string {
    const iso = publication.scheduledAt ?? publication.publishedAt;
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  protected dateOf(publication: Publication): string {
    const iso = publication.scheduledAt ?? publication.publishedAt;
    if (!iso) return 'Sans date';
    return new Date(iso).toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    });
  }

  protected select(publication: Publication): void {
    this.selected.set(publication);
  }
}

/** Premier jour du mois, à minuit. */
function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

/** Clé `AAAA-MM-JJ` en heure locale — `toISOString` décalerait d'un fuseau. */
function dateKey(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function sortKey(publication: Publication): string {
  return publication.scheduledAt ?? publication.publishedAt ?? '';
}
