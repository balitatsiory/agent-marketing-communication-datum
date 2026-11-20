import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface PlatformMetricDto {
  readonly code: string;
  readonly label: string;
  readonly nature: string;
  readonly is_summable: boolean;
  readonly platform_metric_name: string;
}

export interface SocialPlatformDto {
  readonly id_social_platforms: number;
  readonly code: string;
  readonly label: string;
  readonly is_enabled: boolean;
  readonly api_version: string | null;
  readonly max_description_length: number | null;
  readonly supports_event_polling: boolean;
  readonly supports_account_metrics: boolean;
  readonly allows_automated_message_reply: boolean;
  readonly message_response_window_hours: number | null;
  readonly sort_order: number;
  readonly supported_metrics: readonly PlatformMetricDto[];
}

export interface SocialAccountStatusDto {
  readonly code: string;
  readonly label: string;
  readonly sort_order: number;
}

export interface SocialAccountErrorCauseDto {
  readonly code: string;
  readonly label: string;
  readonly recommended_action: string;
}

export interface SocialAccountMetricsSummaryDto {
  readonly followers: number | null;
  readonly reach: number | null;
  readonly views_30d: number | null;
  readonly interactions_30d: number | null;
  readonly last_metric_date: string | null;
  readonly last_collected_at: string | null;
  readonly posts_30d: number;
}

export interface SocialAccountDto {
  readonly id_social_accounts: number;
  readonly platform_code: string;
  readonly platform_label: string;
  readonly status_code: string;
  readonly status_label: string;
  readonly id_social_accounts_parent: number | null;
  readonly parent_display_name: string | null;
  readonly parent_platform_code: string | null;
  readonly account_external_id: string;
  readonly account_display_name: string;
  readonly account_username: string | null;
  readonly profile_url: string | null;
  readonly credential_mode: 'own' | 'inherited';
  readonly error_cause: SocialAccountErrorCauseDto | null;
  readonly current_error_message: string | null;
  readonly has_active_token: boolean;
  readonly token_kind: string | null;
  readonly token_expires_at: string | null;
  readonly metrics: SocialAccountMetricsSummaryDto;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface SocialAccountCreate {
  readonly platform_code: string;
  readonly account_display_name: string;
  readonly account_username?: string | null;
  readonly account_external_id: string;
  readonly profile_url?: string | null;
  readonly credential_mode: 'own' | 'inherited';
  readonly id_social_accounts_parent?: number | null;
  readonly access_token?: string | null;
  readonly refresh_token?: string | null;
  readonly token_kind?: string | null;
  readonly obtained_at?: string | null;
  readonly access_expires_at?: string | null;
}

export interface SocialAccountReconnect {
  readonly access_token: string;
  readonly refresh_token?: string | null;
  readonly token_kind?: string | null;
  readonly obtained_at?: string | null;
  readonly access_expires_at?: string | null;
}

export interface SocialAccountVerifyDto {
  readonly verified: boolean;
  readonly message: string;
  readonly platform_name: string | null;
  readonly platform_username: string | null;
  readonly platform_url: string | null;
  readonly granted_permissions: readonly string[] | null;
  readonly missing_permissions: readonly string[];
  readonly raw_error: string | null;
  readonly account: SocialAccountDto;
}

export interface SocialStatisticTypeDto {
  readonly code: string;
  readonly label: string;
  readonly description: string | null;
  readonly nature: string;
  readonly is_summable: boolean;
  readonly supported_by_platform: boolean;
  readonly platform_metric_name: string | null;
}

export interface StatisticPointDto {
  readonly metric_date: string;
  readonly collected_at: string;
  readonly value: number;
}

export interface SocialAccountStatisticsDto {
  readonly days: number;
  readonly metric_types: readonly SocialStatisticTypeDto[];
  readonly series: Readonly<Record<string, readonly StatisticPointDto[]>>;
}

export interface SocialAccountSyncStatsDto {
  readonly ok: boolean;
  readonly synced_days: number;
  readonly message: string;
  readonly raw_error: string | null;
  readonly account: SocialAccountDto;
}

export interface SocialAccountTokenDto {
  readonly id_social_account_tokens: number;
  readonly token_kind: string | null;
  readonly obtained_at: string;
  readonly access_expires_at: string | null;
  readonly superseded_at: string | null;
  readonly revoked_at: string | null;
  readonly granted_permissions: readonly string[];
  readonly created_by_name: string | null;
  readonly is_active: boolean;
}

export interface SocialAccountSyncDto {
  readonly id_social_account_syncs: number;
  readonly sync_kind: string;
  readonly started_at: string;
  readonly finished_at: string | null;
  readonly sync_outcome: string | null;
  readonly covered_until_date: string | null;
  readonly error_cause_code: string | null;
  readonly error_cause_label: string | null;
  readonly retry_after: string | null;
  readonly triggered_by_name: string | null;
}

export interface SocialPostDto {
  readonly id_social_posts: number;
  readonly post_external_id: string;
  readonly permalink: string | null;
  readonly published_at: string | null;
  readonly archived_on_platform_at: string | null;
  readonly archived_by_name: string | null;
  readonly deleted_on_platform_at: string | null;
  readonly created_at: string;
}

export interface SocialAccountSyncPostsDto {
  readonly ok: boolean;
  readonly imported_count: number;
  readonly total_fetched: number;
  readonly message: string;
  readonly raw_error: string | null;
  readonly posts: readonly SocialPostDto[];
}

@Injectable({ providedIn: 'root' })
export class SocialAccountsApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  platforms(): Promise<readonly SocialPlatformDto[]> {
    return firstValueFrom(this.http.get<SocialPlatformDto[]>(`${this.base}/social-platforms`));
  }

