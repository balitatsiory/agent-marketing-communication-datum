import { Injectable, inject, signal } from '@angular/core';
import { NotificationsApi, NotificationStatsDto } from '../api/notifications.api';

/**
 * État léger partagé pour le compteur de notifications non lues (barre latérale)
 * et le rafraîchissement après une action de validation.
 */
@Injectable({ providedIn: 'root' })
export class NotificationBadgeStore {
  private readonly api = inject(NotificationsApi);

  readonly unreadCount = signal<number>(0);
  readonly stats = signal<NotificationStatsDto | null>(null);

  async refresh(): Promise<void> {
    try {
      const data = await this.api.stats();
      this.stats.set(data);
      this.unreadCount.set(data.unread);
    } catch {
      // Silencieux : le compteur ne doit pas bloquer la navigation.
    }
  }

  setFromStats(data: NotificationStatsDto): void {
    this.stats.set(data);
    this.unreadCount.set(data.unread);
  }
}
