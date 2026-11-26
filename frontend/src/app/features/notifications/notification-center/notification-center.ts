import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import {
  NotificationDto,
  NotificationsApi,
  NotificationSourceScope,
  NotificationStatsDto,
  NotificationTypeCode,
} from '../../../core/api/notifications.api';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { NotificationBadgeStore } from '../../../core/services/notification-badge-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

interface TypeFilterOption {
  readonly code: NotificationTypeCode;
  readonly label: string;
}

interface DayGroup {
  readonly label: string;
  readonly items: readonly NotificationDto[];
}

const KNOWN_NETWORKS = new Set<string>(SOCIAL_NETWORKS.map((n) => n.code));

@Component({
  selector: 'app-notification-center',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './notification-center.html',
  styleUrl: './notification-center.scss',
})
export class NotificationCenter implements OnInit {
  private readonly api = inject(NotificationsApi);
  private readonly badgeStore = inject(NotificationBadgeStore);
  private readonly router = inject(Router);

  protected readonly networks = SOCIAL_NETWORKS;

  protected readonly typeOptions: readonly TypeFilterOption[] = [
    { code: 'validation_request', label: 'Demandes de validation' },
    { code: 'correction_suggested', label: 'Corrections suggérées' },
    { code: 'publication_approved', label: 'Publications approuvées' },
    { code: 'publication_published', label: 'Publications publiées' },
    { code: 'publication_failed', label: 'Échecs de publication' },
    { code: 'message_reply', label: 'Messages & commentaires' },
    { code: 'account_alert', label: 'Alertes comptes' },
    { code: 'webinar_reminder', label: 'Rappels webinaires' },
    { code: 'team_activity', label: 'Activité équipe' },
  ];

  protected readonly items = signal<readonly NotificationDto[]>([]);
  protected readonly total = signal(0);
  protected readonly stats = signal<NotificationStatsDto | null>(null);
  protected readonly isLoading = signal(false);
  protected readonly errorMessage = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  /* ---------- filtres ---------- */
  protected readonly searchTerm = signal('');
  protected readonly selectedSource = signal<NotificationSourceScope | 'all'>('all');
  protected readonly selectedTypes = signal<ReadonlySet<NotificationTypeCode>>(new Set());
  protected readonly selectedPlatforms = signal<ReadonlySet<string>>(new Set());
  protected readonly unreadOnly = signal(false);
  protected readonly actionOnly = signal(false);

  protected readonly hasActiveFilters = computed(
    () =>
      this.searchTerm().trim().length > 0 ||
      this.selectedSource() !== 'all' ||
      this.selectedTypes().size > 0 ||
      this.selectedPlatforms().size > 0 ||
      this.unreadOnly() ||
      this.actionOnly(),
  );

  protected readonly groupedByDay = computed<readonly DayGroup[]>(() => {
    const groups = new Map<string, NotificationDto[]>();
    for (const item of this.items()) {
      const label = dayLabel(item.created_at);
      const list = groups.get(label) ?? [];
      list.push(item);
      groups.set(label, list);
    }
    return [...groups.entries()].map(([label, items]) => ({ label, items }));
  });

  ngOnInit(): void {
    void this.loadAll();
  }

