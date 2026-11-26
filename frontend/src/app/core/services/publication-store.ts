import { Injectable, computed, inject, signal } from '@angular/core';
import { PublicationsApi, PublicationSummaryDto } from '../api/publications.api';
import { PUBLICATIONS } from '../data/publications.data';
import { Publication, PublicationFormat, PublicationStatus } from '../models/publication';
import { MeetingPublicationType } from '../models/webinar';
import { SocialNetworkCode } from '../models/social-network';

/** Type de publication filtrable : un type d'événement lié, ou aucun lien. */
export type EventTypeFilter = MeetingPublicationType | 'none';

/** Critères de tri proposés par la barre d'outils. */
export type PublicationSort = 'recent' | 'views' | 'comments';

export const PUBLICATION_SORT_LABELS: Readonly<Record<PublicationSort, string>> = {
  recent: 'les plus récentes',
  views: 'vues',
  comments: 'commentaires',
};

/**
 * Source unique des publications et de leur filtrage.
 *
 * Les données sont statiques pour l'instant ; seule la façon de les
 * charger changera quand le backend sera branché. Le filtrage, lui,
 * restera côté client tant que le volume le permet.
 */
@Injectable({ providedIn: 'root' })
export class PublicationStore {
  private readonly api = inject(PublicationsApi);
  private readonly all = signal<readonly Publication[]>(PUBLICATIONS);

  async loadFromApi(): Promise<void> {
    try {
      const page = await this.api.list({ page: 1, size: 100 });
      const persisted = page.items.map(mapSummaryToPublication);
      this.all.set([...persisted, ...PUBLICATIONS]);
    } catch {
      // Conserve les données existantes si l'API est indisponible.
    }
  }

  /** Filtres actifs. Un ensemble vide ne filtre rien. */
  readonly selectedNetworks = signal<ReadonlySet<SocialNetworkCode>>(new Set());
  readonly selectedFormats = signal<ReadonlySet<PublicationFormat>>(new Set());
  readonly selectedStatuses = signal<ReadonlySet<PublicationStatus>>(new Set());
  readonly selectedEventTypes = signal<ReadonlySet<EventTypeFilter>>(new Set());
  readonly searchTerm = signal('');
  readonly sort = signal<PublicationSort>('recent');
  readonly showWithdrawn = signal(false);

  /** Toutes les publications, filtres ignorés. */
  readonly everything = this.all.asReadonly();

  /** Publications répondant aux filtres, triées. */
  readonly results = computed<readonly Publication[]>(() => {
    const networks = this.selectedNetworks();
    const formats = this.selectedFormats();
    const statuses = this.selectedStatuses();
    const eventTypes = this.selectedEventTypes();
    const term = this.searchTerm().trim().toLowerCase();
    const showWithdrawn = this.showWithdrawn();

    const kept = this.all().filter((publication) => {
      if (!showWithdrawn && publication.status === 'withdrawn') return false;
      if (networks.size && !publication.networks.some((code) => networks.has(code))) return false;
      if (formats.size && !formats.has(publication.format)) return false;
      if (statuses.size && !statuses.has(publication.status)) return false;
      if (eventTypes.size && !eventTypesOf(publication).some((type) => eventTypes.has(type))) {
        return false;
      }
      if (term && !this.matches(publication, term)) return false;
      return true;
    });

    return this.sorted(kept, this.sort());
  });

  readonly resultCount = computed(() => this.results().length);

  /** Vrai dès qu'un filtre est posé — sert à afficher « Réinitialiser ». */
  readonly hasActiveFilters = computed(
    () =>
      this.selectedNetworks().size > 0 ||
      this.selectedFormats().size > 0 ||
      this.selectedStatuses().size > 0 ||
      this.selectedEventTypes().size > 0 ||
      this.searchTerm().trim().length > 0 ||
      this.showWithdrawn(),
  );

  /** Nombre d'envois par réseau, tous filtres ignorés. */
  readonly deliveryCountByNetwork = computed(() => {
    const counts = new Map<SocialNetworkCode, number>();
    for (const publication of this.all()) {
      for (const code of publication.networks) {
        counts.set(code, (counts.get(code) ?? 0) + 1);
      }
    }
    return counts;
  });

