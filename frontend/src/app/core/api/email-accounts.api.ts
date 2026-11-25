import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

/**
 * Comptes d'envoi SMTP, tels que l'API les renvoie.
 *
 * Aucun champ ne porte le mot de passe : le backend ne le renvoie jamais, même
 * chiffré. `has_password` dit qu'un mot de passe est enregistré, et
 * `password_masked` ne sert qu'à l'afficher.
 */
export type EmailAccountSecurity = 'ssl_tls' | 'starttls';
export type EmailAccountCheckKind = 'connection' | 'test_message';

export interface EmailAccountDto {
  readonly id_email_accounts: number;
  readonly label: string;
  readonly host: string;
  readonly port: number;
  readonly security: EmailAccountSecurity;
  readonly username: string;
  readonly from_email: string;
  readonly from_name: string | null;
  readonly reply_to_email: string | null;
  readonly timeout_seconds: number;
  readonly is_default: boolean;
  readonly has_password: boolean;
  readonly password_masked: string | null;
  readonly password_obtained_at: string | null;
  readonly last_verified_at: string | null;
  readonly last_verify_ok: boolean | null;
  readonly last_verify_message: string | null;
  readonly created_by_name: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface EmailAccountCreate {
  readonly label: string;
  readonly host: string;
  readonly port: number;
  readonly security: EmailAccountSecurity;
  readonly username: string;
  readonly password: string;
  readonly from_email: string;
  readonly from_name?: string | null;
  readonly reply_to_email?: string | null;
  readonly timeout_seconds?: number;
  readonly is_default?: boolean;
  readonly verify_immediately?: boolean;
}

export interface EmailAccountUpdate {
  readonly label?: string;
  readonly host?: string;
  readonly port?: number;
  readonly security?: EmailAccountSecurity;
  readonly username?: string;
  readonly from_email?: string;
  readonly from_name?: string | null;
  readonly reply_to_email?: string | null;
  readonly timeout_seconds?: number;
}

/**
 * Résultat d'un échange réel avec le serveur SMTP.
 *
 * `verified` à faux n'est pas une erreur HTTP : un mot de passe refusé par
 * IONOS arrive en 200 et se lit dans `message`.
 */
export interface EmailAccountVerifyDto {
  readonly verified: boolean;
  readonly message: string;
  readonly latency_ms: number;
  readonly account: EmailAccountDto;
}

export interface EmailAccountCheckDto {
  readonly id_email_account_checks: number;
  readonly kind: EmailAccountCheckKind;
  readonly is_ok: boolean;
  readonly message: string | null;
  readonly recipient_email: string | null;
  readonly latency_ms: number | null;
  readonly checked_at: string;
  readonly checked_by_name: string | null;
}

@Injectable({ providedIn: 'root' })
export class EmailAccountsApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/email-accounts`;

  list(): Promise<readonly EmailAccountDto[]> {
    return firstValueFrom(this.http.get<EmailAccountDto[]>(this.base));
  }

  /** Le compte qui expédiera, ou `null` si aucun n'est configuré. */
  default(): Promise<EmailAccountDto | null> {
    return firstValueFrom(this.http.get<EmailAccountDto | null>(`${this.base}/default`));
  }

  create(donnees: EmailAccountCreate): Promise<EmailAccountVerifyDto> {
    return firstValueFrom(this.http.post<EmailAccountVerifyDto>(this.base, donnees));
  }

  update(id: number, donnees: EmailAccountUpdate): Promise<EmailAccountDto> {
    return firstValueFrom(this.http.patch<EmailAccountDto>(`${this.base}/${id}`, donnees));
  }

  /** Remplace le mot de passe : le précédent est daté, pas écrasé. */
  setPassword(id: number, password: string, verifyImmediately = true): Promise<EmailAccountVerifyDto> {
    return firstValueFrom(
      this.http.post<EmailAccountVerifyDto>(`${this.base}/${id}/password`, {
        password,
        verify_immediately: verifyImmediately,
      }),
    );
  }

  /** Connexion et authentification réelles. Aucun message n'est envoyé. */
  verify(id: number): Promise<EmailAccountVerifyDto> {
    return firstValueFrom(this.http.post<EmailAccountVerifyDto>(`${this.base}/${id}/verify`, {}));
  }

  sendTestMessage(
    id: number,
    recipientEmail: string,
    subject?: string,
    body?: string,
  ): Promise<EmailAccountVerifyDto> {
    return firstValueFrom(
      this.http.post<EmailAccountVerifyDto>(`${this.base}/${id}/test-message`, {
        recipient_email: recipientEmail,
        subject: subject ?? null,
        body: body ?? null,
      }),
    );
  }

  setDefault(id: number): Promise<EmailAccountDto> {
    return firstValueFrom(this.http.post<EmailAccountDto>(`${this.base}/${id}/default`, {}));
  }

  checks(id: number, limite = 20): Promise<readonly EmailAccountCheckDto[]> {
    const params = new HttpParams().set('limite', String(limite));
    return firstValueFrom(
      this.http.get<EmailAccountCheckDto[]>(`${this.base}/${id}/checks`, { params }),
    );
  }

  /** Archive le compte et révoque son mot de passe, dans la même transaction. */
  archive(id: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/${id}`));
  }
}
