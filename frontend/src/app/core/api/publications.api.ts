import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { PublicationFormat, PublicationStatus } from '../models/publication';
import { Page, PageQuery } from './page';

export interface ValidatorOptionDto {
  readonly id_users: number;
  readonly full_name: string;
  readonly initials: string;
  readonly email: string;
  readonly is_self: boolean;
}

export interface PublicationEventDto {
  readonly id_publication_events: number;
  readonly id_publications: number;
  readonly kind: string;
  readonly label: string;
  readonly comment: string | null;
  readonly id_users_author: number | null;
  readonly author_name: string;
  readonly author_initials: string;
  readonly created_at: string;
}

export interface PublicationMediaItemDto {
  readonly name: string;
  readonly kind: string;
  readonly size_label?: string;
  readonly duration_label?: string | null;
}

export interface PublicationSummaryDto {
  readonly id_publications: number;
  readonly title: string;
  readonly caption: string;
  readonly format_code: PublicationFormat;
  readonly status_code: PublicationStatus;
  readonly platform_codes: readonly string[];
  readonly hashtags: readonly string[];
  readonly scheduled_at: string | null;
  readonly published_at: string | null;
  readonly id_users_author: number;
  readonly author_name: string;
  readonly author_initials: string;
  readonly id_users_validator: number | null;
  readonly validator_name: string | null;
  readonly comment_count: number;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface PublicationDetailDto extends PublicationSummaryDto {
  readonly captions_by_platform: Readonly<Record<string, string>> | null;
  readonly media_items: readonly PublicationMediaItemDto[] | null;
  readonly events: readonly PublicationEventDto[];
}

export interface PublicationCreateInput {
  readonly title: string;
  readonly caption: string;
  readonly captions_by_platform?: Readonly<Record<string, string>> | null;
  readonly format_code: PublicationFormat;
  readonly platform_codes: readonly string[];
  readonly hashtags?: readonly string[];
  readonly media_items?: readonly PublicationMediaItemDto[] | null;
  readonly scheduled_at?: string | null;
  readonly id_users_validator?: number | null;
  readonly submit_for_validation: boolean;
}

export interface PublicationUpdateInput {
  readonly title?: string;
  readonly caption?: string;
  readonly captions_by_platform?: Readonly<Record<string, string>> | null;
  readonly platform_codes?: readonly string[];
  readonly hashtags?: readonly string[];
  readonly scheduled_at?: string | null;
  readonly id_users_validator?: number | null;
}

@Injectable({ providedIn: 'root' })
export class PublicationsApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/publications`;

  validators(): Promise<readonly ValidatorOptionDto[]> {
    return firstValueFrom(this.http.get<ValidatorOptionDto[]>(`${this.base}/validators`));
  }

  list(query: PageQuery & { readonly status?: string | null } = {}): Promise<Page<PublicationSummaryDto>> {
    let params = new HttpParams();
    if (query.page) params = params.set('page', String(query.page));
    if (query.size) params = params.set('size', String(query.size));
    if (query.status) params = params.set('status', query.status);
    return firstValueFrom(this.http.get<Page<PublicationSummaryDto>>(this.base, { params }));
  }

  get(id: number): Promise<PublicationDetailDto> {
    return firstValueFrom(this.http.get<PublicationDetailDto>(`${this.base}/${id}`));
  }

  create(payload: PublicationCreateInput): Promise<PublicationDetailDto> {
    return firstValueFrom(this.http.post<PublicationDetailDto>(this.base, payload));
  }

  update(id: number, payload: PublicationUpdateInput): Promise<PublicationDetailDto> {
    return firstValueFrom(this.http.patch<PublicationDetailDto>(`${this.base}/${id}`, payload));
  }

  submit(
    id: number,
    payload: { readonly id_users_validator?: number | null; readonly comment?: string | null } = {},
  ): Promise<PublicationDetailDto> {
    return firstValueFrom(this.http.post<PublicationDetailDto>(`${this.base}/${id}/submit`, payload));
  }

  requestChanges(id: number, comment: string): Promise<PublicationDetailDto> {
    return firstValueFrom(
      this.http.post<PublicationDetailDto>(`${this.base}/${id}/request-changes`, { comment }),
    );
  }

  addComment(id: number, comment: string): Promise<PublicationDetailDto> {
    return firstValueFrom(
      this.http.post<PublicationDetailDto>(`${this.base}/${id}/comments`, { comment }),
    );
  }

  approve(
    id: number,
    payload: { readonly publish_now: boolean; readonly comment?: string | null },
  ): Promise<PublicationDetailDto> {
    return firstValueFrom(
      this.http.post<PublicationDetailDto>(`${this.base}/${id}/approve`, payload),
    );
  }
}
