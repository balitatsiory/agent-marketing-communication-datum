/**
 * Catégories de courriels liés aux événements.
 *
 * Elles classent à la fois les modèles et les envois : un envoi hérite
 * de la catégorie du modèle qui l'a produit.
 */
export type MailCategory =
  | 'registrationConfirmation'
  | 'reminder'
  | 'changeOrCancellation'
  | 'report'
  | 'replay';

export const MAIL_CATEGORY_LABELS: Readonly<Record<MailCategory, string>> = {
  registrationConfirmation: "Confirmation d'inscription",
  reminder: 'Rappel',
  changeOrCancellation: 'Modification ou annulation',
  report: 'Compte rendu',
  replay: 'Visionnage',
};

/** Ce que chaque catégorie sert à dire — affiché sous son titre. */
export const MAIL_CATEGORY_NOTES: Readonly<Record<MailCategory, string>> = {
  registrationConfirmation: "Envoyé à la minute où quelqu'un s'inscrit.",
  reminder: 'Programmé à J-7, J-1 et H-2 avant la séance.',
  changeOrCancellation: "Déclenché à la main : c'est une mauvaise nouvelle, elle se relit.",
  report: 'Envoyé dans les 48 h, avec les points clés de la séance.',
  replay: 'Envoyé dès la mise en ligne de la rediffusion.',
};

/** Ordre d'affichage des catégories — celui du cycle de vie d'un événement. */
export const MAIL_CATEGORY_ORDER: readonly MailCategory[] = [
  'registrationConfirmation',
  'reminder',
  'changeOrCancellation',
  'report',
  'replay',
];

/* ============================================================
   Contenu d'un courriel
   ============================================================ */

/**
 * Signature électronique apposée au pied de chaque envoi.
 *
 * Elle atteste que le message vient bien de l'espace Datum Academy et
 * qu'il a été validé par l'équipe communication. Les valeurs sont
 * illustratives : la signature réelle sera produite côté serveur.
 */
export interface ElectronicSignature {
  readonly signedBy: string;
  readonly organisation: string;
  readonly signedAt: string;
  /** Empreinte abrégée du certificat, telle qu'affichée au destinataire. */
  readonly fingerprint: string;
}

/** Une ligne du tableau récapitulatif inséré dans le corps du message. */
export interface MailDetail {
  readonly label: string;
  readonly value: string;
}

/** Bouton d'action principal du courriel. */
export interface MailAction {
  readonly label: string;
  readonly url: string;
}

/**
 * Corps d'un courriel, tel qu'il sera rendu.
 *
 * Les variables s'écrivent `{{prenom}}` : elles restent visibles dans
 * l'aperçu d'un modèle, et sont remplacées dans un envoi.
 */
export interface MailContent {
  readonly subject: string;
  /** Première ligne visible dans la liste de la boîte de réception. */
  readonly preheader: string;
  readonly greeting: string;
  readonly paragraphs: readonly string[];
  readonly details: readonly MailDetail[];
  readonly action: MailAction | null;
  readonly closing: string;
  readonly signature: ElectronicSignature;
}

/* ============================================================
   Modèles
   ============================================================ */

/** Une version enregistrée d'un modèle. */
export interface TemplateVersion {
  readonly label: string;
  readonly createdAt: string;
  readonly authorName: string;
  /** Ce que cette version a changé. */
  readonly change: string;
  /** Version actuellement servie aux envois. */
  readonly isCurrent: boolean;
}

export type TemplateStatus = 'published' | 'draft';

/** Un modèle de courriel personnalisable. */
export interface MailTemplate {
  readonly id: number;
  readonly name: string;
  readonly category: MailCategory;
  readonly status: TemplateStatus;
  readonly updatedAt: string;
  readonly authorName: string;
  /** Nombre d'envois produits par ce modèle. */
  readonly usageCount: number;
  /** Variables attendues par le modèle, sans les accolades. */
  readonly variables: readonly string[];
  readonly versions: readonly TemplateVersion[];
  readonly content: MailContent;
}

/* ============================================================
   Envois
   ============================================================ */

export type SendStatus = 'sent' | 'scheduled' | 'partial' | 'failed';

export const SEND_STATUS_LABELS: Readonly<Record<SendStatus, string>> = {
  sent: 'Envoyé',
  scheduled: 'Programmé',
  partial: 'Envoyé en partie',
  failed: 'Échec',
};

/** Classe d'apparence de la pastille, voir `styles/_components.scss`. */
export function sendStatusModifier(status: SendStatus): string {
  switch (status) {
    case 'sent':
      return 'status-published';
    case 'scheduled':
      return 'status-scheduled';
    case 'failed':
    case 'partial':
      return 'status-failed';
    default:
      return 'status-draft';
  }
}

/** Un envoi effectué — ou programmé — depuis un modèle. */
export interface NewsletterSend {
  readonly id: number;
  readonly category: MailCategory;
  readonly subject: string;
  /** Événement auquel l'envoi se rattache. */
  readonly eventTitle: string;
  readonly templateName: string;
  readonly templateVersion: string;
  readonly sentAtLabel: string;
  readonly status: SendStatus;
  readonly recipientCount: number;
  /**
   * Messages effectivement remis.
   *
   * C'est tout ce que rend un serveur d'envoi : parti, remis, rejeté.
   * Ouvertures et clics ne transitent pas par SMTP — ils demandent un
   * pixel de suivi et une réécriture des liens, donc une infrastructure
   * à part. Tant qu'elle n'existe pas, l'écran n'affiche que ce qu'il
   * peut réellement savoir.
   */
  readonly deliveredCount: number;
  /** Renseigné quand l'envoi a échoué, en tout ou partie. */
  readonly failureNote: string | null;
  readonly content: MailContent;
}

/**
 * Vrai quand l'envoi a réellement été tenté.
 *
 * Un envoi programmé n'est pas encore parti ; un envoi en échec a été
 * interrompu avant d'atteindre le serveur d'envoi. Dans les deux cas,
 * l'écart entre destinataires et messages remis ne mesure pas des rejets
 * et ne doit pas être compté comme tel.
 */
export function wasAttempted(send: NewsletterSend): boolean {
  return send.status === 'sent' || send.status === 'partial';
}

/** Messages rejetés par le serveur destinataire. */
export function bounceCount(send: NewsletterSend): number {
  if (!wasAttempted(send)) return 0;
  return Math.max(0, send.recipientCount - send.deliveredCount);
}

/** Taux de remise sur les destinataires visés, en pourcentage entier. */
export function deliveryRate(send: NewsletterSend): number {
  if (!wasAttempted(send) || send.recipientCount === 0) return 0;
  return Math.round((send.deliveredCount / send.recipientCount) * 100);
}
