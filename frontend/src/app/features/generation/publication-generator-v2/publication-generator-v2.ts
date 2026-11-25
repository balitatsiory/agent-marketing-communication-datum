import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { toApiError } from '../../../core/api/api-error';
import { MediaApi } from '../../../core/api/media.api';
import {
  OpenRouterApi,
  PublicationGenerationContextDto,
  PublicationTextGenerationResponseDto,
  PublicationTextProposalDto,
} from '../../../core/api/openrouter.api';
import { SocialAccountsApi } from '../../../core/api/social-accounts.api';
import { DEFAULT_BRIEF } from '../../../core/data/generation.data';
import { FORMAT_BOUNDS } from '../../../core/data/platform-formats.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import {
  GENERATION_TONE_LABELS,
  GeneratedVisual,
  GenerationTone,
} from '../../../core/models/generation';
import {
  MediaReferenceNature,
  MediaReferenceView,
  toMediaReferenceNature,
  toMediaReferenceView,
  toMediaView,
} from '../../../core/models/media-reference';
import { PUBLICATION_FORMAT_LABELS, PublicationFormat } from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/** Les cinq étapes du parcours, dans l'ordre. */
const STEPS = [
  { n: 1, label: 'Forme et destination' },
  { n: 2, label: 'Le sujet' },
  { n: 3, label: 'Les propositions' },
  { n: 4, label: 'Le visuel' },
  { n: 5, label: 'Récapitulatif' },
] as const;

type RoleFilter = string;

interface FormatVisualSpec {
  readonly ratio: GeneratedVisual['ratio'];
  readonly apiRatio: string;
  readonly dimensions: string;
}

const FORMAT_VISUAL_SPECS: Readonly<Record<PublicationFormat, FormatVisualSpec>> = {
  image: { ratio: '4 / 5', apiRatio: '4:5', dimensions: '1080 × 1350' },
  carousel: { ratio: '1 / 1', apiRatio: '1:1', dimensions: '1080 × 1080' },
  reel: { ratio: '9 / 16', apiRatio: '9:16', dimensions: '1080 × 1920' },
  video: { ratio: '4 / 5', apiRatio: '16:9', dimensions: '1920 × 1080' },
  story: { ratio: '9 / 16', apiRatio: '9:16', dimensions: '1080 × 1920' },
  document: { ratio: '4 / 5', apiRatio: '4:5', dimensions: 'PDF A4' },
  text: { ratio: '1 / 1', apiRatio: '1:1', dimensions: 'aucun média' },
};

const KNOWN_NETWORK_CODES = new Set<SocialNetworkCode>([
  'facebook',
  'instagram',
  'linkedin',
  'youtube',
  'tiktok',
]);

export interface TargetNetworkItem {
  readonly code: SocialNetworkCode;
  readonly label: string;
  readonly accountName: string;
  readonly accountId?: number;
}

/** Une version du visuel dans l'étape 4 (issue de l'IA ou d'un fichier importé). */
export interface VisualVersionItem {
  readonly label: string;
  readonly origin: 'ai' | 'imported';
  readonly fileName?: string;
  readonly change: string | null;
  readonly idMedia?: number | null;
  readonly modelId?: string | null;
  readonly costUsd?: number | null;
  /** Data URL base64 (pour fichier importé) ou URL R2 (pour visuel IA), envoyé à l'API lors d'une retouche. */
  readonly sourceForAi?: string;
  readonly visual: GeneratedVisual;
}

export interface RetouchChatBubble {
  readonly author: 'ai' | 'me';
  readonly text: string;
}

const RETOUCH_QUICK_PROMPTS: readonly string[] = [
  'Agrandis le logo et remonte la date.',
  'Utilise la palette bleu nuit #232F3E et orange #FF9900.',
  'Renforce le contraste sous le titre.',
];

const ANGLES = ['Annonce', 'Bénéfice', 'Question'] as const;

/**
 * Générer une publication — version 2, parcours en cinq étapes branché sur :
 * - Modèles IA & Affectations (`ai_task_assignments` + `reasoning_effort`, OpenRouter)
 * - Prompts système & gabarits actifs par défaut (`ai_prompts`)
 * - Médias de référence & Médiathèque R2 (`media_references` + `media`)
 * - Comptes réseaux sociaux raccordés (`social_accounts`)
 */
