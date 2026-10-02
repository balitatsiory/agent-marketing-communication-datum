import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { WEBINARS } from '../../../core/data/webinars.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { SocialNetworkCode } from '../../../core/models/social-network';
import {
  WEBINAR_FILTER_LABELS,
  Webinar,
  WebinarFilter,
  WebinarVisual,
} from '../../../core/models/webinar';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/** Onglets de la pop-up d'un webinaire passé. */
type WebinarTab = 'detail' | 'promo' | 'replay';

/** Une barre du graphique d'inscriptions. */
interface SparkBar {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
  /** Jeton de couleur : les pics de promotion se détachent. */
  readonly fill: string;
}

/** Nombre de webinaires passés affichés avant le bouton « voir les suivants ». */
const PAST_PAGE_SIZE = 2;

/** Échelle fixe du graphique : 0 à 10 inscriptions par jour. */
const SPARK_MAX = 10;
const SPARK_WIDTH = 320;
const SPARK_HEIGHT = 96;
const SPARK_PAD = 6;

/**
 * Webinaires — maquettes 12a (liste) et 12b (pop-up de détail).
 *
 * Un webinaire passé ouvre une pop-up à onglets : au détail s'ajoutent
 * la publication du visuel de promotion et celle du compte rendu avec sa
 * rediffusion. Un webinaire à venir n'a que le détail — il n'y a encore
 * rien à publier après coup.
 *
 * Aucune publication n'est réellement envoyée : voir `publish()`.
 */
@Component({
  selector: 'app-webinar-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, Topbar, Icon, NetworkLogo],
  templateUrl: './webinar-list.html',
  styleUrl: './webinar-list.scss',
})
export class WebinarList {
  protected readonly filterLabels = WEBINAR_FILTER_LABELS;
  protected readonly filters: readonly WebinarFilter[] = ['all', 'scheduled', 'draft', 'past'];
  protected readonly allNetworks = SOCIAL_NETWORKS;

  private readonly webinars = signal<readonly Webinar[]>(WEBINARS);

  protected readonly filter = signal<WebinarFilter>('all');
  protected readonly isPastExpanded = signal(false);

  protected readonly counts = computed(() => {
    const all = this.webinars();
    return {
      all: all.length,
      scheduled: all.filter((webinar) => webinar.status === 'scheduled').length,
      draft: all.filter((webinar) => webinar.status === 'draft').length,
      past: all.filter((webinar) => webinar.status === 'past').length,
    };
  });

  /** Inscrits cumulés, tous webinaires confondus. */
  protected readonly totalRegistrations = computed(() =>
    this.webinars().reduce((total, webinar) => total + webinar.registrationCount, 0),
  );

  /** « À venir » regroupe les webinaires programmés et les brouillons. */
  protected readonly upcoming = computed(() => {
    const filter = this.filter();
    if (filter === 'past') return [];
    return this.webinars().filter((webinar) =>
      filter === 'all'
        ? webinar.status !== 'past'
        : filter === 'scheduled'
          ? webinar.status === 'scheduled'
          : webinar.status === 'draft',
    );
  });

  private readonly allPast = computed(() => {
    const filter = this.filter();
    if (filter === 'scheduled' || filter === 'draft') return [];
    return this.webinars().filter((webinar) => webinar.status === 'past');
  });

  protected readonly past = computed(() =>
    this.isPastExpanded() ? this.allPast() : this.allPast().slice(0, PAST_PAGE_SIZE),
  );

  protected readonly hiddenPastCount = computed(() => this.allPast().length - this.past().length);

  /* ---------- pop-up ---------- */

  protected readonly opened = signal<Webinar | null>(null);
  protected readonly tab = signal<WebinarTab>('detail');
  protected readonly visualIndex = signal(0);

  /** Réseaux cochés pour la publication du visuel, puis du compte rendu. */
  protected readonly promoNetworks = signal<ReadonlySet<SocialNetworkCode>>(new Set());
  protected readonly replayNetworks = signal<ReadonlySet<SocialNetworkCode>>(new Set());

  /** Message de confirmation après une publication simulée. */
  protected readonly publishNotice = signal<string | null>(null);

  protected readonly selectedVisual = computed<WebinarVisual | null>(() => {
    const visuals = this.opened()?.promoVisuals ?? [];
    return visuals[this.visualIndex()] ?? visuals[0] ?? null;
  });

  /** Réseaux connectés auxquels le format retenu est destiné. */
  protected readonly visualTargets = computed(() => {
    const visual = this.selectedVisual();
    if (!visual) return [];
    return this.allNetworks.filter(
      (network) => network.isConnected && visual.networks.includes(network.code),
    );
  });

