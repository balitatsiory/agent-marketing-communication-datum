import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page, PageQuery } from './page';

/**
 * Utilisateur tel que l'API le renvoie.
 *
 * Les noms de champs sont ceux du backend, sans traduction : le jour où un
 * champ change, l'erreur de compilation tombe à l'endroit exact qui le lit.
 */
export interface UserDto {
  readonly id_users: number;
  readonly email: string;
  readonly first_name: string;
  readonly last_name: string;
  readonly is_active: boolean;
  readonly last_login_at: string | null;
  readonly created_at: string;
  readonly deleted_at: string | null;
  /** Codes des droits accordés, dans l'ordre d'affichage du référentiel. */
  readonly permissions: readonly string[];
}

/** Droit attribuable, tel que `GET /permissions` le renvoie. */
export interface PermissionDto {
  readonly code: string;
  readonly label: string;
  readonly description: string | null;
  readonly sort_order: number;
}

export interface UserCreate {
  readonly email: string;
  readonly password: string;
  readonly first_name: string;
  readonly last_name: string;
}

export interface UserUpdate {
  readonly email?: string;
  readonly first_name?: string;
  readonly last_name?: string;
  readonly is_active?: boolean;
}

@Injectable({ providedIn: 'root' })
export class UsersApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  list(query: PageQuery = {}, includeArchived = false): Promise<Page<UserDto>> {
    const params: Record<string, string> = {
      page: String(query.page ?? 1),
      size: String(query.size ?? 50),
    };
    if (includeArchived) params['include_archived'] = 'true';
    return firstValueFrom(this.http.get<Page<UserDto>>(`${this.base}/users`, { params }));
  }

  get(idUsers: number): Promise<UserDto> {
    return firstValueFrom(this.http.get<UserDto>(`${this.base}/users/${idUsers}`));
  }

  create(donnees: UserCreate): Promise<UserDto> {
    return firstValueFrom(this.http.post<UserDto>(`${this.base}/users`, donnees));
  }

  update(idUsers: number, donnees: UserUpdate): Promise<UserDto> {
    return firstValueFrom(
      this.http.patch<UserDto>(`${this.base}/users/${idUsers}`, donnees),
    );
  }

  setPassword(idUsers: number, password: string): Promise<void> {
    return firstValueFrom(
      this.http.patch<void>(`${this.base}/users/${idUsers}/password`, { password }),
    );
  }

  /** Archive le compte. Le backend révoque ses sessions dans la même transaction. */
  archive(idUsers: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/users/${idUsers}`));
  }

  permissions(): Promise<readonly PermissionDto[]> {
    return firstValueFrom(this.http.get<PermissionDto[]>(`${this.base}/permissions`));
  }

  /**
   * Remplace l'ENSEMBLE des droits de l'utilisateur.
   *
   * L'écran coche et décoche des cases puis enregistre un état : c'est ce que
   * PUT exprime. Les droits retirés sont archivés côté base, non supprimés.
   */
  setPermissions(idUsers: number, codes: readonly string[]): Promise<readonly string[]> {
    return firstValueFrom(
      this.http.put<string[]>(`${this.base}/users/${idUsers}/permissions`, { codes }),
    );
  }
}
