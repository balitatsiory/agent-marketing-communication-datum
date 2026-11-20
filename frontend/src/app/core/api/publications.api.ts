import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface PublicationFormatDto {
  readonly code: string;
  readonly label: string;
  readonly min_media_count: number;
  readonly max_media_count: number;
  readonly is_enabled: boolean;
  readonly sort_order: number;
  readonly platforms: readonly string[];
}

export interface PublicationTargetCreate {
  readonly id_social_accounts: number;
  readonly description: string;
  readonly scheduled_at: string;
}

export interface PublicationCreate {
  readonly format_code: string;
  readonly media_ids: readonly number[];
  readonly targets: readonly PublicationTargetCreate[];
}

export interface PublicationMediaDto {
  readonly id_media: number;
  readonly carousel_position: number;
  readonly display_name: string;
  readonly file_type: string;
  readonly url: string;
}

export interface PublicationTargetDto {
  readonly id_publication_targets: number;
  readonly id_social_accounts: number;
  readonly account_display_name: string;
  readonly platform_code: string;
  readonly platform_label: string;
  readonly description: string | null;
  readonly scheduled_at: string;
  readonly delivery_status_code: string;
  readonly delivery_status_label: string;
  readonly id_social_posts: number | null;
  readonly post_external_id: string | null;
  readonly permalink: string | null;
  readonly last_error: string | null;
}

export interface PublicationHistoryDto {
  readonly event_code: string;
  readonly event_label: string;
  readonly status_code: string;
  readonly status_label: string;
  readonly changed_by_name: string | null;
  readonly comment: string | null;
  readonly created_at: string;
}

export interface PublicationDto {
  readonly id_publications: number;
  readonly format_code: string;
  readonly format_label: string;
  readonly status_code: string;
  readonly status_label: string;
  readonly created_by_name: string | null;
  readonly media: readonly PublicationMediaDto[];
  readonly targets: readonly PublicationTargetDto[];
  readonly history: readonly PublicationHistoryDto[];
  readonly created_at: string;
  readonly updated_at: string;
}

export interface PublicationPublishResultDto {
  readonly ok: boolean;
  readonly message: string;
  readonly published_count: number;
  readonly failed_count: number;
  readonly publication: PublicationDto;
}

@Injectable({ providedIn: 'root' })
export class PublicationsApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  formats(): Promise<readonly PublicationFormatDto[]> {
    return firstValueFrom(
      this.http.get<PublicationFormatDto[]>(`${this.base}/publication-formats`),
    );
  }

  list(): Promise<readonly PublicationDto[]> {
    return firstValueFrom(this.http.get<PublicationDto[]>(`${this.base}/publications`));
  }

  get(idPublication: number): Promise<PublicationDto> {
    return firstValueFrom(
      this.http.get<PublicationDto>(`${this.base}/publications/${idPublication}`),
    );
  }

  create(donnees: PublicationCreate): Promise<PublicationDto> {
    return firstValueFrom(
      this.http.post<PublicationDto>(`${this.base}/publications`, donnees),
    );
  }

  approve(idPublication: number, comment: string | null = null): Promise<PublicationDto> {
    return firstValueFrom(
      this.http.post<PublicationDto>(`${this.base}/publications/${idPublication}/approve`, {
        comment,
      }),
    );
  }

  requestCorrection(idPublication: number, comment: string | null = null): Promise<PublicationDto> {
    return firstValueFrom(
      this.http.post<PublicationDto>(
        `${this.base}/publications/${idPublication}/request-correction`,
        { comment },
      ),
    );
  }

  publish(idPublication: number): Promise<PublicationPublishResultDto> {
    return firstValueFrom(
      this.http.post<PublicationPublishResultDto>(
        `${this.base}/publications/${idPublication}/publish`,
        {},
      ),
    );
  }
}
