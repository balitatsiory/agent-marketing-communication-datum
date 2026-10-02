import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { SocialNetwork } from '../../../core/models/social-network';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/** Filtres de la barre de pastilles. */
type NetworkFilter = 'all' | 'connected' | 'toReconnect';

const FILTER_LABELS: Readonly<Record<NetworkFilter, string>> = {
  all: 'Tous',
  connected: 'Connectés',
  toReconnect: 'À reconnecter',
};

/**
 * Réseaux & plateformes — maquette 6b.
 *
 * Un réseau par bloc : identité à gauche, trois chiffres au centre,
 * actions à droite. Les chiffres retenus — publications, abonnés, vues
 * du profil — sont ceux que les API de plateforme rendent directement.
 * Un taux d'engagement supposerait la portée de chaque publication, que
 * tous les réseaux n'exposent pas de la même façon.
 */
@Component({
  selector: 'app-network-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DecimalPipe, Topbar, Icon, NetworkLogo],
  templateUrl: './network-list.html',
  styleUrl: './network-list.scss',
})
export class NetworkList {
  protected readonly filterLabels = FILTER_LABELS;
  protected readonly filters: readonly NetworkFilter[] = ['all', 'connected', 'toReconnect'];

  private readonly all = signal<readonly SocialNetwork[]>(SOCIAL_NETWORKS);

  protected readonly filter = signal<NetworkFilter>('all');

  protected readonly counts = computed(() => {
    const networks = this.all();
    return {
      all: networks.length,
      connected: networks.filter((network) => network.isConnected).length,
      toReconnect: networks.filter((network) => !network.isConnected).length,
    };
  });

  protected readonly results = computed<readonly SocialNetwork[]>(() => {
    switch (this.filter()) {
      case 'connected':
        return this.all().filter((network) => network.isConnected);
      case 'toReconnect':
        return this.all().filter((network) => !network.isConnected);
      default:
        return this.all();
    }
  });

  /** Cumuls affichés en tête, sur les seuls comptes raccordés. */
  protected readonly totals = computed(() => {
    const connected = this.all().filter((network) => network.isConnected);
    return {
      publications: connected.reduce((sum, network) => sum + network.publicationCount, 0),
      followers: connected.reduce((sum, network) => sum + network.followerCount, 0),
      profileViews: connected.reduce((sum, network) => sum + network.profileViewCount, 0),
    };
  });

  /** Nom d'hôte de l'adresse, affiché sous le bouton. */
  protected hostOf(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  }
}