  protected readonly connectedNetworks = computed(() =>
    this.allNetworks.filter((network) => network.isConnected),
  );

  /** Barres du graphique d'inscriptions du webinaire ouvert. */
  protected readonly sparkBars = computed<readonly SparkBar[]>(() => {
    const series = this.opened()?.registrationSeries ?? [];
    if (series.length === 0) return [];
    const barWidth = (SPARK_WIDTH - SPARK_PAD * 2) / series.length;
    return series.map((value, index) => {
      const height = Math.max(1, (value / SPARK_MAX) * (SPARK_HEIGHT - 20));
      return {
        x: SPARK_PAD + index * barWidth + 1,
        y: SPARK_HEIGHT - 12 - height,
        width: barWidth - 2,
        height,
        fill: value >= 7 ? 'var(--accent)' : index === series.length - 1 ? 'var(--ink-2)' : 'var(--border-2)',
      };
    });
  });

  /** Ordonnée du repère pointillé, posé à 5 inscriptions. */
  protected readonly sparkGuideY = SPARK_HEIGHT - 12 - (5 / SPARK_MAX) * (SPARK_HEIGHT - 20);
  protected readonly sparkBaselineY = SPARK_HEIGHT - 12;
  protected readonly sparkWidth = SPARK_WIDTH;
  protected readonly sparkPad = SPARK_PAD;

  /**
   * Change d'onglet et efface la confirmation.
   *
   * Sans cela, le message « visuel de promotion prêt » resterait affiché
   * dans l'onglet du compte rendu, où il ne veut plus rien dire.
   */
  protected setTab(tab: WebinarTab): void {
    this.tab.set(tab);
    this.publishNotice.set(null);
  }

  protected setFilter(filter: WebinarFilter): void {
    this.filter.set(filter);
    this.isPastExpanded.set(false);
  }

  protected open(webinar: Webinar): void {
    this.opened.set(webinar);
    this.tab.set('detail');
    this.visualIndex.set(0);
    this.publishNotice.set(null);
    // Les réseaux visés par le premier format sont cochés d'emblée : c'est
    // le choix attendu neuf fois sur dix.
    this.preselectNetworks(webinar.promoVisuals[0]?.networks ?? []);
    this.replayNetworks.set(this.onlyConnected(['linkedin', 'facebook']));
  }

  /**
   * Ne retient que les réseaux effectivement raccordés.
   *
   * Un format peut viser TikTok alors que le compte n'est pas connecté :
   * sans ce filtre, il serait coché dans l'état, absent de la liste — donc
   * impossible à décocher — et nommé dans la confirmation.
   */
  private onlyConnected(codes: readonly SocialNetworkCode[]): ReadonlySet<SocialNetworkCode> {
    const connected = new Set(this.connectedNetworks().map((network) => network.code));
    return new Set(codes.filter((code) => connected.has(code)));
  }

  private preselectNetworks(codes: readonly SocialNetworkCode[]): void {
    this.promoNetworks.set(this.onlyConnected(codes));
  }

  protected close(): void {
    this.opened.set(null);
  }

  protected selectVisual(index: number): void {
    this.visualIndex.set(index);
    const visual = this.opened()?.promoVisuals[index];
    if (visual) this.preselectNetworks(visual.networks);
    this.publishNotice.set(null);
  }

  protected togglePromoNetwork(code: SocialNetworkCode): void {
    this.promoNetworks.update((current) => toggle(current, code));
  }

  protected toggleReplayNetwork(code: SocialNetworkCode): void {
    this.replayNetworks.update((current) => toggle(current, code));
  }

  protected labelFor(code: SocialNetworkCode): string {
    return this.allNetworks.find((network) => network.code === code)?.label ?? code;
  }

  /**
   * Publication simulée.
   *
   * Rien ne part : le prototype n'a pas de backend, et le message de
   * confirmation le dit plutôt que de laisser croire à un envoi.
   */
  protected publish(kind: 'promo' | 'replay'): void {
    const codes = [...(kind === 'promo' ? this.promoNetworks() : this.replayNetworks())];
    if (codes.length === 0) return;
    const names = codes.map((code) => this.labelFor(code)).join(', ');
    const what = kind === 'promo' ? 'Visuel de promotion' : 'Compte rendu et rediffusion';
    this.publishNotice.set(`${what} prêt pour ${names} — simulation, rien n'a été envoyé.`);
  }
}

/** Ajoute ou retire une valeur, en renvoyant un nouvel ensemble. */
function toggle<T>(current: ReadonlySet<T>, value: T): ReadonlySet<T> {
  const next = new Set(current);
  if (!next.delete(value)) next.add(value);
  return next;
}
