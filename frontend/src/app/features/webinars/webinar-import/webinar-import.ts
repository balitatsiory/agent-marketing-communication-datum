import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  output,
  signal,
} from '@angular/core';

import { toApiError } from '../../../core/api/api-error';
import { FlyerBatchDto, ImportReportDto, WebinarsApi } from '../../../core/api/webinars.api';
import { CountUp } from '../../../shared/count-up/count-up';
import { Icon } from '../../../shared/icon/icon';

type FileKind = 'webinars' | 'pages' | 'flyers';

/** Flyers rapatriés par appel : assez petit pour que la barre avance. */
const LOT = 5;

/**
 * Reprise des webinaires du site, en deux temps.
 *
 * Les données entrent d'abord ; les flyers sont ensuite rapatriés par petits
 * lots, avec une barre de progression. Les deux gestes se rejouent sans
 * doublon.
 */
@Component({
  selector: 'app-webinar-import',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CountUp, Icon],
  templateUrl: './webinar-import.html',
  styleUrl: './webinar-import.scss',
})
export class WebinarImportDialog {
  readonly closed = output<void>();
  readonly changed = output<void>();

  private readonly api = inject(WebinarsApi);

  protected readonly fields: readonly { kind: FileKind; label: string; name: string }[] = [
    { kind: 'webinars', label: 'Webinaires · obligatoire', name: 'webinaires.json' },
    { kind: 'pages', label: 'Pages d’inscription', name: 'pages-inscription.json' },
    { kind: 'flyers', label: 'Manifeste des flyers', name: 'flyers.manifest.json' },
  ];

  protected readonly files = signal<Partial<Record<FileKind, File>>>({});
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly report = signal<ImportReportDto | null>(null);

  protected readonly fetching = signal(false);
  protected readonly stored = signal(0);
  protected readonly failures = signal<FlyerBatchDto['errors']>([]);
  protected readonly remaining = signal<number | null>(null);

  protected readonly progress = computed(() => {
    const reste = this.remaining();
    if (reste === null) return 0;
    const faits = this.stored() + this.failures().length;
    return faits + reste === 0 ? 100 : (faits / (faits + reste)) * 100;
  });

  private isClosed = false;

  constructor() {
    // Fermer la pop-up arrête la boucle après le lot en cours.
    inject(DestroyRef).onDestroy(() => (this.isClosed = true));
  }

  protected choose(kind: FileKind, champ: HTMLInputElement): void {
    const fichier = champ.files?.[0];
    this.files.update((choisis) => ({ ...choisis, [kind]: fichier }));
  }

  protected async runImport(): Promise<void> {
    const { webinars, pages, flyers } = this.files();
    if (!webinars || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    this.report.set(null);
    try {
      this.report.set(await this.api.importFiles(webinars, pages ?? null, flyers ?? null));
      this.changed.emit();
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.busy.set(false);
    }
  }

  protected async fetchFlyers(retryFailed = false): Promise<void> {
    if (this.fetching()) return;
    this.fetching.set(true);
    this.error.set(null);
    this.stored.set(0);
    this.failures.set([]);
    this.remaining.set(null);
    try {
      let reprise = retryFailed;
      do {
        const lot = await this.api.fetchFlyers(LOT, reprise);
        reprise = false;
        this.stored.update((n) => n + lot.stored);
        this.failures.update((liste) => [...liste, ...lot.errors]);
        this.remaining.set(lot.remaining);
        this.changed.emit();
        // Un lot vide alors qu'il reste des flyers ne finirait jamais.
        if (lot.stored + lot.failed === 0) break;
      } while ((this.remaining() ?? 0) > 0 && !this.isClosed);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    } finally {
      this.fetching.set(false);
    }
  }
}
