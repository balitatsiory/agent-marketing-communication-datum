import { ChangeDetectionStrategy, Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  APPLIED_PALETTE,
  DEFAULT_BRIEF,
  PROPOSALS,
  REMAINING_GENERATIONS,
  RETOUCH_CONVERSATION,
  RETOUCH_SUGGESTIONS,
  VISUAL_VERSIONS,
} from '../../../core/data/generation.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import {
  GENERATION_TONE_LABELS,
  GenerationProposal,
  GenerationTone,
  RetouchMessage,
  captionLength,
} from '../../../core/models/generation';
import { PUBLICATION_FORMAT_LABELS, PublicationFormat } from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/** Cadrages proposés dans la pop-up de retouche. */
const RETOUCH_CROPS = ['Instagram Reels', 'Feed 4:5', 'Story', 'Facebook'] as const;

/**
 * Générer une publication — maquettes 4a et 4a1.
 *
 * Deux colonnes : le brief à gauche, les trois propositions à droite.
 * « Voir aperçu & éditer » ouvre la pop-up 4a1, où le visuel se retouche
 * par conversation.
 *
 * La génération est simulée : voir `generation.data.ts` pour ce qu'il
 * restera à brancher.
 */
@Component({
  selector: 'app-publication-generator',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-generator.html',
  styleUrl: './publication-generator.scss',
})
export class PublicationGenerator {
  protected readonly networks = SOCIAL_NETWORKS.filter((network) => network.isConnected);
  protected readonly toneLabels = GENERATION_TONE_LABELS;
  protected readonly tones = Object.keys(GENERATION_TONE_LABELS) as GenerationTone[];
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  protected readonly remainingGenerations = REMAINING_GENERATIONS;
  protected readonly palette = APPLIED_PALETTE;
  protected readonly retouchSuggestions = RETOUCH_SUGGESTIONS;
  protected readonly crops = RETOUCH_CROPS;
  protected readonly versions = VISUAL_VERSIONS;

  /* ---------- brief ---------- */

  protected readonly subject = signal(DEFAULT_BRIEF.subject);
  protected readonly context = signal(DEFAULT_BRIEF.context);
  protected readonly tone = signal<GenerationTone>(DEFAULT_BRIEF.tone);
  protected readonly format = signal<PublicationFormat>(DEFAULT_BRIEF.format);
  protected readonly language = signal(DEFAULT_BRIEF.language);
  protected readonly includeHashtags = signal(DEFAULT_BRIEF.includeHashtags);
  protected readonly briefNetworks = signal<ReadonlySet<SocialNetworkCode>>(DEFAULT_BRIEF.networks);

  protected readonly isGenerating = signal(false);

  /* ---------- propositions ---------- */

  protected readonly proposals = signal<readonly GenerationProposal[]>(PROPOSALS);
  protected readonly selectedId = signal(PROPOSALS[0].id);

  protected readonly selected = computed(
    () => this.proposals().find((proposal) => proposal.id === this.selectedId()) ?? PROPOSALS[0],
  );

  /* ---------- pop-up de retouche ---------- */

  protected readonly isRetouchOpen = signal(false);
  protected readonly retouchProposal = signal<GenerationProposal>(PROPOSALS[0]);
  protected readonly versionIndex = signal(0);
  protected readonly crop = signal<string>(RETOUCH_CROPS[0]);
  protected readonly conversation = signal<readonly RetouchMessage[]>(RETOUCH_CONVERSATION);
  protected readonly draftMessage = signal('');
  protected readonly isRetouching = signal(true);

  protected readonly currentVersion = computed(() => this.versions[this.versionIndex()]);

  /** Historique, de la plus ancienne retouche à la plus récente. */
  protected readonly retouchHistory = computed(() =>
    [...this.versions]
      .reverse()
      .filter((version) => version.change !== null)
      .map((version) => `${version.label} → ${version.change}`),
  );

  protected lengthOf(proposal: GenerationProposal): number {
    return captionLength(proposal);
  }

  protected toggleBriefNetwork(code: SocialNetworkCode): void {
    this.briefNetworks.update((current) => {
      const next = new Set(current);
      if (!next.delete(code)) next.add(code);
      return next;
    });
  }

  /**
   * Simule l'appel au modèle.
   *
   * Le délai est volontaire : l'écran doit savoir afficher son état
   * d'attente avant même que le backend existe.
   */
  protected generate(): void {
    this.isGenerating.set(true);
    setTimeout(() => this.isGenerating.set(false), 800);
  }

  protected select(proposal: GenerationProposal): void {
    this.selectedId.set(proposal.id);
  }

  protected openRetouch(proposal: GenerationProposal): void {
    this.retouchProposal.set(proposal);
    this.selectedId.set(proposal.id);
    this.versionIndex.set(0);
    this.isRetouchOpen.set(true);
  }

  protected closeRetouch(): void {
    this.isRetouchOpen.set(false);
  }

  protected showVersion(index: number): void {
    this.versionIndex.set(index);
  }

  /** Ajoute le message à la conversation et simule la régénération. */
  protected sendMessage(text = this.draftMessage()): void {
    const trimmed = text.trim();
    if (!trimmed) return;

    this.conversation.update((log) => [...log, { author: 'user', text: trimmed }]);
    this.draftMessage.set('');
    this.isRetouching.set(true);

    setTimeout(() => {
      this.conversation.update((log) => [
        ...log,
        {
          author: 'assistant',
          text: "Visuel régénéré avec cette consigne. Dites-moi si l'équilibre vous convient.",
          actions: ['Garder cette version', 'Revenir à la précédente'],
        },
      ]);
      this.isRetouching.set(false);
    }, 900);
  }
}
