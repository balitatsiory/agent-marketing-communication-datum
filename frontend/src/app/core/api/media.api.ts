import { HttpClient, HttpEventType, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { filter, firstValueFrom, map, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Page, PageQuery } from './page';

/**
 * Média de la bibliothèque tel que l'API le renvoie.
 *
 * `url` est recomposée par l'API à la lecture : la clé de stockage ne quitte
 * jamais le backend.
 */
export interface MediaDto {
  readonly id_media: number;
  readonly display_name: string;
  readonly file_type: string;
  readonly source: string;
  readonly size_bytes: number;
  readonly width: number | null;
  readonly height: number | null;
  readonly video_duration_seconds: number | null;
  readonly created_at: string;
  readonly deleted_at: string | null;
  readonly url: string;
}

export interface MediaRename {
  readonly display_name: string;
}

/** Nature d'un média de référence, telle que `GET /media-reference-natures` la renvoie. */
export interface MediaReferenceNatureDto {
  readonly code: string;
  readonly label: string;
  readonly description: string | null;
  readonly sort_order: number;
}

/** Média déclaré comme référence pour la génération d'images. */
export interface MediaReferenceDto {
  readonly id_media_references: number;
  readonly id_media: number;
  readonly nature_code: string;
  readonly label: string;
  readonly description: string | null;
  readonly is_active: boolean;
  readonly created_at: string;
  readonly deleted_at: string | null;
}

export interface MediaReferenceCreate {
  readonly id_media: number;
  readonly nature_code: string;
  readonly label: string;
  readonly description?: string | null;
}

export interface MediaReferenceUpdate {
  readonly nature_code?: string;
  readonly label?: string;
  readonly description?: string | null;
  readonly is_active?: boolean;
}

@Injectable({ providedIn: 'root' })
export class MediaApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  /**
   * Dépose un fichier dans la bibliothèque.
   *
   * Aucun en-tête `Content-Type` n'est posé à la main : le navigateur doit le
   * composer lui-même avec la frontière multipart.
   */
  upload(
    fichier: File,
    displayName?: string,
    onProgress?: (pourcentage: number) => void,
  ): Promise<MediaDto> {
    const formulaire = new FormData();
    formulaire.append('fichier', fichier);
    if (displayName && displayName.trim().length > 0) {
      formulaire.append('display_name', displayName.trim());
    }

    if (!onProgress) {
      return firstValueFrom(this.http.post<MediaDto>(`${this.base}/media`, formulaire));
    }

    return firstValueFrom(
      this.http
        .post<MediaDto>(`${this.base}/media`, formulaire, {
          reportProgress: true,
          observe: 'events',
        })
        .pipe(
          tap((evenement) => {
            if (evenement.type === HttpEventType.UploadProgress && evenement.total) {
              onProgress(Math.round((100 * evenement.loaded) / evenement.total));
            }
          }),
          filter(
            (evenement): evenement is HttpResponse<MediaDto> =>
              evenement.type === HttpEventType.Response,
          ),
          map((reponse) => reponse.body as MediaDto),
        ),
    );
  }

  list(query: PageQuery = {}, includeArchived = false): Promise<Page<MediaDto>> {
    const params: Record<string, string> = {
      page: String(query.page ?? 1),
      size: String(query.size ?? 50),
    };
    if (includeArchived) params['include_archived'] = 'true';
    return firstValueFrom(this.http.get<Page<MediaDto>>(`${this.base}/media`, { params }));
  }

  get(idMedia: number): Promise<MediaDto> {
    return firstValueFrom(this.http.get<MediaDto>(`${this.base}/media/${idMedia}`));
  }

  rename(idMedia: number, displayName: string): Promise<MediaDto> {
    const donnees: MediaRename = { display_name: displayName };
    return firstValueFrom(
      this.http.patch<MediaDto>(`${this.base}/media/${idMedia}`, donnees),
    );
  }

  archive(idMedia: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/media/${idMedia}`));
  }

  purge(idMedia: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/media/${idMedia}/purge`));
  }

  natures(): Promise<readonly MediaReferenceNatureDto[]> {
    return firstValueFrom(
      this.http.get<MediaReferenceNatureDto[]>(`${this.base}/media-reference-natures`),
    );
  }

  createReference(donnees: MediaReferenceCreate): Promise<MediaReferenceDto> {
    return firstValueFrom(
      this.http.post<MediaReferenceDto>(`${this.base}/media-references`, donnees),
    );
  }

  listReferences(query: PageQuery = {}, includeArchived = false): Promise<Page<MediaReferenceDto>> {
    const params: Record<string, string> = {
      page: String(query.page ?? 1),
      size: String(query.size ?? 50),
    };
    if (includeArchived) params['include_archived'] = 'true';
    return firstValueFrom(
      this.http.get<Page<MediaReferenceDto>>(`${this.base}/media-references`, { params }),
    );
  }

  updateReference(idReference: number, donnees: MediaReferenceUpdate): Promise<MediaReferenceDto> {
    return firstValueFrom(
      this.http.patch<MediaReferenceDto>(`${this.base}/media-references/${idReference}`, donnees),
    );
  }

  archiveReference(idReference: number): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.base}/media-references/${idReference}`),
    );
  }
}
