import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CONVERSATIONS } from '../../../core/data/conversations.data';
import { NEWSLETTER_SENDS } from '../../../core/data/newsletter-sends.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { WEBINARS } from '../../../core/data/webinars.data';
import { Publication } from '../../../core/models/publication';
import { NETWORK_SERIES_COLORS, SocialNetwork } from '../../../core/models/social-network';
import { PublicationStore } from '../../../core/services/publication-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';
import { StatusBadge } from '../../../shared/status-badge/status-badge';
import { LineSeries, MultiLineChart } from '../../../shared/multi-line-chart/multi-line-chart';
import { RouterLink } from '@angular/router';

/** Fenêtre d'observation du graphique d'abonnés. */
type Window = 7 | 30;

/** Critère de classement des publications. */
type TopMetric = 'views' | 'reactions';

/** Un point du graphique, en coordonnées du `viewBox`. */
interface ChartPoint {
  readonly x: number;
  readonly y: number;
  readonly value: number;
  readonly dayIndex: number;
}

/** Une entrée de la file « à traiter ». */
interface ActionItem {
  /** Libellé au singulier et au pluriel : « 1 compte » et non « 1 comptes ». */
  readonly one: string;
  readonly many: string;
  readonly count: number;
  readonly route: string;
  readonly isUrgent: boolean;
}

const CHART_WIDTH = 640;
const CHART_HEIGHT = 160;
const CHART_PAD_X = 4;
const CHART_PAD_TOP = 12;
const CHART_PAD_BOTTOM = 18;

/**
 * Tableau de bord — OB-07 « un tableau de bord unique », F-19 à F-21.
 *
 * Aucune maquette ne lui correspond dans l'export v2.1 : la composition
 * est une proposition. Elle s'en tient à ce que les données de
 * l'application rendent déjà, et laisse de côté le suivi par campagne,
 * que le cahier des charges signale comme non modélisé.
 */
@Component({
  selector: 'app-overview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Topbar, Icon, NetworkLogo, StatusBadge, MultiLineChart],
  templateUrl: './overview.html',
  styleUrl: './overview.scss',
})
export class Overview {
  private readonly publications = inject(PublicationStore);

  protected readonly networks = SOCIAL_NETWORKS;
  protected readonly connectedNetworks = SOCIAL_NETWORKS.filter((network) => network.isConnected);

  protected readonly window = signal<Window>(30);
  protected readonly topMetric = signal<TopMetric>('views');

  /* ---------- publications ---------- */

  protected readonly publicationCounts = computed(() => {
    const all = this.publications.everything();
    return {
      published: all.filter((publication) => publication.status === 'published').length,
      scheduled: all.filter(
        (publication) => publication.status === 'scheduled' || publication.status === 'approved',
      ).length,
      review: all.filter((publication) => publication.status === 'review').length,
      draft: all.filter((publication) => publication.status === 'draft').length,
    };
  });

  /** Les cinq publications les plus vues, ou les plus réagies. */
  protected readonly topPublications = computed<readonly Publication[]>(() => {
    const metric = this.topMetric();
    return [...this.publications.everything()]
      .filter((publication) => publication.publishedAt !== null)
      .sort((left, right) =>
        metric === 'views'
          ? right.viewCount - left.viewCount
          : right.reactionCount - left.reactionCount,
      )
      .slice(0, 5);
  });

  protected metricOf(publication: Publication): number {
    return this.topMetric() === 'views' ? publication.viewCount : publication.reactionCount;
  }

  /* ---------- messages ---------- */

  protected readonly unreadMessageCount = computed(
    () => CONVERSATIONS.filter((conversation) => !conversation.isRead).length,
  );

  /** Messages dont la fenêtre de réponse de la plateforme est fermée. */
  protected readonly lateMessageCount = computed(
    () => CONVERSATIONS.filter((conversation) => conversation.isReplyWindowClosed).length,
  );

  /* ---------- abonnés ---------- */

  /** Somme des abonnés des comptes raccordés, jour par jour. */
  private readonly totalSeries = computed<readonly number[]>(() => {
    const length = this.connectedNetworks[0]?.followerHistory.length ?? 0;
    return Array.from({ length }, (_, day) =>
      this.connectedNetworks.reduce((sum, network) => sum + network.followerHistory[day], 0),
    );
  });

  /** La portion de série correspondant à la fenêtre choisie. */
  private readonly windowSeries = computed<readonly number[]>(() =>
    this.totalSeries().slice(-this.window()),
  );

  protected readonly followerTotal = computed(
    () => this.windowSeries()[this.windowSeries().length - 1] ?? 0,
  );

  /** Progression sur la fenêtre : dernier relevé moins le premier. */
  protected readonly followerGain = computed(() => {
    const series = this.windowSeries();
    if (series.length < 2) return 0;
    return series[series.length - 1] - series[0];
  });

  /** Progression en pourcentage, virgule décimale comprise. */
  protected readonly followerGainRate = computed(() => {
    const series = this.windowSeries();
    if (series.length < 2 || series[0] === 0) return '0';
    const rate = Math.round((this.followerGain() / series[0]) * 1000) / 10;
    return rate.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  });

  protected readonly isGaining = computed(() => this.followerGain() > 0);

