import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page, PageQuery } from './page';

/** Les noms de champs sont ceux du backend, sans traduction. */
export type MailTemplateStatus = 'draft' | 'published';

export interface MailCategoryDto {
  readonly code: string;
  readonly label: string;
  readonly note: string;
  readonly sort_order: number;
}

export interface SendStatusDto {
  readonly code: string;
  readonly label: string;
  readonly sort_order: number;
}

export interface MailTemplateDto {
  readonly id_mail_templates: number;
  readonly category_code: string;
  readonly category_label: string;
  readonly category_note: string;
  readonly name: string;
  readonly subject: string;
  readonly preheader: string | null;
  readonly body_html: string;
  readonly variables: readonly string[];
  readonly status: MailTemplateStatus;
  readonly version_label: string;
  readonly is_standard: boolean;
  readonly usage_count: number;
  readonly created_by_name: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface MailTemplateCreate {
  readonly category_code: string;
  readonly name: string;
  readonly subject: string;
  readonly preheader?: string | null;
  readonly body_html: string;
  readonly status?: MailTemplateStatus;
}

export interface MailTemplateUpdate {
  readonly category_code?: string;
  readonly name?: string;
  readonly subject?: string;
  readonly preheader?: string | null;
  readonly body_html?: string;
  readonly status?: MailTemplateStatus;
  readonly change_note?: string | null;
}

export interface MailTemplateVersionDto {
  readonly id_mail_template_versions: number;
  readonly label: string;
  readonly subject: string;
  readonly change_note: string | null;
  readonly author_name: string | null;
  readonly created_at: string;
}

export interface MailTemplatePreviewDto {
  readonly subject: string;
  readonly preheader: string;
  readonly html: string;
  readonly text: string;
  readonly variables: readonly string[];
  readonly missing_variables: readonly string[];
}

export interface NewsletterRecipientDto {
  readonly email: string;
  readonly display_name: string | null;
  readonly is_delivered: boolean;
  readonly error_message: string | null;
  readonly sent_at: string | null;
}

export interface NewsletterSendDto {
  readonly id_newsletter_sends: number;
  readonly category_code: string;
  readonly category_label: string;
  readonly status_code: string;
  readonly status_label: string;
  readonly subject: string;
  readonly event_title: string | null;
  readonly template_name: string;
  readonly template_version: string;
  readonly id_mail_templates: number | null;
  readonly id_email_accounts: number;
  readonly account_label: string;
  readonly account_from_email: string;
  readonly recipient_count: number;
  readonly delivered_count: number;
  readonly bounce_count: number;
  readonly delivery_rate: number;
  readonly failure_note: string | null;
  readonly scheduled_at: string | null;
  readonly sent_at: string | null;
  readonly created_by_name: string | null;
  readonly created_at: string;
}

export interface NewsletterSendDetailDto extends NewsletterSendDto {
  readonly recipients: readonly NewsletterRecipientDto[];
}

export interface NewsletterCountDto {
  readonly code: string;
  readonly label: string;
  readonly count: number;
}

export interface NewsletterStatsDto {
  readonly sends: number;
  readonly attempted: number;
  readonly targeted: number;
  readonly delivered: number;
  readonly bounced: number;
  readonly delivery_rate: number;
  readonly needing_attention: number;
  readonly by_category: readonly NewsletterCountDto[];
  readonly by_status: readonly NewsletterCountDto[];
  readonly computed_at: string;
}

export interface NewsletterSendCreate {
  readonly id_mail_templates: number;
  readonly id_email_accounts?: number | null;
  readonly event_title?: string | null;
  readonly recipients: readonly { email: string; display_name?: string | null }[];
  readonly variables?: Record<string, string>;
}

/** Filtres de la boîte d'envois. `id_email_accounts` vide = tous les comptes. */
export interface SendQuery extends PageQuery {
  readonly id_email_accounts?: number | null;
  readonly category_code?: string | null;
  readonly status_code?: string | null;
  readonly search?: string | null;
}

@Injectable({ providedIn: 'root' })
export class NewsletterApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/newsletter`;

  categories(): Promise<readonly MailCategoryDto[]> {
    return firstValueFrom(this.http.get<MailCategoryDto[]>(`${this.base}/categories`));
  }

  sendStatuses(): Promise<readonly SendStatusDto[]> {
    return firstValueFrom(this.http.get<SendStatusDto[]>(`${this.base}/send-statuses`));
  }

  // ---------------------------------------------------------------- modèles

  templates(query: PageQuery & { category_code?: string | null; status?: string | null; search?: string | null } = {}): Promise<Page<MailTemplateDto>> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('size', String(query.size ?? 50));
    if (query.category_code) params = params.set('category_code', query.category_code);
    if (query.status) params = params.set('status', query.status);
    if (query.search) params = params.set('search', query.search);
    return firstValueFrom(
      this.http.get<Page<MailTemplateDto>>(`${this.base}/mail-templates`, { params }),
    );
  }

  template(id: number): Promise<MailTemplateDto> {
    return firstValueFrom(this.http.get<MailTemplateDto>(`${this.base}/mail-templates/${id}`));
  }

  createTemplate(donnees: MailTemplateCreate): Promise<MailTemplateDto> {
    return firstValueFrom(
      this.http.post<MailTemplateDto>(`${this.base}/mail-templates`, donnees),
    );
  }

  updateTemplate(id: number, donnees: MailTemplateUpdate): Promise<MailTemplateDto> {
    return firstValueFrom(
      this.http.patch<MailTemplateDto>(`${this.base}/mail-templates/${id}`, donnees),
    );
  }

  archiveTemplate(id: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/mail-templates/${id}`));
  }

  /** Installe les cinq modèles standards. Sans effet sur ceux qui existent déjà. */
  installStandards(): Promise<readonly MailTemplateDto[]> {
    return firstValueFrom(
      this.http.post<MailTemplateDto[]>(`${this.base}/mail-templates/install-standards`, {}),
    );
  }

  versions(id: number): Promise<readonly MailTemplateVersionDto[]> {
    return firstValueFrom(
      this.http.get<MailTemplateVersionDto[]>(`${this.base}/mail-templates/${id}/versions`),
    );
  }

  preview(id: number, variables: Record<string, string> = {}): Promise<MailTemplatePreviewDto> {
    return firstValueFrom(
      this.http.post<MailTemplatePreviewDto>(`${this.base}/mail-templates/${id}/preview`, {
        variables,
      }),
    );
  }

  // ---------------------------------------------------------------- envois

  sends(query: SendQuery = {}): Promise<Page<NewsletterSendDto>> {
    let params = new HttpParams()
      .set('page', String(query.page ?? 1))
      .set('size', String(query.size ?? 20));
    if (query.id_email_accounts) {
      params = params.set('id_email_accounts', String(query.id_email_accounts));
    }
    if (query.category_code) params = params.set('category_code', query.category_code);
    if (query.status_code) params = params.set('status_code', query.status_code);
    if (query.search) params = params.set('search', query.search);
    return firstValueFrom(this.http.get<Page<NewsletterSendDto>>(`${this.base}/sends`, { params }));
  }

  send(id: number): Promise<NewsletterSendDetailDto> {
    return firstValueFrom(this.http.get<NewsletterSendDetailDto>(`${this.base}/sends/${id}`));
  }

  stats(idEmailAccounts?: number | null): Promise<NewsletterStatsDto> {
    let params = new HttpParams();
    if (idEmailAccounts) params = params.set('id_email_accounts', String(idEmailAccounts));
    return firstValueFrom(
      this.http.get<NewsletterStatsDto>(`${this.base}/sends/stats`, { params }),
    );
  }

  createSend(donnees: NewsletterSendCreate): Promise<NewsletterSendDetailDto> {
    return firstValueFrom(
      this.http.post<NewsletterSendDetailDto>(`${this.base}/sends`, donnees),
    );
  }
}
