import { PublicationFormat } from './publication';
import { SocialNetworkCode } from './social-network';

/** Ton demandé au modèle pour la rédaction. */
export type GenerationTone = 'inspiring' | 'direct' | 'funny' | 'professional';

export const GENERATION_TONE_LABELS: Readonly<Record<GenerationTone, string>> = {
  inspiring: 'Inspirant',
  direct: 'Direct',
  funny: 'Drôle',
  professional: 'Pro',
};

/** Ce que l'utilisateur fournit avant de lancer une génération. */
export interface GenerationBrief {
  subject: string;
  context: string;
  tone: GenerationTone;
  format: PublicationFormat;
  networks: ReadonlySet<SocialNetworkCode>;
  language: string;
  includeHashtags: boolean;
}

/** Un visuel produit par la génération. */
export interface GeneratedVisual {
  /** Chemin servi depuis `public/`. */
  readonly source: string;
  /** Rapport d'image, pour réserver la place avant chargement. */
  readonly ratio: '4 / 5' | '1 / 1' | '9 / 16';
  /** Dimensions affichées sous la vignette. */
  readonly dimensions: string;
  readonly alt: string;
}

/** Une des trois propositions renvoyées par le modèle. */
export interface GenerationProposal {
  readonly id: number;
  readonly title: string;
  /** Angle rédactionnel, affiché en capitales à côté du titre. */
  readonly angle: string;
  /** Légende découpée en paragraphes, comme elle partira sur le réseau. */
  readonly paragraphs: readonly string[];
  readonly hashtags: readonly string[];
  /** Hashtags proposés en plus de ceux affichés. */
  readonly extraHashtagCount: number;
  readonly visual: GeneratedVisual;
}

/** Nombre de caractères de la légende, hashtags exclus. */
export function captionLength(proposal: GenerationProposal): number {
  return proposal.paragraphs.join(' ').length;
}

/** Une version du visuel dans la pop-up de retouche. */
export interface VisualVersion {
  readonly label: string;
  readonly visual: GeneratedVisual;
  /** Ce que cette version a changé par rapport à la précédente. */
  readonly change: string | null;
}

/** Qui parle dans la conversation de retouche. */
export type RetouchAuthor = 'system' | 'user' | 'assistant';

/** Un tour de la conversation de retouche. */
export interface RetouchMessage {
  readonly author: RetouchAuthor;
  readonly text: string;
  /** Actions proposées sous une réponse du modèle. */
  readonly actions?: readonly string[];
}
