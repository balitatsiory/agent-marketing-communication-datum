import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page, PageQuery } from './page';

export type WebinarStatusCode = 'draft' | 'scheduled' | 'past' | 'cancelled';
export type LinkMode = 'zoom_auto' | 'manual';
export type RegistrationMode = 'none' | 'zoom_page' | 'iagora_form' | 'external';
export type WebinarSort = 'date' | 'title' | 'registrations' | 'created';
export type SortDirection = 'asc' | 'desc';

export interface RefItem {
  readonly code: string;
  readonly label: string;
}

export interface WebinarReferenceDto {
  readonly statuses: readonly RefItem[];
  readonly types: readonly RefItem[];
  readonly categories: readonly RefItem[];
  readonly publication_types: readonly RefItem[];
  readonly platforms: readonly RefItem[];
}

export interface WebinarDto {
  readonly id_webinars: number;
  readonly title: string;
  readonly status_code: WebinarStatusCode;
  readonly status_label: string;
  readonly type_code: string;
  readonly type_label: string;
  readonly origin: 'manual' | 'zoom_sync' | 'site_import';
  readonly categories: readonly RefItem[];
  readonly id_zoom_accounts: number | null;
  readonly zoom_account_label: string | null;
  readonly external_zoom_meeting_id: number | null;
  readonly starts_at: string | null;
  readonly ends_at: string | null;
  readonly is_date_confirmed: boolean;
  readonly is_time_known: boolean;
  readonly published_on: string | null;
  readonly duration_minutes: number | null;
  readonly join_url: string | null;
  readonly registration_mode: RegistrationMode;
  readonly registration_url: string | null;
  readonly form_slug: string | null;
  readonly replay_url: string | null;
  readonly flyer_url: string | null;
  /** `null` : inscriptions inconnues (reprise du site). */
  readonly registration_count: number | null;
  readonly excerpt: string | null;
}

export interface MeetingSettings {
  readonly passcode: string | null;
  readonly waiting_room: boolean;
  readonly join_before_host: boolean;
  readonly mute_upon_entry: boolean;
  readonly host_video: boolean;
  readonly participant_video: boolean;
  readonly auto_recording: 'none' | 'local' | 'cloud';
  readonly email_notification: boolean;
}

/** Fiche lue par `GET /meetings/{meetingId}`, sans lien d'animation ni mot de passe. */
export interface ZoomMeetingDto {
  readonly id?: number;
  readonly uuid?: string;
  readonly host_email?: string;
  readonly topic?: string;
  readonly type?: number;
  readonly status?: string;
  readonly start_time?: string;
  readonly duration?: number;
  readonly timezone?: string;
  readonly created_at?: string;
  readonly join_url?: string;
  readonly registration_url?: string;
  readonly occurrence_count?: number;
  readonly settings?: Readonly<Record<string, string | number | boolean>>;
}

export interface RegistrationPageDto {
  readonly id_webinar_registration_pages: number;
  readonly kind: 'external' | 'iagora_form';
  readonly slug: string;
  readonly url: string | null;
  readonly is_active: boolean;
  readonly id_webinars: number | null;
  readonly webinar_title: string | null;
  readonly id_webinars_candidate: number | null;
  readonly candidate_title: string | null;
  readonly candidate_score: number | null;
  readonly event_starts_at: string | null;
  readonly event_ends_at: string | null;
  readonly note: string | null;
}

export interface PublicationLinkDto {
  readonly id_webinar_publication_links: number;
  readonly type_code: string;
  readonly type_label: string;
  readonly platform_code: string | null;
  readonly platform_label: string | null;
  readonly url: string;
  readonly label: string | null;
  readonly created_by_name: string | null;
  readonly created_at: string;
}

export interface PublicationLinkCreate {
  readonly type_code: string;
  readonly url: string;
  readonly platform_code: string | null;
  readonly label: string | null;
}

export interface DailyCount {
  readonly day: string;
  readonly count: number;
}

