/**
 * Médias de référence : les fichiers que l'IA doit avoir sous les yeux
 * pour produire un visuel — logos, portraits, ambiances, gabarits.
 */

/**
 * Rôle d'un média dans la génération.
 *
 * Le rôle dit à l'IA ce qu'elle a le droit de faire du fichier : le
 * reprendre tel quel, s'en inspirer, ou en suivre la structure.
 */
export type MediaReferenceRole = 'asset' | 'style' | 'layout';

export const MEDIA_REFERENCE_ROLES: readonly MediaReferenceRole[] = ['asset', 'style', 'layout'];

export const MEDIA_REFERENCE_ROLE_LABELS: Readonly<Record<MediaReferenceRole, string>> = {
  asset: 'Actif',
  style: 'Style',
  layout: 'Gabarit',
};

/** Ce que le rôle implique, affiché sous chaque bouton radio. */
export const MEDIA_REFERENCE_ROLE_HINTS: Readonly<Record<MediaReferenceRole, string>> = {
  asset: "repris tel quel, sans réinterprétation (logo, photo d'intervenant)",
  style: "guide les couleurs et l'ambiance",
  layout: 'structure la mise en page',
};

/**
 * État de la description.
 *
 * `ai-proposal` : écrite par l'IA au dépôt, personne ne l'a encore relue.
 * `reviewed` : une personne l'a relue, modifiée ou non.
 */
export type MediaDescriptionStatus = 'ai-proposal' | 'reviewed';

export const MEDIA_DESCRIPTION_STATUS_LABELS: Readonly<Record<MediaDescriptionStatus, string>> = {
  'ai-proposal': 'Proposition IA — à relire',
  reviewed: 'Relue',
};

export interface MediaReference {
  readonly id: number;
  readonly fileName: string;
  readonly role: MediaReferenceRole;
  readonly description: string;
  readonly descriptionStatus: MediaDescriptionStatus;
  /** Une personne identifiable figure sur le média. */
  readonly depictsPerson: boolean;
  /** Consentement écrit, spécifique à l'usage IA. Sans objet si personne n'est représenté. */
  readonly consentCollected: boolean;
  /** Aperçu du fichier, quand il est disponible. `null` : vignette rayée. */
  readonly previewUrl: string | null;
}

/** Ce que la fenêtre Importer / Modifier renvoie à l'enregistrement. */
export interface MediaReferenceDraft {
  readonly role: MediaReferenceRole;
  readonly description: string;
  readonly depictsPerson: boolean;
  readonly consentCollected: boolean;
}
