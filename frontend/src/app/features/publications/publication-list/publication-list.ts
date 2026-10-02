import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import {
  PUBLICATION_FORMAT_LABELS,
  PUBLICATION_STATUS_LABELS,
  Publication,
  PublicationFormat,
  PublicationStatus,
} from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import {
  PUBLICATION_SORT_LABELS,
  PublicationSort,
  PublicationStore,
} from '../../../core/services/publication-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';
import { StatusBadge } from '../../../shared/status-badge/status-badge';
import { TimeBarChart } from '../../../shared/time-bar-chart/time-bar-chart';

/** Affichage des résultats : vignettes ou tableau. */
type ViewMode = 'grid' | 'list';

/** Publications — maquette 13b : filtres en colonne, grille de vignettes. */
@Component({
  selector: 'app-publication-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, RouterLink, Topbar, Icon, NetworkLogo, StatusBadge, TimeBarChart],
  templateUrl: './publication-list.html',
  styleUrl: './publication-list.scss',
})
export class PublicationList {
  protected readonly store = inject(PublicationStore);

  protected readonly networks = SOCIAL_NETWORKS;
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly statusLabels = PUBLICATION_STATUS_LABELS;
  protected readonly sortLabels = PUBLICATION_SORT_LABELS;

  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  /** « Retirée » a sa propre case, à part : elle ne filtre pas, elle révèle. */
  protected readonly statuses = (
    Object.keys(PUBLICATION_STATUS_LABELS) as PublicationStatus[]
  ).filter((status) => status !== 'withdrawn');

  protected readonly viewMode = signal<ViewMode>('grid');
  protected readonly openedPublication = signal<Publication | null>(null);

  /* ---------- synchronisation ---------- */

  protected readonly lastSyncLabel = signal("aujourd'hui, 08 h 40");
  protected readonly isSyncing = signal(false);
  protected readonly notice = signal<string | null>(null);

  /** Comptes dont le jeton a expiré : leurs chiffres ne bougeront pas. */
  protected readonly staleNetworks = computed(() =>
    this.networks.filter((network) => !network.isConnected),
  );

  /**
   * Synchronisation simulée.
   *
   * Le délai rend visible l'état d'attente, que l'écran doit savoir
   * afficher avant même que le backend existe.
   */
  protected synchronise(): void {
    if (this.isSyncing()) return;
    this.isSyncing.set(true);
    this.notice.set(null);
    setTimeout(() => {
      this.isSyncing.set(false);
      const stale = this.staleNetworks();
      this.lastSyncLabel.set('à l’instant');
      this.notice.set(
        stale.length
          ? `Chiffres relevés sur ${this.networks.length - stale.length} comptes. ${stale
              .map((network) => network.label)
              .join(', ')} reste à reconnecter — simulation, aucun appel réel.`
          : 'Chiffres relevés sur tous les comptes — simulation, aucun appel réel.',
      );
    }, 900);
  }

  /* ---------- filtres ---------- */

  protected readonly activeFilterLabels = computed(() => {
    const labels: string[] = [];
    for (const code of this.store.selectedNetworks()) {
      labels.push(this.networks.find((network) => network.code === code)?.label ?? code);
    }
    for (const format of this.store.selectedFormats()) labels.push(this.formatLabels[format]);
    for (const status of this.store.selectedStatuses()) labels.push(this.statusLabels[status]);
    return labels;
  });

  protected readonly sortOrder: readonly PublicationSort[] = ['recent', 'views', 'comments'];

  protected deliveriesFor(code: SocialNetworkCode): number {
    return this.store.deliveryCountByNetwork().get(code) ?? 0;
  }

  protected cycleSort(): void {
    const current = this.sortOrder.indexOf(this.store.sort());
    this.store.sort.set(this.sortOrder[(current + 1) % this.sortOrder.length]);
  }

  protected onSearch(value: string): void {
    this.store.searchTerm.set(value);
  }

  /* ---------- dates ---------- */

  protected displayDate(publication: Publication): string {
    const iso = publication.publishedAt ?? publication.scheduledAt;
    if (!iso) return 'Sans date';
    return new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
  }

  protected fullDate(publication: Publication): string {
    const iso = publication.publishedAt ?? publication.scheduledAt;
    if (!iso) return 'Aucune date de programmation';
    return new Date(iso).toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /** La même échéance en GMT — les plateformes raisonnent dans ce fuseau. */
  protected gmtDate(publication: Publication): string | null {
    const iso = publication.scheduledAt ?? publication.publishedAt;
    if (!iso) return null;
    const date = new Date(iso);
    return `${date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      timeZone: 'UTC',
    })} à ${date.toISOString().slice(11, 16)} GMT`;
  }

  /* ---------- détail ---------- */

  protected open(publication: Publication): void {
    this.openedPublication.set(publication);
    this.notice.set(null);
  }

  protected close(): void {
    this.openedPublication.set(null);
  }

  /** Vrai pour les statuts qui précèdent un départ. */
  protected isPending(publication: Publication): boolean {
    return (
      publication.status === 'scheduled' ||
      publication.status === 'approved' ||
      publication.status === 'review'
    );
  }

  protected isLive(publication: Publication): boolean {
    return publication.status === 'published' || publication.status === 'partiallyPublished';
  }

  /** Total des vues relevées jour par jour. */
  protected totalViews(publication: Publication): number {
    return (publication.dailyStats ?? []).reduce((sum, day) => sum + day.views, 0);
  }

  protected totalReactions(publication: Publication): number {
    return (publication.dailyStats ?? []).reduce((sum, day) => sum + day.reactions, 0);
  }

  /** Suppression simulée d'un brouillon. */
  protected deleteDraft(publication: Publication): void {
    this.close();
    this.notice.set(
      `Brouillon « ${publication.title} » supprimé — simulation, rien n'a été effacé.`,
    );
  }

  /** Confirmation simulée d'une publication programmée. */
  protected confirmPublication(publication: Publication): void {
    this.close();
    this.notice.set(
      `« ${publication.title} » confirmée pour le ${this.displayDate(publication)} — simulation, rien n'a été programmé.`,
    );
  }
}
