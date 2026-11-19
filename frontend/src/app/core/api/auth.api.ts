import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

/** Couple de jetons renvoyé par la connexion et le renouvellement. */
export interface TokenPair {
  readonly access_token: string;
  readonly refresh_token: string;
  readonly token_type: string;
  readonly expires_in: number;
}

/**
 * Profil courant, tel que `GET /auth/me` le renvoie.
 *
 * Volontairement distinct du modèle `User` de la maquette : celui-ci porte des
 * champs que le backend ne connaît pas (SSO Google, double authentification,
 * statut « invitation envoyée »). Les mélanger masquerait l'écart au lieu de
 * le rendre visible.
 */
export interface Me {
  readonly id_users: number;
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly permissions: readonly string[];
}

@Injectable({ providedIn: 'root' })
export class AuthApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/auth`;

  login(email: string, password: string): Promise<TokenPair> {
    return firstValueFrom(
      this.http.post<TokenPair>(`${this.base}/login`, { email, password }),
    );
  }

  /** N'est jamais interceptée : voir `authInterceptor`, qui l'ignore. */
  refresh(refreshToken: string): Promise<TokenPair> {
    return firstValueFrom(
      this.http.post<TokenPair>(`${this.base}/refresh`, { refresh_token: refreshToken }),
    );
  }

  logout(refreshToken: string): Promise<void> {
    return firstValueFrom(
      this.http.post<void>(`${this.base}/logout`, { refresh_token: refreshToken }),
    );
  }

  me(): Promise<Me> {
    return firstValueFrom(this.http.get<Me>(`${this.base}/me`));
  }

  changePassword(currentPassword: string, newPassword: string): Promise<void> {
    return firstValueFrom(
      this.http.patch<void>(`${this.base}/me/password`, {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    );
  }
}
