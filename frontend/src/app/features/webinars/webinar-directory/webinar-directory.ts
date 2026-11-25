import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import {
  SortDirection,
  WebinarDto,
  WebinarFilters,
  WebinarReferenceDto,
  WebinarSort,
  WebinarStatsDto,
  WebinarStatusCode,
  WebinarsApi,
} from '../../../core/api/webinars.api';
import { ZoomAccountDto, ZoomAccountsApi } from '../../../core/api/zoom-accounts.api';
import { Session } from '../../../core/services/session';
import { Topbar } from '../../../layout/topbar/topbar';
import { CountUp } from '../../../shared/count-up/count-up';
import { Icon } from '../../../shared/icon/icon';
import { WebinarDetailDialog } from '../webinar-detail/webinar-detail';
import { WebinarImportDialog } from '../webinar-import/webinar-import';
import { WebinarStatsDialog } from '../webinar-stats/webinar-stats';
import {
  dateBlock,
  durationLabel,
  longSchedule,
  statusModifier,
  timeLabel,
} from '../webinar-format';

type View = 'list' | 'grid';
/** `all` cumule ; `none` retient les fiches sans compte Zoom ; sinon l'identifiant. */
type AccountChoice = 'all' | 'none' | number;

const PAGE_SIZES = [12, 24, 48] as const;
const PREFERENCES = 'iagora.webinars.view';
const ATTENTE_RECHERCHE_MS = 300;

interface Tile {
  readonly status: WebinarStatusCode | null;
  readonly label: string;
  readonly value: number;
}

function lirePreferences(): { view: View; size: number } {
  try {
    const lu = JSON.parse(localStorage.getItem(PREFERENCES) ?? '{}') as Partial<{
      view: View;
      size: number;
    }>;
    return {
      view: lu.view === 'grid' ? 'grid' : 'list',
      size: PAGE_SIZES.find((taille) => taille === lu.size) ?? PAGE_SIZES[0],
    };
  } catch {
    return { view: 'list', size: PAGE_SIZES[0] };
  }
}

/**
 * Webinaires — liste et grille (maquette 12a), branchées sur l'API.
 *
 * Le compte choisi filtre à la fois les chiffres d'en-tête et la liste ;
 * « Tous les comptes » les cumule, webinaires repris du site compris.
 */
@Component({
  selector: 'app-webinar-directory',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DecimalPipe,
    RouterLink,
    Topbar,
    Icon,
    CountUp,
    WebinarDetailDialog,
    WebinarImportDialog,
    WebinarStatsDialog,
  ],
  templateUrl: './webinar-directory.html',
  styleUrl: './webinar-directory.scss',
})
export class WebinarDirectory {
  /** `?fiche=12` ouvre directement la pop-up d'un webinaire. */
  readonly fiche = input<string>();

  private readonly api = inject(WebinarsApi);
  private readonly zoomApi = inject(ZoomAccountsApi);
  private readonly session = inject(Session);
  private readonly router = inject(Router);

  protected readonly pageSizes = PAGE_SIZES;
  protected readonly dateBlock = dateBlock;
  protected readonly durationLabel = durationLabel;
  protected readonly timeLabel = timeLabel;
  protected readonly longSchedule = longSchedule;
  protected readonly statusModifier = statusModifier;

  protected readonly canManage = computed(() => this.session.has('manage_webinars'));
  protected readonly canManageAccounts = computed(() =>
    this.session.has('manage_zoom_accounts'),
  );

  /* ---------- filtres ---------- */

  protected readonly account = signal<AccountChoice>('all');
  protected readonly status = signal<WebinarStatusCode | null>(null);
  protected readonly type = signal('');
  protected readonly category = signal('');
  protected readonly search = signal('');
  protected readonly sort = signal<WebinarSort>('date');
  protected readonly direction = signal<SortDirection>('desc');
  protected readonly view = signal<View>(lirePreferences().view);
  protected readonly size = signal(lirePreferences().size);
  protected readonly page = signal(1);

  /* ---------- données ---------- */

