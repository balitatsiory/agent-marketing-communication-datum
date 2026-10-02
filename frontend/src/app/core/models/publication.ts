import { SocialNetworkCode } from './social-network';

/**
 * Cycle de vie d'une publication, repris des filtres de la maquette 13b.
 *
 * `partiallyPublished` existe parce qu'une publication part sur plusieurs
 * réseaux à la fois : elle peut réussir sur l'un et échouer sur l'autre.
 */
export type PublicationStatus =
  | 'draft'
  | 'review'
  | 'approved'
  | 'scheduled'
  | 'published'
  | 'partiallyPublished'
  | 'failed'
  | 'withdrawn';

/** Format du média porté par la publication. */
export type PublicationFormat = 'reel' | 'video' | 'image' | 'carousel' | 'story';

/** Une publication, du brouillon jusqu'à son envoi sur les réseaux. */
export interface Publication {
  readonly id: number;
  readonly title: string;
  /** Légende complète, telle qu'elle part sur les réseaux. */
  readonly caption: string;
  readonly format: PublicationFormat;
  readonly status: PublicationStatus;
  /** Réseaux visés par cette publication. */
  readonly networks: readonly SocialNetworkCode[];
  readonly authorName: string;
  /** Date de programmation, en ISO 8601. Absente pour un brouillon. */
  readonly scheduledAt: string | null;
  /** Date d'envoi effectif, en ISO 8601. Absente tant que rien n'est parti. */
  readonly publishedAt: string | null;
  readonly viewCount: number;
  /** Mentions « j'aime » et partages cumulés sur les réseaux visés. */
  readonly reactionCount: number;
  readonly commentCount: number;
  readonly hashtags: readonly string[];
  /** Journal de la publication, du plus ancien au plus récent. */
  readonly history: readonly PublicationEvent[];
  /**
   * Relevés quotidiens des sept jours suivant le départ.
   *
   * `null` tant que rien n'est parti : il n'y a alors rien à mesurer, et
   * une série de zéros laisserait croire à un échec.
   */
  readonly dailyStats: readonly DailyStat[] | null;
}

/** Nature d'une étape du journal d'une publication. */
export type PublicationEventKind =
  | 'created'
  | 'submitted'
  | 'approved'
  | 'scheduled'
  | 'modified'
  | 'published'
  | 'failed'
  | 'withdrawn';

/**
 * Une étape du journal.
 *
 * NF-02 et S-07 : auteur, date et résultat conservés pour toute diffusion.
 * `authorName` vaut « IAGORA » quand l'étape est automatique.
 */
export interface PublicationEvent {
  readonly kind: PublicationEventKind;
  readonly label: string;
  readonly authorName: string;
  readonly authorInitials: string;
  readonly atLabel: string;
}

/** Vues et réactions d'un jour donné. */
export interface DailyStat {
  readonly dayLabel: string;
  readonly views: number;
  readonly reactions: number;
}

/** Libellés français des statuts — l'identifiant reste en anglais. */
export const PUBLICATION_STATUS_LABELS: Readonly<Record<PublicationStatus, string>> = {
  draft: 'Brouillon',
  review: 'À valider',
  approved: 'Approuvée',
  scheduled: 'Programmée',
  published: 'Publiée',
  partiallyPublished: 'Publiée en partie',
  failed: 'Échec',
  withdrawn: 'Retirée',
};

/** Libellés français des formats. */
export const PUBLICATION_FORMAT_LABELS: Readonly<Record<PublicationFormat, string>> = {
  reel: 'Reel',
  video: 'Vidéo',
  image: 'Image',
  carousel: 'Carrousel',
  story: 'Story',
};

/**
 * Classe CSS de la pastille de statut.
 *
 * Les huit statuts se ramènent aux cinq apparences définies dans
 * `styles/_components.scss` : inutile d'en dessiner huit.
 */
export function statusModifier(status: PublicationStatus): string {
  switch (status) {
    case 'published':
      return 'status-published';
    case 'scheduled':
    case 'approved':
      return 'status-scheduled';
    case 'review':
      return 'status-review';
    case 'failed':
    case 'partiallyPublished':
      return 'status-failed';
    default:
      return 'status-draft';
  }
}
