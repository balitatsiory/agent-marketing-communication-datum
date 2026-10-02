import { Injectable, computed, signal } from '@angular/core';
import { CONVERSATIONS } from '../data/conversations.data';
import { Conversation, ConversationChannel } from '../models/conversation';
import { SocialNetworkCode } from '../models/social-network';

/** Nombre de conversations affichées avant le bouton « voir les suivantes ». */
const INITIAL_PAGE_SIZE = 5;

/**
 * File unifiée : filtres, sélection, et pagination de la liste.
 *
 * Les filtres de canal et de plateforme sont indépendants et chacun à
 * choix unique — c'est le comportement de la maquette 10a, où chaque
 * colonne de filtres n'a qu'une ligne active.
 */
@Injectable({ providedIn: 'root' })
export class InboxStore {
  private readonly all = signal<readonly Conversation[]>(CONVERSATIONS);

  /** `null` vaut « Tous ». */
  readonly channelFilter = signal<ConversationChannel | null>(null);
  readonly networkFilter = signal<SocialNetworkCode | null>(null);
  readonly isListExpanded = signal(false);

  readonly everything = this.all.asReadonly();

  readonly results = computed<readonly Conversation[]>(() => {
    const channel = this.channelFilter();
    const network = this.networkFilter();
    return this.all().filter(
      (conversation) =>
        (channel === null || conversation.channel === channel) &&
        (network === null || conversation.network === network),
    );
  });

  /** Ce que la liste affiche réellement, pagination comprise. */
  readonly visible = computed(() =>
    this.isListExpanded() ? this.results() : this.results().slice(0, INITIAL_PAGE_SIZE),
  );

  readonly hiddenCount = computed(() => this.results().length - this.visible().length);

  /** Conversations dont la fenêtre de réponse de la plateforme est fermée. */
  readonly lateCount = computed(
    () => this.all().filter((conversation) => conversation.isReplyWindowClosed).length,
  );

  readonly countByChannel = computed(() => {
    const counts = new Map<ConversationChannel, number>();
    for (const conversation of this.all()) {
      counts.set(conversation.channel, (counts.get(conversation.channel) ?? 0) + 1);
    }
    return counts;
  });

  readonly countByNetwork = computed(() => {
    const counts = new Map<SocialNetworkCode, number>();
    for (const conversation of this.all()) {
      counts.set(conversation.network, (counts.get(conversation.network) ?? 0) + 1);
    }
    return counts;
  });

  private readonly selectedId = signal(CONVERSATIONS[0].id);

  /**
   * Conversation ouverte dans le volet de droite.
   *
   * Si un filtre fait disparaître la conversation ouverte, on bascule sur
   * la première de la liste plutôt que de laisser un volet orphelin.
   */
  readonly selected = computed<Conversation | null>(() => {
    const results = this.results();
    if (results.length === 0) return null;
    return results.find((conversation) => conversation.id === this.selectedId()) ?? results[0];
  });

  select(conversation: Conversation): void {
    this.selectedId.set(conversation.id);
  }

  setChannelFilter(channel: ConversationChannel | null): void {
    this.channelFilter.set(channel);
    this.isListExpanded.set(false);
  }

  setNetworkFilter(network: SocialNetworkCode | null): void {
    // Recliquer la plateforme active la désélectionne : sans cela, rien ne
    // permettrait de revenir à « toutes plateformes ».
    this.networkFilter.update((current) => (current === network ? null : network));
    this.isListExpanded.set(false);
  }

  expandList(): void {
    this.isListExpanded.set(true);
  }
}
