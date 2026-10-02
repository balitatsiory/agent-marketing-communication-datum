import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import {
  CONVERSATION_CHANNEL_LABELS,
  CONVERSATION_CHANNEL_SHORT,
  Conversation,
  ConversationChannel,
  conversationExcerpt,
} from '../../../core/models/conversation';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { InboxStore } from '../../../core/services/inbox-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/**
 * Messagerie unifiée — maquette 10a.
 *
 * Trois colonnes : filtres, file des conversations, fil ouvert. L'agent
 * prépare les réponses, un humain les envoie — rien ne part sans une
 * action explicite, et le volet le dit.
 *
 * Deux états du fil méritent l'attention :
 * - un brouillon d'agent à valider, rejeter ou retoucher ;
 * - une fenêtre de réponse fermée par la plateforme, où l'envoi depuis
 *   IAGORA est impossible et le champ désactivé.
 */
@Component({
  selector: 'app-unified-inbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon, NetworkLogo],
  templateUrl: './unified-inbox.html',
  styleUrl: './unified-inbox.scss',
})
export class UnifiedInbox {
  protected readonly store = inject(InboxStore);

  protected readonly networks = SOCIAL_NETWORKS;
  protected readonly channelLabels = CONVERSATION_CHANNEL_LABELS;
  protected readonly channelShort = CONVERSATION_CHANNEL_SHORT;
  protected readonly channels: readonly ConversationChannel[] = [
    'directMessage',
    'comment',
    'mention',
  ];

  protected readonly manualReply = signal('');

  protected excerpt(conversation: Conversation): string {
    return conversationExcerpt(conversation);
  }

  protected countFor(channel: ConversationChannel): number {
    return this.store.countByChannel().get(channel) ?? 0;
  }

  protected countForNetwork(code: SocialNetworkCode): number {
    return this.store.countByNetwork().get(code) ?? 0;
  }
}