@Component({
  selector: 'app-publication-generator-v2',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-generator-v2.html',
  styleUrl: './publication-generator-v2.scss',
})
export class PublicationGeneratorV2 {
  private readonly mediaApi = inject(MediaApi);
  private readonly openRouterApi = inject(OpenRouterApi);
  private readonly socialAccountsApi = inject(SocialAccountsApi);
  private readonly createdObjectUrls: string[] = [];

  protected readonly steps = STEPS;
  protected readonly toneLabels = GENERATION_TONE_LABELS;
  protected readonly tones = Object.keys(GENERATION_TONE_LABELS) as GenerationTone[];
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly formatBounds = FORMAT_BOUNDS;
  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  protected readonly angles = ANGLES;
  protected readonly quickPrompts = RETOUCH_QUICK_PROMPTS;

  /* ---------- contexte IA actif ---------- */

  protected readonly aiContext = signal<PublicationGenerationContextDto | null>(null);
  protected readonly aiContextError = signal<string | null>(null);
  protected readonly noticeMessage = signal<string | null>(null);

  /* ---------- étape courante ---------- */

  protected readonly step = signal(1);
  protected readonly requestId = signal<number | null>(null);

  /* ---------- étape 1 : forme et destination ---------- */

  protected readonly networks = signal<readonly TargetNetworkItem[]>(
    SOCIAL_NETWORKS.filter((n) => n.isConnected).map((n) => ({
      code: n.code,
      label: n.label,
      accountName: n.accountName,
    })),
  );
  protected readonly format = signal<PublicationFormat>(DEFAULT_BRIEF.format);
  protected readonly briefNetworks = signal<ReadonlySet<SocialNetworkCode>>(DEFAULT_BRIEF.networks);
  protected readonly isFormatDrawerOpen = signal(false);

  protected readonly currentFormatSpec = computed<FormatVisualSpec>(
    () => FORMAT_VISUAL_SPECS[this.format()],
  );

  /* ---------- étape 2 & 4 : le sujet et les médias de référence ---------- */

  protected readonly subject = signal(DEFAULT_BRIEF.subject);
  protected readonly visualDescription = signal(DEFAULT_BRIEF.context);
  protected readonly tone = signal<GenerationTone>(DEFAULT_BRIEF.tone);
  protected readonly language = signal(DEFAULT_BRIEF.language);
  protected readonly includeHashtags = signal(DEFAULT_BRIEF.includeHashtags);
  protected readonly hashtagsMin = signal(3);
  protected readonly hashtagsMax = signal(6);
  protected readonly useKnowledgeBase = signal(true);
  protected readonly referenceIds = signal<ReadonlySet<number>>(new Set());

  private readonly natures = signal<readonly MediaReferenceNature[]>([]);
  protected readonly library = signal<readonly MediaReferenceView[]>([]);

  protected readonly references = computed(() =>
    this.library().filter((entry) => this.referenceIds().has(entry.idMediaReferences)),
  );

  /* ---------- la bibliothèque (pop-up) ---------- */

  protected readonly isLibraryOpen = signal(false);
  protected readonly librarySearch = signal('');
  protected readonly libraryRoleFilter = signal<RoleFilter>('all');
  protected readonly libraryDraft = signal<ReadonlySet<number>>(new Set<number>());

  protected readonly roleFilterOptions = computed(() => {
    const all = this.library();
    return [
      { key: 'all' as RoleFilter, label: 'Tous', count: all.length },
      ...this.natures().map((nature) => ({
        key: nature.code as RoleFilter,
        label: nature.label,
        count: all.filter((entry) => entry.natureCode === nature.code).length,
      })),
    ];
  });

  protected readonly libraryResults = computed(() => {
    const roleFilter = this.libraryRoleFilter();
    const needle = this.librarySearch().trim().toLowerCase();
    let list = this.library();

    if (roleFilter !== 'all') {
      list = list.filter((entry) => entry.natureCode === roleFilter);
    }

    if (!needle) return list;
    return list.filter(
      (entry) =>
        entry.label.toLowerCase().includes(needle) ||
        (entry.description?.toLowerCase().includes(needle) ?? false) ||
        entry.natureLabel.toLowerCase().includes(needle),
    );
  });