  statuses(): Promise<readonly SocialAccountStatusDto[]> {
    return firstValueFrom(
      this.http.get<SocialAccountStatusDto[]>(`${this.base}/social-account-statuses`),
    );
  }

  list(): Promise<readonly SocialAccountDto[]> {
    return firstValueFrom(this.http.get<SocialAccountDto[]>(`${this.base}/social-accounts`));
  }

  create(donnees: SocialAccountCreate): Promise<SocialAccountDto> {
    return firstValueFrom(
      this.http.post<SocialAccountDto>(`${this.base}/social-accounts`, donnees),
    );
  }

  reconnect(idCompte: number, donnees: SocialAccountReconnect): Promise<SocialAccountDto> {
    return firstValueFrom(
      this.http.post<SocialAccountDto>(
        `${this.base}/social-accounts/${idCompte}/reconnect`,
        donnees,
      ),
    );
  }

  verify(idCompte: number): Promise<SocialAccountVerifyDto> {
    return firstValueFrom(
      this.http.post<SocialAccountVerifyDto>(
        `${this.base}/social-accounts/${idCompte}/verify`,
        {},
      ),
    );
  }

  disconnect(idCompte: number): Promise<SocialAccountDto> {
    return firstValueFrom(
      this.http.post<SocialAccountDto>(`${this.base}/social-accounts/${idCompte}/disconnect`, {}),
    );
  }

  get(idCompte: number): Promise<SocialAccountDto> {
    return firstValueFrom(
      this.http.get<SocialAccountDto>(`${this.base}/social-accounts/${idCompte}`),
    );
  }

  statistics(idCompte: number, days = 30): Promise<SocialAccountStatisticsDto> {
    return firstValueFrom(
      this.http.get<SocialAccountStatisticsDto>(
        `${this.base}/social-accounts/${idCompte}/statistics`,
        { params: { days: String(days) } },
      ),
    );
  }

  syncStatistics(idCompte: number): Promise<SocialAccountSyncStatsDto> {
    return firstValueFrom(
      this.http.post<SocialAccountSyncStatsDto>(
        `${this.base}/social-accounts/${idCompte}/sync-statistics`,
        {},
      ),
    );
  }

  tokens(idCompte: number): Promise<readonly SocialAccountTokenDto[]> {
    return firstValueFrom(
      this.http.get<SocialAccountTokenDto[]>(`${this.base}/social-accounts/${idCompte}/tokens`),
    );
  }

  syncs(idCompte: number): Promise<readonly SocialAccountSyncDto[]> {
    return firstValueFrom(
      this.http.get<SocialAccountSyncDto[]>(`${this.base}/social-accounts/${idCompte}/syncs`),
    );
  }

  posts(idCompte: number): Promise<readonly SocialPostDto[]> {
    return firstValueFrom(
      this.http.get<SocialPostDto[]>(`${this.base}/social-accounts/${idCompte}/posts`),
    );
  }

  syncPosts(idCompte: number): Promise<SocialAccountSyncPostsDto> {
    return firstValueFrom(
      this.http.post<SocialAccountSyncPostsDto>(
        `${this.base}/social-accounts/${idCompte}/sync-posts`,
        {},
      ),
    );
  }

  archivePost(idCompte: number, idPost: number): Promise<SocialPostDto> {
    return firstValueFrom(
      this.http.post<SocialPostDto>(
        `${this.base}/social-accounts/${idCompte}/posts/${idPost}/archive`,
        {},
      ),
    );
  }
}