  protected async loadAll(): Promise<void> {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      const [statsData, page] = await Promise.all([
        this.api.stats(),
        this.api.list(this.buildQuery()),
      ]);
      this.stats.set(statsData);
      this.badgeStore.setFromStats(statsData);
      this.items.set(page.items);
      this.total.set(page.total);
    } catch {
      this.errorMessage.set('Impossible de charger les notifications pour le moment.');
    } finally {
      this.isLoading.set(false);
    }
  }

  protected async reloadList(): Promise<void> {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    try {
      const page = await this.api.list(this.buildQuery());
      this.items.set(page.items);
      this.total.set(page.total);
    } catch {
      this.errorMessage.set('Impossible de filtrer les notifications.');
    } finally {
      this.isLoading.set(false);
    }
  }

  private buildQuery() {
    const source = this.selectedSource();
    return {
      page: 1,
      size: 50,
      q: this.searchTerm().trim() || null,
      source: source === 'all' ? null : source,
      types: [...this.selectedTypes()],
      platforms: [...this.selectedPlatforms()],
      unread_only: this.unreadOnly(),
      requires_action: this.actionOnly(),
    };
  }

  /* ---------- interactions filtres ---------- */

  protected setSource(source: NotificationSourceScope | 'all'): void {
    this.selectedSource.set(source);
    void this.reloadList();
  }

  protected toggleType(code: NotificationTypeCode): void {
    this.selectedTypes.update((current) => toggleSet(current, code));
    void this.reloadList();
  }

  protected togglePlatform(code: string): void {
    this.selectedPlatforms.update((current) => toggleSet(current, code));
    void this.reloadList();
  }

  protected toggleUnreadOnly(): void {
    this.unreadOnly.update((v) => !v);
    void this.reloadList();
  }

  protected toggleActionOnly(): void {
    this.actionOnly.update((v) => !v);
    void this.reloadList();
  }

  protected onSearchChange(value: string): void {
    this.searchTerm.set(value);
    void this.reloadList();
  }

  protected applyQuickChip(preset: 'all' | 'unread' | 'action' | 'internal' | 'platform'): void {
    this.selectedTypes.set(new Set());
    this.selectedPlatforms.set(new Set());
    this.unreadOnly.set(preset === 'unread');
    this.actionOnly.set(preset === 'action');
    this.selectedSource.set(
      preset === 'internal' ? 'internal' : preset === 'platform' ? 'platform' : 'all',
    );
    void this.reloadList();
  }

  protected resetFilters(): void {
    this.searchTerm.set('');
    this.selectedSource.set('all');
    this.selectedTypes.set(new Set());
    this.selectedPlatforms.set(new Set());
    this.unreadOnly.set(false);
    this.actionOnly.set(false);
    void this.reloadList();
  }

  protected typeCount(code: NotificationTypeCode): number {
    return this.stats()?.by_type[code] ?? 0;
  }

  protected platformCount(code: string): number {
    return this.stats()?.by_platform[code] ?? 0;
  }

  /* ---------- actions sur notifications ---------- */

  protected async openNotification(item: NotificationDto): Promise<void> {
    if (!item.is_read) {
      try {
        await this.api.markRead(item.id_notifications);
        await this.badgeStore.refresh();
      } catch {
        // On continue la navigation même si le marquage échoue.
      }
    }
    if (item.action_url) {
      await this.router.navigateByUrl(item.action_url);
    } else {
      await this.loadAll();
    }
  }

  protected async toggleRead(item: NotificationDto, event: Event): Promise<void> {
    event.stopPropagation();
    try {
      if (item.is_read) {
        await this.api.markUnread(item.id_notifications);
      } else {
        await this.api.markRead(item.id_notifications);
      }
      await this.loadAll();
    } catch {
      this.errorMessage.set('Impossible de mettre à jour le statut de lecture.');
    }
  }

  protected async markAllAsRead(): Promise<void> {
    try {
      const res = await this.api.markAllRead();
      if (res.updated > 0) {
        this.notice.set(
          `${res.updated} notification${res.updated > 1 ? 's marquées' : ' marquée'} comme lue.`,
        );
      }
      await this.loadAll();
    } catch {
      this.errorMessage.set('Impossible de tout marquer comme lu.');
    }
  }

  /* ---------- présentation ---------- */

  protected isSocialNetwork(code: string | null): code is SocialNetworkCode {
    return code !== null && KNOWN_NETWORKS.has(code);
  }

  protected markTone(item: NotificationDto): 'err' | 'accent' | 'ok' | '' {
    if (item.notification_type === 'publication_failed' || item.notification_type === 'account_alert') {
      return 'err';
    }
    if (
      item.notification_type === 'validation_request' ||
      item.notification_type === 'correction_suggested'
    ) {
      return 'accent';
    }
    if (
      item.notification_type === 'publication_approved' ||
      item.notification_type === 'publication_published'
    ) {
      return 'ok';
    }
    return '';
  }

  protected formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
}

function toggleSet<T>(current: ReadonlySet<T>, value: T): ReadonlySet<T> {
  const next = new Set(current);
  if (!next.delete(value)) next.add(value);
  return next;
}

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (sameDay(date, now)) return "Aujourd'hui";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return 'Hier';

  return date.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
  });
}