  /* ---------- étape 3 : les propositions ---------- */

  protected readonly proposalsByNetwork = signal<
    Readonly<Record<string, readonly PublicationTextProposalDto[]>>
  >({});
  protected readonly selectedByNetwork = signal<Readonly<Record<string, string>>>({});
  protected readonly lastTextMeta = signal<PublicationTextGenerationResponseDto | null>(null);
  protected readonly isGenerating = signal(false);
  protected readonly textError = signal<string | null>(null);
  protected readonly runNumber = signal(0);
  protected readonly pageSize = signal(3);

  /* Modale d'édition d'une proposition de texte */
  protected readonly editingProposal = signal<{
    network: string;
    id: string;
    angle: string;
  } | null>(null);
  protected readonly editBodyDraft = signal('');
  protected readonly editTagsDraft = signal('');

  protected readonly hasGeneratedTexts = computed(() => {
    const map = this.proposalsByNetwork();
    return Object.values(map).some((list) => list.length > 0);
  });

  /* ---------- étape 4 : le visuel ---------- */

  protected readonly versions = signal<readonly VisualVersionItem[]>([]);
  protected readonly visualIndex = signal(0);
  protected readonly retouchDraft = signal('');
  protected readonly isVisualDragOver = signal(false);
  protected readonly isGeneratingVisual = signal(false);
  protected readonly visualError = signal<string | null>(null);
  protected readonly visualImportError = signal<string | null>(null);

  protected readonly chatMessages = signal<readonly RetouchChatBubble[]>([
    {
      author: 'ai',
      text: "Prêt à générer votre visuel à partir du brief, de vos médias de référence et du prompt actif. Vous pouvez aussi importer un fichier pour l'utiliser tel quel ou me demander de le retoucher.",
    },
  ]);

  protected readonly currentVisual = computed<VisualVersionItem | null>(
    () => this.versions()[this.visualIndex()] ?? this.versions()[0] ?? null,
  );

  /* ---------- étape 5 : récapitulatif ---------- */

  protected readonly scheduleMode = signal<'now' | 'later'>('later');
  protected readonly scheduledDate = signal(new Date().toISOString().slice(0, 10));
  protected readonly scheduledTime = signal('09:00');
  protected readonly createdConfirmation = signal<string | null>(null);