export interface WebinarDetailDto extends WebinarDto {
  readonly title_en: string | null;
  readonly description: string | null;
  readonly description_en: string | null;
  readonly timezone: string | null;
  readonly link_mode: LinkMode;
  readonly meeting_settings: MeetingSettings | null;
  readonly zoom_meeting: ZoomMeetingDto | null;
  readonly zoom_synced_at: string | null;
  readonly source_url: string | null;
  readonly flyer_source_url: string | null;
  readonly flyer_error: string | null;
  readonly anomalies: readonly string[];
  readonly date_hint: string | null;
  readonly registration_pages: readonly RegistrationPageDto[];
  readonly publication_links: readonly PublicationLinkDto[];
  readonly consented_count: number;
  readonly registration_series: readonly DailyCount[];
  readonly created_by_name: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface CountItem extends RefItem {
  readonly count: number;
}

export interface AccountStats {
  readonly id_zoom_accounts: number | null;
  readonly label: string;
  readonly total: number;
  readonly scheduled: number;
  readonly past: number;
  readonly draft: number;
}

export interface WebinarStatsDto {
  readonly total: number;
  readonly scheduled: number;
  readonly past: number;
  readonly draft: number;
  readonly cancelled: number;
  readonly by_type: readonly CountItem[];
  readonly by_category: readonly CountItem[];
  readonly by_month: readonly { readonly month: string; readonly count: number }[];
  readonly accounts: readonly AccountStats[];
  readonly registrations: number;
  readonly consented_registrations: number;
  readonly with_replay: number;
  readonly dates_to_confirm: number;
  readonly pending_flyers: number;
  readonly next_webinar: WebinarDto | null;
}

export interface WebinarFilters {
  readonly status?: string | null;
  readonly type?: string | null;
  readonly category?: string | null;
  readonly id_zoom_accounts?: number | null;
  readonly unassigned?: boolean;
  readonly q?: string | null;
}

export interface WebinarQuery extends WebinarFilters, PageQuery {
  readonly sort?: WebinarSort;
  readonly direction?: SortDirection;
}

/** Champs modifiables d'une fiche. */
export interface WebinarInput {
  readonly title?: string;
  readonly description?: string | null;
  readonly category_codes?: readonly string[];
  readonly starts_at?: string | null;
  readonly is_date_confirmed?: boolean;
  readonly duration_minutes?: number | null;
  readonly timezone?: string | null;
  readonly link_mode?: LinkMode;
  readonly id_zoom_accounts?: number | null;
  readonly join_url?: string | null;
  readonly registration_mode?: RegistrationMode;
  readonly registration_url?: string | null;
  readonly replay_url?: string | null;
  readonly meeting_settings?: MeetingSettings;
  readonly publication_links?: readonly PublicationLinkCreate[];
}

export interface ZoomSyncDto {
  readonly accounts: readonly {
    readonly id_zoom_accounts: number;
    readonly label: string;
    readonly ok: boolean;
    readonly message: string;
    readonly found: number;
    readonly created: number;
    readonly updated: number;
  }[];
}

export interface RegistrationDto {
  readonly id_webinar_registrations: number;
  readonly email: string | null;
  readonly first_name: string | null;
  readonly last_name: string | null;
  readonly source: 'iagora_form' | 'manual' | 'zoom_sync';
  readonly has_newsletter_consent: boolean;
  readonly registered_at: string;
  readonly zoom_status: string | null;
  readonly zoom_join_url: string | null;
  readonly zoom_error: string | null;
  readonly anonymized_at: string | null;
}

export interface RegistrationInput {
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly has_newsletter_consent: boolean;
}

export interface NewsletterAudienceDto {
  readonly id_webinars: number;
  readonly title: string;
  readonly items: readonly { readonly email: string; readonly display_name: string | null }[];
  readonly excluded_without_consent: number;
}

export interface PublicPageDto {
  readonly title: string;
  readonly description: string | null;
  readonly starts_at: string | null;
  readonly is_time_known: boolean;
  readonly duration_minutes: number | null;
  readonly flyer_url: string | null;
  readonly is_open: boolean;
}

export interface ImportReportDto {
  readonly webinars_created: number;
  readonly webinars_updated: number;
  readonly webinars_kept: number;
  readonly pages_created: number;
  readonly pages_updated: number;
  readonly dates_to_confirm: number;
  readonly pending_flyers: number;
  readonly warnings: readonly string[];
}

export interface FlyerBatchDto {
  readonly stored: number;
  readonly failed: number;
  readonly remaining: number;
  readonly errors: readonly {
    readonly id_webinars: number;
    readonly title: string;
    readonly message: string;
  }[];
}

/** Paramètres de requête : les valeurs vides ne sont pas envoyées. */
function parametres(source: object): HttpParams {
  let params = new HttpParams();
  for (const [nom, valeur] of Object.entries(source)) {
    if (valeur !== null && valeur !== undefined && valeur !== '' && valeur !== false) {
      params = params.set(nom, String(valeur));
    }
  }
  return params;
}

@Injectable({ providedIn: 'root' })
export class WebinarsApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/webinars`;
  private readonly publicBase = `${environment.apiBaseUrl}/public/registration-pages`;

  list(requete: WebinarQuery): Promise<Page<WebinarDto>> {
    return firstValueFrom(
      this.http.get<Page<WebinarDto>>(this.base, { params: parametres(requete) }),
    );
  }

  stats(filtres: WebinarFilters): Promise<WebinarStatsDto> {
    return firstValueFrom(
      this.http.get<WebinarStatsDto>(`${this.base}/stats`, { params: parametres(filtres) }),
    );
  }

  reference(): Promise<WebinarReferenceDto> {
    return firstValueFrom(this.http.get<WebinarReferenceDto>(`${this.base}/reference`));
  }

  get(id: number): Promise<WebinarDetailDto> {
    return firstValueFrom(this.http.get<WebinarDetailDto>(`${this.base}/${id}`));
  }

  create(donnees: WebinarInput): Promise<WebinarDetailDto> {
    return firstValueFrom(this.http.post<WebinarDetailDto>(this.base, donnees));
  }

  update(id: number, donnees: WebinarInput): Promise<WebinarDetailDto> {
    return firstValueFrom(this.http.patch<WebinarDetailDto>(`${this.base}/${id}`, donnees));
  }

  archive(id: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/${id}`));
  }

  /** Valide un brouillon : crée la réunion Zoom si le lien est automatique. */
  schedule(id: number): Promise<WebinarDetailDto> {
    return firstValueFrom(this.http.post<WebinarDetailDto>(`${this.base}/${id}/schedule`, {}));
  }

  refreshFromZoom(id: number): Promise<WebinarDetailDto> {
    return firstValueFrom(
      this.http.post<WebinarDetailDto>(`${this.base}/${id}/refresh-from-zoom`, {}),
    );
  }

  syncZoom(idZoomAccounts: number | null): Promise<ZoomSyncDto> {
    return firstValueFrom(
      this.http.post<ZoomSyncDto>(`${this.base}/zoom-sync`, {
        id_zoom_accounts: idZoomAccounts,
      }),
    );
  }

  importMeeting(idZoomAccounts: number, meetingId: string): Promise<WebinarDetailDto> {
    return firstValueFrom(
      this.http.post<WebinarDetailDto>(`${this.base}/zoom-meetings`, {
        id_zoom_accounts: idZoomAccounts,
        meeting_id: meetingId,
      }),
    );
  }

  importFiles(webinaires: File, pages: File | null, flyers: File | null): Promise<ImportReportDto> {
    const formulaire = new FormData();
    formulaire.set('webinars_file', webinaires);
    if (pages) formulaire.set('pages_file', pages);
    if (flyers) formulaire.set('flyers_file', flyers);
    return firstValueFrom(this.http.post<ImportReportDto>(`${this.base}/imports`, formulaire));
  }

  fetchFlyers(limit: number, retryFailed = false): Promise<FlyerBatchDto> {
    return firstValueFrom(
      this.http.post<FlyerBatchDto>(
        `${this.base}/flyers/fetch`,
        {},
        { params: parametres({ limit, retry_failed: retryFailed }) },
      ),
    );
  }

  registrationPages(): Promise<readonly RegistrationPageDto[]> {
    return firstValueFrom(
      this.http.get<RegistrationPageDto[]>(`${this.base}/registration-pages`),
    );
  }

  linkPage(idPage: number, idWebinars: number | null): Promise<RegistrationPageDto> {
    return firstValueFrom(
      this.http.patch<RegistrationPageDto>(`${this.base}/registration-pages/${idPage}`, {
        id_webinars: idWebinars,
      }),
    );
  }

  addPublicationLink(
    id: number,
    lien: PublicationLinkCreate,
  ): Promise<readonly PublicationLinkDto[]> {
    return firstValueFrom(
      this.http.post<PublicationLinkDto[]>(`${this.base}/${id}/publication-links`, lien),
    );
  }

  removePublicationLink(id: number, idLink: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/${id}/publication-links/${idLink}`));
  }

  registrations(id: number, page: number, size: number): Promise<Page<RegistrationDto>> {
    return firstValueFrom(
      this.http.get<Page<RegistrationDto>>(`${this.base}/${id}/registrations`, {
        params: parametres({ page, size }),
      }),
    );
  }

  /** Tous les inscrits en CSV, quelle que soit la page affichée. */
  exportRegistrations(id: number): Promise<Blob> {
    return firstValueFrom(
      this.http.get(`${this.base}/${id}/registrations/export`, { responseType: 'blob' }),
    );
  }

  addRegistration(id: number, inscription: RegistrationInput): Promise<RegistrationDto> {
    return firstValueFrom(
      this.http.post<RegistrationDto>(`${this.base}/${id}/registrations`, inscription),
    );
  }

  syncRegistrants(
    id: number,
  ): Promise<{ readonly found: number; readonly created: number; readonly updated: number }> {
    return firstValueFrom(
      this.http.post<{ found: number; created: number; updated: number }>(
        `${this.base}/${id}/registrations/zoom-sync`,
        {},
      ),
    );
  }

  setConsent(id: number, idRegistration: number, accord: boolean): Promise<RegistrationDto> {
    return firstValueFrom(
      this.http.patch<RegistrationDto>(`${this.base}/${id}/registrations/${idRegistration}`, {
        has_newsletter_consent: accord,
      }),
    );
  }

  pushToZoom(id: number, idRegistration: number): Promise<RegistrationDto> {
    return firstValueFrom(
      this.http.post<RegistrationDto>(
        `${this.base}/${id}/registrations/${idRegistration}/push-to-zoom`,
        {},
      ),
    );
  }

  anonymize(id: number, idRegistration: number): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.base}/${id}/registrations/${idRegistration}`),
    );
  }

  audience(id: number): Promise<NewsletterAudienceDto> {
    return firstValueFrom(
      this.http.get<NewsletterAudienceDto>(`${this.base}/${id}/newsletter-audience`),
    );
  }

  publicPage(slug: string): Promise<PublicPageDto> {
    return firstValueFrom(
      this.http.get<PublicPageDto>(`${this.publicBase}/${encodeURIComponent(slug)}`),
    );
  }

  registerPublic(
    slug: string,
    inscription: RegistrationInput & { readonly website: string },
  ): Promise<{ readonly message: string }> {
    return firstValueFrom(
      this.http.post<{ message: string }>(
        `${this.publicBase}/${encodeURIComponent(slug)}/registrations`,
        inscription,
      ),
    );
  }
}
