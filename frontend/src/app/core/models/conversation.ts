import { SocialNetworkCode } from './social-network';

/** Nature de l'échange, telle que la filtre la colonne de gauche. */
export type ConversationChannel = 'directMessage' | 'comment' | 'mention';

export const CONVERSATION_CHANNEL_LABELS: Readonly<Record<ConversationChannel, string>> = {
  directMessage: 'Messages privés',
  comment: 'Commentaires',
  mention: 'Mentions',
};

/** Libellé au singulier, pour la ligne de métadonnées d'une conversation. */
export const CONVERSATION_CHANNEL_SHORT: Readonly<Record<ConversationChannel, string>> = {
  directMessage: 'Message privé',
  comment: 'Commentaire',
  mention: 'Mention',
};

/**
 * Pastille d'état d'une conversation.
 *
 * `ai` et `late` portent une couleur ; `priority` un simple trait appuyé ;
 * `neutral` sert aux mentions libres, sans traitement particulier.
 */
export type ConversationFlagTone = 'ai' | 'late' | 'priority' | 'neutral';

export interface ConversationFlag {
  readonly label: string;
  readonly tone: ConversationFlagTone;
}

/** Un message reçu dans le fil. */
export interface ConversationMessage {
  readonly text: string;
  /** Horodatage affiché, p. ex. « Aujourd'hui 08 h 51 ». */
  readonly at: string;
}

/** Brouillon de réponse préparé par l'agent, en attente de validation humaine. */
export interface AssistantDraft {
  readonly paragraphs: readonly string[];
  /** Retouches proposées sous le brouillon. */
  readonly quickActions: readonly string[];
}

/** Une conversation de la file unifiée. */
export interface Conversation {
  readonly id: number;
  readonly authorName: string;
  /** Initiales affichées dans la pastille, faute de photo. */
  readonly initials: string;
  readonly network: SocialNetworkCode;
  readonly channel: ConversationChannel;
  /** Ancienneté affichée dans la liste, p. ex. « 22 min ». */
  readonly age: string;
  /** Précision affichée sous le nom dans l'en-tête du fil. */
  readonly origin: string;
  /** Faux tant que personne n'a ouvert la conversation. */
  readonly isRead: boolean;
  readonly messages: readonly ConversationMessage[];
  readonly draft: AssistantDraft | null;
  readonly flag: ConversationFlag;
  /**
   * La plateforme n'accepte plus de réponse depuis une application tierce.
   *
   * Meta ferme la fenêtre 24 h après le dernier message reçu : l'écran doit
   * le dire et renvoyer vers la plateforme plutôt que laisser croire à un
   * envoi possible.
   */
  readonly isReplyWindowClosed: boolean;
  /** Lien de repli vers la plateforme, quand la fenêtre est fermée. */
  readonly platformInboxUrl?: string;
}

/** Extrait affiché dans la liste : le dernier message reçu. */
export function conversationExcerpt(conversation: Conversation): string {
  return conversation.messages[conversation.messages.length - 1]?.text ?? '';
}