  protected readonly items = signal<readonly WebinarDto[]>([]);
  protected readonly total = signal(0);
  protected readonly pages = signal(0);
  protected readonly stats = signal<WebinarStatsDto | null>(null);
  protected readonly reference = signal<WebinarReferenceDto | null>(null);
  protected readonly accounts = signal<readonly ZoomAccountDto[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  /* ---------- pop-ups et actions ---------- */

  protected readonly openedId = signal<number | null>(null);
  protected readonly isStatsOpen = signal(false);
  protected readonly isImportOpen = signal(false);
  protected readonly isNumberOpen = signal(false);
  protected readonly meetingNumber = signal('');
  protected readonly meetingAccount = signal<number | null>(null);
  protected readonly syncing = signal(false);
  protected readonly importing = signal(false);
  protected readonly messages = signal<readonly { ok: boolean; text: string }[]>([]);

  private demande = 0;
  private demandeStats = 0;
  private attente: ReturnType<typeof setTimeout> | undefined;

  private readonly filters = computed<WebinarFilters>(() => {
    const choix = this.account();
    return {
      id_zoom_accounts: typeof choix === 'number' ? choix : null,
      unassigned: choix === 'none',
    };
  });

  /** Les tuiles suivent le compte choisi, pas les autres filtres. */
  protected readonly tiles = computed<readonly Tile[]>(() => {
    const stats = this.stats();
    return [
      { status: null, label: 'Total', value: stats?.total ?? 0 },
      { status: 'scheduled', label: 'À venir', value: stats?.scheduled ?? 0 },
      { status: 'past', label: 'Passés', value: stats?.past ?? 0 },
      { status: 'draft', label: 'Brouillons', value: stats?.draft ?? 0 },
    ];
  });

  protected readonly hasFilters = computed(
    () => !!(this.status() || this.type() || this.category() || this.search().trim()),
  );

  protected readonly range = computed(() => {
    const total = this.total();
    if (total === 0) return '0';
    const debut = (this.page() - 1) * this.size() + 1;
    return `${debut}–${Math.min(total, debut + this.size() - 1)} sur ${total}`;
  });

  /** Numéros de page affichés : les voisins de la page courante et les bouts. */
  protected readonly pageNumbers = computed<readonly (number | null)[]>(() => {
    const total = this.pages();
    const courante = this.page();
    const gardees = [...new Set([1, courante - 1, courante, courante + 1, total])]
      .filter((n) => n >= 1 && n <= total)
      .sort((a, b) => a - b);
    return gardees.flatMap((n, i) => (i > 0 && n - gardees[i - 1] > 1 ? [null, n] : [n]));
  });

  constructor() {
    void this.chargerReferences();

    // Chaque changement de filtre, de tri ou de page relit la liste.
    effect(() => {
      this.filters();
      this.status();
      this.type();
      this.category();
      this.sort();
      this.direction();
      this.page();
      this.size();
      untracked(() => void this.chargerListe());
    });
    effect(() => {
      this.filters();
      untracked(() => void this.chargerStats());
    });
    effect(() => {
      const demandee = Number(this.fiche());
      if (Number.isInteger(demandee) && demandee > 0) {
        untracked(() => this.openedId.set(demandee));
      }
    });
    effect(() => {
      try {
        localStorage.setItem(
          PREFERENCES,
          JSON.stringify({ view: this.view(), size: this.size() }),
        );
      } catch {
        // Stockage indisponible : la préférence ne survivra pas au rechargement.
      }
    });
    inject(DestroyRef).onDestroy(() => clearTimeout(this.attente));
  }

  /* ---------- lecture ---------- */

  private async chargerReferences(): Promise<void> {
    try {
      const [reference, accounts] = await Promise.all([
        this.api.reference(),
        this.zoomApi.list(),
      ]);
      this.reference.set(reference);
      this.accounts.set(accounts);
      this.meetingAccount.set(accounts[0]?.id_zoom_accounts ?? null);
    } catch (erreur) {
      this.error.set(toApiError(erreur).message);
    }
  }

  private async chargerListe(): Promise<void> {
    const numero = ++this.demande;
    this.loading.set(true);
    try {
      const reponse = await this.api.list({
        ...this.filters(),
        status: this.status(),
        type: this.type(),
        category: this.category(),
        q: this.search().trim(),
        sort: this.sort(),
        direction: this.direction(),
        page: this.page(),
        size: this.size(),
      });
      // Une réponse tardive ne doit pas écraser celle d'un filtre plus récent.
      if (numero !== this.demande) return;
      if (reponse.pages > 0 && this.page() > reponse.pages) {
        this.page.set(reponse.pages);
        return;
      }
      this.items.set(reponse.items);
      this.total.set(reponse.total);
      this.pages.set(reponse.pages);
      this.error.set(null);
    } catch (erreur) {
      if (numero === this.demande) this.error.set(toApiError(erreur).message);
    } finally {
      if (numero === this.demande) this.loading.set(false);
    }
  }

  private async chargerStats(): Promise<void> {
    const numero = ++this.demandeStats;
    try {
      const stats = await this.api.stats(this.filters());
      if (numero === this.demandeStats) this.stats.set(stats);
    } catch (erreur) {
      if (numero === this.demandeStats) this.error.set(toApiError(erreur).message);
    }
  }

  protected reload(): void {
    void this.chargerListe();
    void this.chargerStats();
  }

  /* ---------- filtres ---------- */

  protected chooseAccount(valeur: string): void {
    this.account.set(valeur === 'all' || valeur === 'none' ? valeur : Number(valeur));
    this.page.set(1);
  }

  protected chooseStatus(status: WebinarStatusCode | null): void {
    this.status.set(status);
    // À venir : la prochaine séance d'abord. Ailleurs : la plus récente.
    if (this.sort() === 'date') this.direction.set(status === 'scheduled' ? 'asc' : 'desc');
    this.page.set(1);
  }

  protected chooseType(valeur: string): void {
    this.type.set(valeur);
    this.page.set(1);
  }

  protected chooseCategory(valeur: string): void {
    this.category.set(valeur);
    this.page.set(1);
  }

  protected chooseSort(valeur: string): void {
    this.sort.set(valeur as WebinarSort);
    this.direction.set(valeur === 'title' ? 'asc' : 'desc');
    this.page.set(1);
  }

  protected toggleDirection(): void {
    this.direction.update((sens) => (sens === 'asc' ? 'desc' : 'asc'));
    this.page.set(1);
  }

  protected chooseSize(valeur: string): void {
    this.size.set(Number(valeur));
    this.page.set(1);
  }

  /** La recherche attend la fin de la frappe. */
  protected typeSearch(valeur: string): void {
    this.search.set(valeur);
    clearTimeout(this.attente);
    this.attente = setTimeout(() => {
      if (this.page() === 1) void this.chargerListe();
      else this.page.set(1);
    }, ATTENTE_RECHERCHE_MS);
  }

  protected resetFilters(): void {
    const avaitUneRecherche = this.search() !== '';
    this.search.set('');
    this.type.set('');
    this.category.set('');
    this.status.set(null);
    this.page.set(1);
    if (avaitUneRecherche) void this.chargerListe();
  }

  /* ---------- actions ---------- */

  protected open(id: number): void {
    this.openedId.set(id);
  }

  protected closeDetail(): void {
    this.openedId.set(null);
    if (this.fiche()) void this.router.navigate([], { queryParams: {} });
  }

  protected async syncZoom(): Promise<void> {
    if (this.syncing()) return;
    const choix = this.account();
    this.syncing.set(true);
    this.messages.set([]);
    try {
      const resultat = await this.api.syncZoom(typeof choix === 'number' ? choix : null);
      this.messages.set(
        resultat.accounts.length
          ? resultat.accounts.map((compte) => ({
              ok: compte.ok,
              text: `${compte.label} — ${compte.message}`,
            }))
          : [{ ok: false, text: 'Aucun compte Zoom raccordé.' }],
      );
      this.reload();
    } catch (erreur) {
      this.messages.set([{ ok: false, text: toApiError(erreur).message }]);
    } finally {
      this.syncing.set(false);
    }
  }

  protected async importByNumber(): Promise<void> {
    const compte = this.meetingAccount();
    const numero = this.meetingNumber().trim();
    if (compte === null || !/^[0-9 ]{9,20}$/.test(numero) || this.importing()) return;
    this.importing.set(true);
    this.messages.set([]);
    try {
      const fiche = await this.api.importMeeting(compte, numero);
      this.isNumberOpen.set(false);
      this.meetingNumber.set('');
      this.reload();
      this.openedId.set(fiche.id_webinars);
    } catch (erreur) {
      this.messages.set([{ ok: false, text: toApiError(erreur).message }]);
      this.isNumberOpen.set(false);
    } finally {
      this.importing.set(false);
    }
  }

  protected openFromStats(id: number): void {
    this.isStatsOpen.set(false);
    this.openedId.set(id);
  }
}
