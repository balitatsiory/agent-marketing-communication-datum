import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page, PageQuery } from './page';

export type NotificationSourceScope = 'internal' | 'platform';

export type NotificationTypeCode =
  | 'validation_request'
  | 'correction_suggested'
  | 'publication_approved'
  | 'publication_published'
  | 'publication_failed'
  | 'message_reply'
  | 'account_alert'
  | 'webinar_reminder'
  | 'team_activity';

export interface NotificationDto {
  readonly id_notifications: number;
  readonly id_users_recipient: number;
  readonly id_users_actor: number | null;
  readonly actor_name: string | null;
  readonly actor_initials: string | null;
  readonly notification_type: NotificationTypeCode;
  readonly notification_type_label: string;
  readonly source_scope: NotificationSourceScope;
  readonly platform_code: string | null;
  readonly title: string;
  readonly body: string;
  readonly requires_action: boolean;
  readonly action_label: string | null;
  readonly action_url: string | null;
  readonly entity_type: string | null;
  readonly entity_id: number | null;
  readonly is_read: boolean;
  readonly read_at: string | null;
  readonly created_at: string;
}

export interface NotificationStatsDto {
  readonly total: number;
  readonly unread: number;
  readonly action_required: number;
  readonly internal_count: number;
  readonly platform_count: number;
  readonly by_type: Readonly<Record<string, number>>;
  readonly by_platform: Readonly<Record<string, number>>;
  readonly pending_actions: readonly NotificationDto[];
}

export interface NotificationQuery extends PageQuery {
  readonly q?: string | null;
  readonly source?: NotificationSourceScope | null;
  readonly types?: readonly string[];
  readonly platforms?: readonly string[];
  readonly unread_only?: boolean;
  readonly requires_action?: boolean;
}

@Injectable({ providedIn: 'root' })
export class NotificationsApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/notifications`;

  list(query: NotificationQuery = {}): Promise<Page<NotificationDto>> {
    let params = new HttpParams();
    if (query.page) params = params.set('page', String(query.page));
    if (query.size) params = params.set('size', String(query.size));
    if (query.q?.trim()) params = params.set('q', query.q.trim());
    if (query.source) params = params.set('source', query.source);
    if (query.unread_only) params = params.set('unread_only', 'true');
    if (query.requires_action) params = params.set('requires_action', 'true');
    for (const t of query.types ?? []) {
      params = params.append('type', t);
    }
    for (const p of query.platforms ?? []) {
      params = params.append('platform', p);
    }
    return firstValueFrom(this.http.get<Page<NotificationDto>>(this.base, { params }));
  }

  stats(): Promise<NotificationStatsDto> {
    return firstValueFrom(this.http.get<NotificationStatsDto>(`${this.base}/stats`));
  }

  markRead(id: number): Promise<NotificationDto> {
    return firstValueFrom(this.http.post<NotificationDto>(`${this.base}/${id}/read`, {}));
  }

  markUnread(id: number): Promise<NotificationDto> {
    return firstValueFrom(this.http.post<NotificationDto>(`${this.base}/${id}/unread`, {}));
  }

  markAllRead(): Promise<{ readonly updated: number }> {
    return firstValueFrom(this.http.post<{ updated: number }>(`${this.base}/read-all`, {}));
  }

  delete(id: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/${id}`));
  }
}
