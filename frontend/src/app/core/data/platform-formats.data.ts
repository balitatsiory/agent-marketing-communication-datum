import { PublicationFormat } from '../models/publication';
import { SocialNetworkCode } from '../models/social-network';

/**
 * Bornes de médias par format — table `formats` du modèle de données,
 * arrêtée le 13 octobre 2026.
 *
 * Les deux bornes vivent sur le format et non sur le couple réseau ×
 * format : un carrousel plafonne à dix médias sur tous les réseaux.
 * C'est la limite de l'API de publication d'Instagram ; aligner LinkedIn,
 * qui en accepterait vingt, évite une publication valide d'un côté et
 * refusée de l'autre.
 */
export interface FormatBounds {
  readonly minMediaCount: number;
  readonly maxMediaCount: number;
  /** Natures de fichier acceptées. Vide pour un format sans média. */
  readonly accepts: readonly MediaKind[];
  /** Contrainte affichée sous le nom du format. */
  readonly hint: string;
}

/** Nature d'un fichier importé. */
export type MediaKind = 'image' | 'video' | 'document';

export const FORMAT_BOUNDS: Readonly<Record<PublicationFormat, FormatBounds>> = {
  image: { minMediaCount: 1, maxMediaCount: 1, accepts: ['image'], hint: 'une image' },
  carousel: {
    minMediaCount: 2,
    maxMediaCount: 10,
    accepts: ['image', 'video'],
    hint: '2 à 10 médias',
  },
  reel: { minMediaCount: 1, maxMediaCount: 1, accepts: ['video'], hint: 'une vidéo verticale' },
  video: { minMediaCount: 1, maxMediaCount: 1, accepts: ['video'], hint: 'une vidéo' },
  story: { minMediaCount: 1, maxMediaCount: 1, accepts: ['image', 'video'], hint: '24 h' },
  document: { minMediaCount: 1, maxMediaCount: 1, accepts: ['document'], hint: 'un PDF' },
  text: { minMediaCount: 0, maxMediaCount: 0, accepts: [], hint: 'aucun média' },
};

/**
 * Table de liaison `platform_formats` : quels formats chaque réseau
 * accepte.
 *
 * Aucune clé étrangère ne pointe vers elle. Elle sert ici à griser les
 * réseaux incompatibles avec le format choisi, avant l'erreur — et non
 * à laisser l'utilisateur découvrir le refus à l'envoi.
 *
 * À remplacer par `GET /api/v1/platform-formats`.
 */
export const PLATFORM_FORMATS: Readonly<
  Record<SocialNetworkCode, readonly PublicationFormat[]>
> = {
  instagram: ['image', 'carousel', 'reel', 'story'],
  facebook: ['image', 'carousel', 'reel', 'video', 'story', 'text'],
  linkedin: ['image', 'carousel', 'video', 'document', 'text'],
  // Les publications photo de TikTok restent à confirmer auprès de la
  // documentation officielle : seule la vidéo est posée pour l'instant.
  tiktok: ['video'],
  youtube: ['video'],
};

/** `platforms.max_caption_length` — longueur maximale d'une légende. */
export const CAPTION_LIMITS: Readonly<Record<SocialNetworkCode, number>> = {
  instagram: 2200,
  facebook: 63206,
  linkedin: 3000,
  tiktok: 2200,
  youtube: 5000,
};

/** Ce réseau accepte-t-il ce format ? */
export function acceptsFormat(network: SocialNetworkCode, format: PublicationFormat): boolean {
  return PLATFORM_FORMATS[network].includes(format);
}
