import { toApiError } from '../api/api-error';
import {
  MediaDto,
  MediaReferenceDto,
  MediaReferenceNatureDto,
} from '../api/media.api';

/**
 * Vue d'un média de la bibliothèque, prête pour l'affichage.
 *
 * Isolée de `MediaDto` : si le contrat du backend change, l'erreur de
 * compilation tombe dans `toMediaView` et non dans les gabarits.
 */
export interface MediaView {
  readonly idMedia: number;
  readonly displayName: string;
  readonly fileType: string;
  readonly isImage: boolean;
  readonly isVideo: boolean;
  readonly source: string;
  readonly sizeBytes: number;
  readonly sizeLabel: string;
  readonly width: number | null;
  readonly height: number | null;
  readonly dimensionsLabel: string | null;
  readonly videoDurationSeconds: number | null;
  readonly createdAtLabel: string;
  readonly isArchived: boolean;
  readonly url: string;
}

/**
 * Nature d'un média de référence.
 *
 * **La liste des natures n'est pas recopiée dans le frontend.** Les versions
 * précédentes déclaraient trois rôles `asset | style | layout` et un statut
 * `ai-proposal | reviewed` qui n'existent pas en base. La table
 * `media_reference_natures` contient aujourd'hui cinq entrées (`logo`,
 * `personne`, `lieu`, `objet`, `fond`), alimentées par migration et appelées à
 * évoluer : les écrans les lisent donc par `GET /api/v1/media-reference-natures`,
 * comme ils lisent les droits par `GET /api/v1/permissions`.
 */
export interface MediaReferenceNature {
  readonly code: string;
  readonly label: string;
  readonly description: string | null;
  readonly sortOrder: number;
}

/**
 * Vue d'un média déclaré comme référence, enrichie du média de la bibliothèque
 * et du libellé de sa nature.
 */
export interface MediaReferenceView {
  readonly idMediaReferences: number;
  readonly idMedia: number;
  readonly natureCode: string;
  readonly natureLabel: string;
  readonly label: string;
  readonly description: string | null;
  readonly isActive: boolean;
  readonly isArchived: boolean;
  readonly createdAtLabel: string;
  readonly media: MediaView | null;
}

const DATE_COURTE = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'short',
});

export function formaterPoids(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
}

export function toMediaView(dto: MediaDto): MediaView {
  return {
    idMedia: dto.id_media,
    displayName: dto.display_name,
    fileType: dto.file_type,
    isImage: dto.file_type.startsWith('image/'),
    isVideo: dto.file_type.startsWith('video/'),
    source: dto.source,
    sizeBytes: dto.size_bytes,
    sizeLabel: formaterPoids(dto.size_bytes),
    width: dto.width,
    height: dto.height,
    dimensionsLabel:
      dto.width !== null && dto.height !== null ? `${dto.width} × ${dto.height} px` : null,
    videoDurationSeconds: dto.video_duration_seconds,
    createdAtLabel: DATE_COURTE.format(new Date(dto.created_at)),
    isArchived: dto.deleted_at !== null,
    url: dto.url,
  };
}

export function toMediaReferenceNature(dto: MediaReferenceNatureDto): MediaReferenceNature {
  return {
    code: dto.code,
    label: dto.label,
    description: dto.description,
    sortOrder: dto.sort_order,
  };
}

export function toMediaReferenceView(
  dto: MediaReferenceDto,
  mediasParId: ReadonlyMap<number, MediaView>,
  naturesParCode: ReadonlyMap<string, MediaReferenceNature>,
): MediaReferenceView {
  return {
    idMediaReferences: dto.id_media_references,
    idMedia: dto.id_media,
    natureCode: dto.nature_code,
    natureLabel: naturesParCode.get(dto.nature_code)?.label ?? dto.nature_code,
    label: dto.label,
    description: dto.description,
    isActive: dto.is_active,
    isArchived: dto.deleted_at !== null,
    createdAtLabel: DATE_COURTE.format(new Date(dto.created_at)),
    media: mediasParId.get(dto.id_media) ?? null,
  };
}

const MESSAGES_ERREUR_MEDIA: Readonly<Record<string, string>> = {
  unsupported_file_type:
    "Format de fichier non reconnu. Seules les images (PNG, JPEG, WebP, GIF) et les vidéos (MP4, WebM) sont acceptées.",
  file_too_large:
    'Ce fichier dépasse le poids maximal autorisé par le serveur.',
  image_too_large:
    "Les dimensions de cette image dépassent la définition maximale acceptée par le serveur.",
  image_not_compressible:
    "Cette image dépasse 8 Mo et n'a pas pu être suffisamment compressée pour passer sous le plafond.",
};

/**
 * Traduit les codes d'erreur stables du module Média en messages explicites
 * pour l'utilisateur.
 */
export function traduireErreurMedia(erreur: unknown): string {
  const apiErreur = toApiError(erreur);
  return MESSAGES_ERREUR_MEDIA[apiErreur.code] ?? apiErreur.message;
}