  protected readonly targets = computed(() =>
    this.networks().filter((network) => this.briefNetworks().has(network.code)),
  );

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      for (const url of this.createdObjectUrls) {
        URL.revokeObjectURL(url);
      }
    });
    void this.chargerDonneesInitiales();
  }

  private async chargerDonneesInitiales(): Promise<void> {
    await Promise.all([
      this.chargerContexteIA(),
      this.chargerReferences(),
      this.chargerComptesSociaux(),
    ]);
  }

  private async chargerContexteIA(): Promise<void> {
    try {
      const ctx = await this.openRouterApi.generationContext();
      this.aiContext.set(ctx);
      this.aiContextError.set(null);
    } catch (err) {
      this.aiContextError.set(toApiError(err).message);
    }
  }

  private async chargerComptesSociaux(): Promise<void> {
    try {
      const comptes = await this.socialAccountsApi.list();
      const actifs = comptes.filter(
        (c) =>
          c.status_code !== 'disconnected' &&
          KNOWN_NETWORK_CODES.has(c.platform_code.toLowerCase() as SocialNetworkCode),
      );
      if (actifs.length === 0) return;

      // Dédoublonner par plateforme pour l'étape 1 (un toggle par réseau), en affichant le compte principal
      const parReseau = new Map<SocialNetworkCode, TargetNetworkItem>();
      for (const c of actifs) {
        const code = c.platform_code.toLowerCase() as SocialNetworkCode;
        if (!parReseau.has(code)) {
          parReseau.set(code, {
            code,
            label: c.platform_label,
            accountName: c.account_display_name,
            accountId: c.id_social_accounts,
          });
        }
      }
      const liste = Array.from(parReseau.values());
      this.networks.set(liste);
      this.briefNetworks.set(new Set(liste.slice(0, 2).map((n) => n.code)));
    } catch {
      // Conserve le repli par défaut si l'API comptes sociaux n'est pas accessible.
    }
  }

  private async chargerReferences(): Promise<void> {
    try {
      const [naturesDto, refsPage, mediasPage] = await Promise.all([
        this.mediaApi.natures(),
        this.mediaApi.listReferences({ page: 1, size: 200 }, false),
        this.mediaApi.list({ page: 1, size: 200 }, false),
      ]);
      const natures = naturesDto.map(toMediaReferenceNature).sort((a, b) => a.sortOrder - b.sortOrder);
      const mediasParId = new Map(mediasPage.items.map((m) => [m.id_media, toMediaView(m)]));
      const naturesParCode = new Map(natures.map((n) => [n.code, n]));
      this.natures.set(natures);
      this.library.set(
        refsPage.items
          .filter((r) => r.is_active && r.deleted_at === null)
          .map((r) => toMediaReferenceView(r, mediasParId, naturesParCode)),
      );
    } catch {
      // Silencieux si le compte n'a pas le droit médias.
    }
  }

  /* ---------- navigation ---------- */

  protected readonly hasVisualStep = computed(() => this.format() !== 'text');

  protected goTo(n: number): void {
    if (n === 4 && !this.hasVisualStep() && this.step() !== 4) return;
    this.step.set(n);
    if (n === 4 && this.hasVisualStep() && this.versions().length === 0 && !this.isGeneratingVisual()) {
      void this.generateVisual('create');
    }
  }

  protected next(): void {
    const n = this.step() + 1;
    const target = n === 4 && !this.hasVisualStep() ? 5 : n;
    this.goTo(target);
  }

  protected previous(): void {
    const n = this.step() - 1;
    this.step.set(n === 4 && !this.hasVisualStep() ? 3 : Math.max(1, n));
  }

  /* ---------- format et réseaux ---------- */

  protected toggleFormatDrawer(): void {
    this.isFormatDrawerOpen.update((open) => !open);
  }

  protected chooseFormat(option: PublicationFormat): void {
    this.format.set(option);
    if (option !== 'text') {
      const spec = FORMAT_VISUAL_SPECS[option];
      this.versions.update((list) =>
        list.map((item) => ({
          ...item,
          visual: {
            ...item.visual,
            ratio: spec.ratio,
            dimensions: spec.dimensions,
          },
        })),
      );
    }
  }

  protected toggleNetwork(code: SocialNetworkCode): void {
    this.briefNetworks.update((current) => {
      const next = new Set(current);
      if (!next.delete(code)) next.add(code);
      return next;
    });
  }

  /* ---------- médias de référence (liste + pop-up) ---------- */

  protected removeReference(id: number): void {
    this.referenceIds.update((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  }

  protected openLibrary(): void {
    this.libraryDraft.set(new Set(this.referenceIds()));
    this.librarySearch.set('');
    this.libraryRoleFilter.set('all');
    this.isLibraryOpen.set(true);
  }

  protected setLibraryRoleFilter(role: RoleFilter): void {
    this.libraryRoleFilter.set(role);
  }

  protected toggleDraft(id: number): void {
    this.libraryDraft.update((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  protected confirmLibrary(): void {
    this.referenceIds.set(new Set(this.libraryDraft()));
    this.isLibraryOpen.set(false);
  }

  protected closeLibrary(): void {
    this.isLibraryOpen.set(false);
  }

  /* ---------- étape 3 : génération réelle des textes ---------- */

  protected proposalsFor(networkCode: string): readonly PublicationTextProposalDto[] {
    const all = this.proposalsByNetwork()[networkCode] ?? [];
    return all.slice(0, this.pageSize());
  }

  protected selectedProposalFor(networkCode: string): PublicationTextProposalDto | null {
    const list = this.proposalsByNetwork()[networkCode] ?? [];
    if (list.length === 0) return null;
    const chosenId = this.selectedByNetwork()[networkCode];
    return list.find((p) => p.id === chosenId) ?? list[0];
  }

  protected select(networkCode: string, proposal: PublicationTextProposalDto): void {
    this.selectedByNetwork.update((map) => ({ ...map, [networkCode]: proposal.id }));
  }

  protected isSelected(networkCode: string, proposal: PublicationTextProposalDto): boolean {
    const chosen = this.selectedProposalFor(networkCode);
    return chosen?.id === proposal.id;
  }

  protected lengthOf(proposal: PublicationTextProposalDto): number {
    return proposal.paragraphs.join('\n\n').length;
  }

  protected async generateTexts(): Promise<void> {
    const sujet = this.subject().trim();
    const reseaux = this.targets().map((t) => t.code);
    if (sujet.length < 3) {
      this.textError.set('Saisissez un sujet d’au moins 3 caractères avant de générer.');
      return;
    }
    if (reseaux.length === 0) {
      this.textError.set('Sélectionnez au moins un réseau à l’étape 1.');
      return;
    }

    this.proposalsByNetwork.set({});
    this.selectedByNetwork.set({});
    this.runNumber.set(1);
    this.step.set(3);
    await this.executerGenerationTextes(1, false);
  }

  protected async regenerate(): Promise<void> {
    const nextRun = this.runNumber() + 1;
    this.runNumber.set(nextRun);
    await this.executerGenerationTextes(nextRun, true);
  }

  private async executerGenerationTextes(runNum: number, append: boolean): Promise<void> {
    const reseaux = this.targets().map((t) => t.code);
    this.isGenerating.set(true);
    this.textError.set(null);
    try {
      const res = await this.openRouterApi.generatePublicationTexts({
        subject: this.subject().trim(),
        format: this.format(),
        networks: reseaux,
        tone: this.tone(),
        language: this.language(),
        hashtags_min: Math.max(0, Number(this.hashtagsMin()) || 0),
        hashtags_max: Math.max(0, Number(this.hashtagsMax()) || 0),
        use_knowledge_base: this.useKnowledgeBase(),
        run_number: runNum,
        angles: [...ANGLES],
      });

      this.lastTextMeta.set(res);
      if (!this.requestId()) {
        this.requestId.set(Math.floor(Date.now() / 1000) % 100000);
      }

      this.proposalsByNetwork.update((current) => {
        const nextMap: Record<string, readonly PublicationTextProposalDto[]> = append
          ? { ...current }
          : {};
        for (const net of reseaux) {
          const incoming = res.proposals_by_network[net] ?? [];
          nextMap[net] = append ? [...incoming, ...(nextMap[net] ?? [])] : incoming;
        }
        return nextMap;
      });

      // Sélectionner la première proposition de chaque réseau si aucune n'est encore sélectionnée
      this.selectedByNetwork.update((current) => {
        const nextSel: Record<string, string> = { ...current };
        for (const net of reseaux) {
          const incoming = res.proposals_by_network[net] ?? [];
          if ((!append || !nextSel[net]) && incoming.length > 0) {
            nextSel[net] = incoming[0].id;
          }
        }
        return nextSel;
      });
    } catch (err) {
      this.textError.set(toApiError(err).message);
    } finally {
      this.isGenerating.set(false);
    }
  }

  /* Édition & copie d'une proposition */

  protected openEditProposal(
    event: Event,
    networkCode: string,
    proposal: PublicationTextProposalDto,
  ): void {
    event.stopPropagation();
    this.editingProposal.set({
      network: networkCode,
      id: proposal.id,
      angle: proposal.angle,
    });
    this.editBodyDraft.set(proposal.paragraphs.join('\n\n'));
    this.editTagsDraft.set(proposal.hashtags.join(' '));
  }

  protected saveEditProposal(): void {
    const target = this.editingProposal();
    if (!target) return;

    const paragraphs = this.editBodyDraft()
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);
    if (paragraphs.length === 0) return;

    const hashtags = this.editTagsDraft()
      .split(/[\s,]+/)
      .map((t) => t.trim())
      .filter(Boolean)
      .map((t) => (t.startsWith('#') ? t : `#${t}`));

    this.proposalsByNetwork.update((map) => {
      const list = map[target.network] ?? [];
      return {
        ...map,
        [target.network]: list.map((p) =>
          p.id === target.id ? { ...p, paragraphs, hashtags } : p,
        ),
      };
    });
    this.editingProposal.set(null);
    this.flashNotice('Texte de la proposition mis à jour.');
  }

  protected copyProposalToOtherNetworks(
    event: Event,
    sourceNetwork: string,
    proposal: PublicationTextProposalDto,
  ): void {
    event.stopPropagation();
    const others = this.targets()
      .map((t) => t.code)
      .filter((code) => code !== sourceNetwork);
    if (others.length === 0) return;

    this.proposalsByNetwork.update((map) => {
      const nextMap: Record<string, readonly PublicationTextProposalDto[]> = { ...map };
      for (const other of others) {
        const clone: PublicationTextProposalDto = {
          ...proposal,
          id: `copy-${other}-${Date.now()}`,
          network: other,
        };
        nextMap[other] = [clone, ...(nextMap[other] ?? [])];
      }
      return nextMap;
    });
    this.selectedByNetwork.update((sel) => {
      const nextSel: Record<string, string> = { ...sel };
      for (const other of others) {
        const first = this.proposalsByNetwork()[other]?.[0];
        if (first) nextSel[other] = first.id;
      }
      return nextSel;
    });
    this.flashNotice(`Proposition copiée vers ${others.length} autre(s) réseau(x).`);
  }

  /* ---------- étape 4 : génération & retouche réelle du visuel ---------- */

  private primarySelectedCaption(): string {
    for (const target of this.targets()) {
      const prop = this.selectedProposalFor(target.code);
      if (prop) {
        return prop.paragraphs.join('\n\n');
      }
    }
    return '';
  }

  protected regenerateVisuals(): void {
    void this.generateVisual('create');
  }

  private async generateVisual(
    mode: 'create' | 'retouch',
    retouchInstruction?: string,
  ): Promise<void> {
    if (this.isGeneratingVisual()) return;
    const spec = this.currentFormatSpec();
    const sourceVersion = mode === 'retouch' ? this.currentVisual() : null;

    this.isGeneratingVisual.set(true);
    this.visualError.set(null);
    if (mode === 'retouch' && retouchInstruction) {
      this.chatMessages.update((msgs) => [...msgs, { author: 'me', text: retouchInstruction }]);
    }

    try {
      const res = await this.openRouterApi.generatePublicationVisual({
        mode,
        subject: this.subject().trim() || 'Publication DATUM Academy',
        visual_description: this.visualDescription().trim(),
        selected_caption: this.primarySelectedCaption(),
        format: this.format(),
        aspect_ratio: spec.apiRatio,
        retouch_instruction: mode === 'retouch' ? retouchInstruction : null,
        source_image_url:
          mode === 'retouch' && sourceVersion
            ? (sourceVersion.sourceForAi ?? sourceVersion.visual.source)
            : null,
        reference_media_ids: Array.from(this.referenceIds()),
      });

      const nextNum = this.versions().length + 1;
      const newLabel = `v${nextNum}`;
      const refCount = this.references().length;

      const changeLabel =
        mode === 'retouch' && retouchInstruction
          ? `Retouche de ${sourceVersion?.label ?? 'v1'} : « ${retouchInstruction} »`
          : refCount > 0
            ? `Généré (${res.model_name ?? res.model_id}) · ${refCount} réf.`
            : `Généré (${res.model_name ?? res.model_id})`;

      const newItem: VisualVersionItem = {
        label: newLabel,
        origin: 'ai',
        change: changeLabel,
        idMedia: res.id_media,
        modelId: res.model_id,
        costUsd: res.cost_usd,
        sourceForAi: res.image_url,
        visual: {
          source: res.image_url,
          ratio: spec.ratio,
          dimensions: spec.dimensions,
          alt: `Visuel ${newLabel} généré pour ${this.subject()}`,
        },
      };

      this.versions.update((current) => [newItem, ...current]);
      this.visualIndex.set(0);

      const metaSuffix = res.id_media ? ` (enregistré dans la Médiathèque #${res.id_media})` : '';
      this.chatMessages.update((msgs) => [
        ...msgs,
        { author: 'ai', text: `${res.assistant_message}${metaSuffix}` },
      ]);
    } catch (err) {
      const msg = toApiError(err).message;
      this.visualError.set(msg);
      this.chatMessages.update((msgs) => [
        ...msgs,
        { author: 'ai', text: `Erreur lors de la génération : ${msg}` },
      ]);
    } finally {
      this.isGeneratingVisual.set(false);
    }
  }

  protected showVisual(index: number): void {
    this.visualIndex.set(index);
  }

  /* ---------- import d'un nouveau fichier visuel (étape 4) ---------- */

  protected onVisualFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.importVisualFile(file);
    }
    input.value = '';
  }

  protected onVisualDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isVisualDragOver.set(true);
  }

  protected onVisualDragLeave(): void {
    this.isVisualDragOver.set(false);
  }

  protected onVisualDrop(event: DragEvent): void {
    event.preventDefault();
    this.isVisualDragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.importVisualFile(file);
    }
  }

  private importVisualFile(file: File): void {
    if (!file.type.startsWith('image/')) {
      this.visualImportError.set(
        `« ${file.name} » n'est pas une image. Formats acceptés : PNG, JPG, WebP, SVG.`,
      );
      return;
    }

    this.visualImportError.set(null);
    const objectUrl = URL.createObjectURL(file);
    this.createdObjectUrls.push(objectUrl);

    const nextNum = this.versions().length + 1;
    const newLabel = `v${nextNum}`;
    const spec = this.currentFormatSpec();

    const importedItem: VisualVersionItem = {
      label: newLabel,
      origin: 'imported',
      fileName: file.name,
      change: `Importé : ${file.name}`,
      visual: {
        source: objectUrl,
        ratio: spec.ratio,
        dimensions: spec.dimensions,
        alt: `Fichier importé ${file.name}`,
      },
    };

    this.versions.update((current) => [importedItem, ...current]);
    this.visualIndex.set(0);

    // Lire aussi en Data URL pour permettre la retouche IA directe sur ce fichier importé
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        const dataUrl = reader.result;
        this.versions.update((list) =>
          list.map((v) => (v.label === newLabel ? { ...v, sourceForAi: dataUrl } : v)),
        );
      }
    };
    reader.readAsDataURL(file);

    this.chatMessages.update((msgs) => [
      ...msgs,
      {
        author: 'ai',
        text: `Fichier « ${file.name} » importé en tant que ${newLabel}. Vous pouvez continuer directement avec ce fichier ou m'écrire une consigne pour le retoucher par IA.`,
      },
    ]);
  }

  /* ---------- retouche par conversation ---------- */

  protected applyQuickPrompt(prompt: string): void {
    this.retouchDraft.set(prompt);
  }

  protected sendRetouch(): void {
    const prompt = this.retouchDraft().trim();
    if (!prompt || this.isGeneratingVisual()) return;
    this.retouchDraft.set('');
    void this.generateVisual('retouch', prompt);
  }

  /* ---------- étape 5 : validation récapitulatif ---------- */

  protected openEditForNetwork(networkCode: string): void {
    const prop = this.selectedProposalFor(networkCode);
    if (!prop) return;
    this.editingProposal.set({
      network: networkCode,
      id: prop.id,
      angle: prop.angle,
    });
    this.editBodyDraft.set(prop.paragraphs.join('\n\n'));
    this.editTagsDraft.set(prop.hashtags.join(' '));
  }

  protected finalizePublication(): void {
    const count = this.targets().length;
    const vis = this.currentVisual();
    const when =
      this.scheduleMode() === 'now'
        ? "dès l'approbation"
        : `le ${this.scheduledDate()} à ${this.scheduledTime()}`;
    const mediaInfo = vis?.idMedia ? ` · Visuel enregistré (Médiathèque #${vis.idMedia})` : '';
    this.createdConfirmation.set(
      `Publication prête pour ${count} réseau${count > 1 ? 'x' : ''} (${when})${mediaInfo}. Les textes IA et le visuel R2 sont prêts pour le module Publications.`,
    );
  }

  private flashNotice(msg: string): void {
    this.noticeMessage.set(msg);
    setTimeout(() => {
      if (this.noticeMessage() === msg) {
        this.noticeMessage.set(null);
      }
    }, 4000);
  }
}