  /** Nombre de publications par type, tous filtres ignorés. */
  readonly eventTypeCounts = computed(() => {
    const counts = new Map<EventTypeFilter, number>();
    for (const publication of this.all()) {
      for (const type of new Set(eventTypesOf(publication))) {
        counts.set(type, (counts.get(type) ?? 0) + 1);
      }
    }
    return counts;
  });

  /** Total des vues sur les publications effectivement parties. */
  readonly totalViewCount = computed(() =>
    this.all().reduce((total, publication) => total + publication.viewCount, 0),
  );

  readonly totalCommentCount = computed(() =>
    this.all().reduce((total, publication) => total + publication.commentCount, 0),
  );

  /** Nombre total d'envois : une publication sur trois réseaux en compte trois. */
  readonly totalDeliveryCount = computed(() =>
    this.all().reduce((total, publication) => total + publication.networks.length, 0),
  );

  /** Publications programmées, de la plus proche à la plus lointaine. */
  readonly upcoming = computed(() =>
    this.all()
      .filter((publication) => publication.scheduledAt !== null && publication.publishedAt === null)
      .sort((left, right) => left.scheduledAt!.localeCompare(right.scheduledAt!)),
  );

  findById(id: number): Publication | undefined {
    return this.all().find((publication) => publication.id === id);
  }

  toggleNetwork(code: SocialNetworkCode): void {
    this.selectedNetworks.update((current) => toggle(current, code));
  }

  toggleFormat(format: PublicationFormat): void {
    this.selectedFormats.update((current) => toggle(current, format));
  }

  toggleStatus(status: PublicationStatus): void {
    this.selectedStatuses.update((current) => toggle(current, status));
  }

  toggleEventType(type: EventTypeFilter): void {
    this.selectedEventTypes.update((current) => toggle(current, type));
  }

  resetFilters(): void {
    this.selectedNetworks.set(new Set());
    this.selectedEventTypes.set(new Set());
    this.selectedFormats.set(new Set());
    this.selectedStatuses.set(new Set());
    this.searchTerm.set('');
    this.showWithdrawn.set(false);
  }

  private matches(publication: Publication, term: string): boolean {
    return (
      publication.title.toLowerCase().includes(term) ||
      publication.caption.toLowerCase().includes(term) ||
      publication.authorName.toLowerCase().includes(term) ||
      publication.hashtags.some((hashtag) => hashtag.toLowerCase().includes(term))
    );
  }

  private sorted(publications: readonly Publication[], sort: PublicationSort): Publication[] {
    const copy = [...publications];
    switch (sort) {
      case 'views':
        return copy.sort((left, right) => right.viewCount - left.viewCount);
      case 'comments':
        return copy.sort((left, right) => right.commentCount - left.commentCount);
      default:
        // Une publication sans date tombe en fin de liste.
        return copy.sort((left, right) => dateKey(right).localeCompare(dateKey(left)));
    }
  }
}

/** Types portés par une publication ; sans lien, elle compte comme « none ». */
function eventTypesOf(publication: Publication): EventTypeFilter[] {
  const links = publication.eventLinks ?? [];
  return links.length ? links.map((link) => link.type) : ['none'];
}

/** Date de référence pour le tri chronologique. */
function dateKey(publication: Publication): string {
  return publication.publishedAt ?? publication.scheduledAt ?? '';
}

/** Ajoute ou retire une valeur, en renvoyant un nouvel ensemble. */
function toggle<T>(current: ReadonlySet<T>, value: T): ReadonlySet<T> {
  const next = new Set(current);
  if (!next.delete(value)) next.add(value);
  return next;
}

function mapSummaryToPublication(dto: PublicationSummaryDto): Publication {
  return {
    id: dto.id_publications,
    isPersisted: true,
    title: dto.title,
    caption: dto.caption,
    format: dto.format_code,
    status: dto.status_code,
    networks: dto.platform_codes as readonly SocialNetworkCode[],
    authorName: dto.author_name,
    scheduledAt: dto.scheduled_at,
    publishedAt: dto.published_at,
    viewCount: 0,
    reactionCount: 0,
    commentCount: dto.comment_count,
    hashtags: dto.hashtags,
    history: [],
    dailyStats: null,
  };
}