  /**
   * Une courbe par réseau raccordé.
   *
   * Toutes partagent la même échelle verticale : c'est ce qui permet de
   * les comparer. Les écarts d'audience restent lisibles parce que les
   * ordres de grandeur sont voisins — de 1 240 à 8 420 abonnés.
   */
  protected readonly followerSeries = computed<readonly LineSeries[]>(() =>
    this.connectedNetworks.map((network) => ({
      key: network.code,
      label: network.label,
      color: NETWORK_SERIES_COLORS[network.code],
      values: network.followerHistory.slice(-this.window()),
    })),
  );

  /** Libellés de l'axe horizontal : J-29 … hier, aujourd'hui. */
  protected readonly dayLabels = computed<readonly string[]>(() => {
    const count = this.window();
    return Array.from({ length: count }, (_, index) => {
      const back = count - 1 - index;
      if (back === 0) return "aujourd'hui";
      if (back === 1) return 'hier';
      return `il y a ${back} jours`;
    });
  });

  /** Gain par réseau sur la fenêtre, le plus gros d'abord. */
  protected readonly gainByNetwork = computed(() =>
    this.connectedNetworks
      .map((network) => ({
        network,
        gain: this.gainOf(network),
      }))
      .sort((left, right) => right.gain - left.gain),
  );

  protected colorOf(code: SocialNetwork['code']): string {
    return NETWORK_SERIES_COLORS[code];
  }

  private gainOf(network: SocialNetwork): number {
    const series = network.followerHistory.slice(-this.window());
    if (series.length < 2) return 0;
    return series[series.length - 1] - series[0];
  }

  /* ---------- webinaires ---------- */

  protected readonly webinarCounts = computed(() => ({
    upcoming: WEBINARS.filter((webinar) => webinar.status === 'scheduled').length,
    past: WEBINARS.filter((webinar) => webinar.status === 'past').length,
    draft: WEBINARS.filter((webinar) => webinar.status === 'draft').length,
    registrations: WEBINARS.reduce((sum, webinar) => sum + webinar.registrationCount, 0),
    attendees: WEBINARS.reduce((sum, webinar) => sum + (webinar.attendeeCount ?? 0), 0),
  }));

  /** Les deux prochaines séances. */
  protected readonly nextWebinars = computed(() =>
    WEBINARS.filter((webinar) => webinar.status === 'scheduled').slice(0, 2),
  );

  /** Taux de présence observé sur les séances passées. */
  protected readonly attendanceRate = computed(() => {
    const past = WEBINARS.filter((webinar) => webinar.status === 'past');
    const registered = past.reduce((sum, webinar) => sum + webinar.registrationCount, 0);
    const attended = past.reduce((sum, webinar) => sum + (webinar.attendeeCount ?? 0), 0);
    return registered ? Math.round((attended / registered) * 100) : 0;
  });

  /* ---------- file « à traiter » ---------- */

  /**
   * Ce qui attend une action humaine.
   *
   * OB-04 : aucune publication ne part sans validation. Cette file est la
   * traduction de cette règle sur le tableau de bord.
   */
  protected readonly actionItems = computed<readonly ActionItem[]>(() =>
    [
      {
        one: 'publication à valider',
        many: 'publications à valider',
        count: this.publicationCounts().review,
        route: '/publications',
        isUrgent: true,
      },
      {
        one: 'message non lu',
        many: 'messages non lus',
        count: this.unreadMessageCount(),
        route: '/messages',
        isUrgent: false,
      },
      {
        one: 'message hors délai de réponse',
        many: 'messages hors délai de réponse',
        count: this.lateMessageCount(),
        route: '/messages',
        isUrgent: true,
      },
      {
        one: 'compte à reconnecter',
        many: 'comptes à reconnecter',
        count: this.networks.filter((network) => !network.isConnected).length,
        route: '/reseaux',
        isUrgent: true,
      },
      {
        one: 'envoi de newsletter à reprendre',
        many: 'envois de newsletter à reprendre',
        count: NEWSLETTER_SENDS.filter(
          (send) => send.status === 'failed' || send.status === 'partial',
        ).length,
        route: '/newsletter/envois',
        isUrgent: false,
      },
    ].filter((item) => item.count > 0),
  );

  protected readonly totalToHandle = computed(() =>
    this.actionItems().reduce((sum, item) => sum + item.count, 0),
  );

  /* ---------- par canal ---------- */

  /**
   * Activité par canal — F-19, « performance par canal ».
   *
   * On compte les publications parties et l'audience du compte, pas les
   * vues : `viewCount` est un cumul porté par la publication, pas ventilé
   * par réseau. Une publication partie sur trois réseaux donnerait trois
   * fois le même total, et des barres qui additionnent la même audience.
   * Ventiler demandera un relevé par réseau côté backend.
   */
  protected readonly byChannel = computed(() => {
    const published = this.publications
      .everything()
      .filter((publication) => publication.publishedAt !== null);

    const rows = this.connectedNetworks.map((network) => ({
      network,
      publications: published.filter((publication) =>
        publication.networks.includes(network.code),
      ).length,
      followers: network.followerCount,
    }));

    const maxPublications = Math.max(1, ...rows.map((row) => row.publications));
    return rows
      .map((row) => ({ ...row, share: Math.round((row.publications / maxPublications) * 100) }))
      .sort((left, right) => right.publications - left.publications);
  });

  protected displayDate(publication: Publication): string {
    const iso = publication.publishedAt ?? publication.scheduledAt;
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }
}
