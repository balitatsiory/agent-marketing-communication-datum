import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

/**
 * Comptes Zoom (applications Server-to-Server OAuth).
 *
 * Ni le Client Secret ni le jeton d'accès ne reviennent de l'API : seules
 * leurs dates et les droits portés par le jeton sont connus ici.
 */
export interface ZoomScopeDto {
  readonly scope: string;
  readonly label: string;
  readonly is_granted: boolean;
}

export interface ZoomAccountDto {
  readonly id_zoom_accounts: number;
  readonly label: string;
  readonly host_email: string;
  readonly external_zoom_account_id: string;
  readonly client_id: string;
  readonly has_client_secret: boolean;
  readonly client_secret_masked: string | null;
  readonly client_secret_obtained_at: string | null;
  readonly token_obtained_at: string | null;
  readonly token_expires_at: string | null;
  readonly has_valid_token: boolean;
  readonly scopes: readonly ZoomScopeDto[];
  readonly granted_scopes: readonly string[];
  readonly last_verified_at: string | null;
  readonly last_verify_ok: boolean | null;
  readonly last_verify_message: string | null;
  readonly created_by_name: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface ZoomAccountCreate {
  readonly label: string;
  readonly host_email: string;
  readonly external_zoom_account_id: string;
  readonly client_id: string;
  readonly client_secret: string;
}

export type ZoomAccountUpdate = Partial<Omit<ZoomAccountCreate, 'client_secret'>>;

/** `verified` à faux n'est pas une erreur HTTP : le motif est dans `message`. */
export interface ZoomAccountVerifyDto {
  readonly verified: boolean;
  readonly message: string;
  readonly latency_ms: number;
  readonly account: ZoomAccountDto;
}

export interface ZoomAccountCheckDto {
  readonly id_zoom_account_checks: number;
  readonly kind: 'connection' | 'token_refresh';
  readonly is_ok: boolean;
  readonly message: string | null;
  readonly latency_ms: number | null;
  readonly checked_at: string;
  readonly checked_by_name: string | null;
}

@Injectable({ providedIn: 'root' })
export class ZoomAccountsApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/zoom-accounts`;

  list(): Promise<readonly ZoomAccountDto[]> {
    return firstValueFrom(this.http.get<ZoomAccountDto[]>(this.base));
  }

  create(donnees: ZoomAccountCreate): Promise<ZoomAccountVerifyDto> {
    return firstValueFrom(this.http.post<ZoomAccountVerifyDto>(this.base, donnees));
  }

  update(id: number, donnees: ZoomAccountUpdate): Promise<ZoomAccountDto> {
    return firstValueFrom(this.http.patch<ZoomAccountDto>(`${this.base}/${id}`, donnees));
  }

  replaceSecret(id: number, clientSecret: string): Promise<ZoomAccountVerifyDto> {
    return firstValueFrom(
      this.http.post<ZoomAccountVerifyDto>(`${this.base}/${id}/client-secret`, {
        client_secret: clientSecret,
      }),
    );
  }

  /** Jeton neuf puis lecture réelle des réunions de l'hôte. */
  verify(id: number): Promise<ZoomAccountVerifyDto> {
    return firstValueFrom(this.http.post<ZoomAccountVerifyDto>(`${this.base}/${id}/verify`, {}));
  }

  refreshToken(id: number): Promise<ZoomAccountVerifyDto> {
    return firstValueFrom(
      this.http.post<ZoomAccountVerifyDto>(`${this.base}/${id}/refresh-token`, {}),
    );
  }

  checks(id: number): Promise<readonly ZoomAccountCheckDto[]> {
    return firstValueFrom(this.http.get<ZoomAccountCheckDto[]>(`${this.base}/${id}/checks`));
  }

  archive(id: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/${id}`));
  }
}
