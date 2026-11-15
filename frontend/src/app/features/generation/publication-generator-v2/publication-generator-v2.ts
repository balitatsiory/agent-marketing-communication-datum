import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
   computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  DEFAULT_BRIEF,
  PROPOSALS,
  REMAINING_GENERATIONS,
  VISUAL_VERSIONS,
} from '../../../core/data/generation.data';
import { FORMAT_BOUNDS } from '../../../core/data/platform-formats.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import {
  GENERATION_TONE_LABELS,
  GeneratedVisual,
  GenerationProposal,
  GenerationTone,
  captionLength,
} from '../../../core/models/generation';
import {
  MEDIA_REFERENCE_ROLE_LABELS,
  MEDIA_REFERENCE_ROLES,
  MediaReferenceRole,
} from '../../../core/models/media-reference';
import { PUBLICATION_FORMAT_LABELS, PublicationFormat } from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { MediaReferenceStore } from '../../../core/services/media-reference-store';
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

/** Filtre par rôle dans la pop-up des médias de référence. */
type RoleFilter = 'all' | MediaReferenceRole;

/** Cadrage et dimensions cibles selon le format de publication. */
interface FormatVisualSpec {
  readonly ratio: GeneratedVisual['ratio'];
  readonly dimensions: string;
}

const FORMAT_VISUAL_SPECS: Readonly<Record<PublicationFormat, FormatVisualSpec>> = {
  image: { ratio: '4 / 5', dimensions: '1080 × 1350' },
  carousel: { ratio: '1 / 1', dimensions: '1080 × 1080' },
  reel: { ratio: '9 / 16', dimensions: '1080 × 1920' },
  video: { ratio: '4 / 5', dimensions: '1920 × 1080' },
  story: { ratio: '9 / 16', dimensions: '1080 × 1920' },
  document: { ratio: '4 / 5', dimensions: 'PDF A4' },
  text: { ratio: '1 / 1', dimensions: 'aucun média' },
};

/** Une version du visuel dans l'étape 4 (issue de l'IA ou d'un fichier importé). */
export interface VisualVersionItem {
  readonly label: string;
  readonly origin: 'ai' | 'imported';
  readonly fileName?: string;
  readonly change: string | null;
  readonly visual: GeneratedVisual;
}

/** Message affiché dans le fil de retouche par conversation. */
export interface RetouchChatBubble {
  readonly author: 'ai' | 'me';
  readonly text: string;
}

/** Suggestions rapides de retouche par prompt. */
const RETOUCH_QUICK_PROMPTS: readonly string[] = [
  'Agrandis le logo et remonte la date.',
  'Utilise la palette bleu nuit #232F3E et orange #FF9900.',
  'Renforce le contraste sous le titre.',
];

/** Angles rédactionnels tirés — table `generation_text_angles`. */
const ANGLES = ['Annonce', 'Bénéfice', 'Question'] as const;

/**
 * Générer une publication — version 2, en parcours de cinq étapes.
 *
 * Reprend la maquette validée le 30 octobre 2026 et le nouveau design
 * de l'étape 4 (« Le visuel ») :
 * - rappel et modification directe du format choisi à l'étape 1 ;
 * - liste des médias de référence sélectionnés et pop-up de sélection
 *   dans la bibliothèque ;
 * - import d'un nouveau fichier visuel pour l'utiliser tel quel ou le
 *   modifier par prompt dans la conversation de retouche.
 */
@Component({
  selector: 'app-publication-generator-v2',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-generator-v2.html',
  styleUrl: './publication-generator-v2.scss',
})
export class PublicationGeneratorV2 {
  private readonly mediaStore = inject(MediaReferenceStore);
  private readonly createdObjectUrls: string[] = [];

  protected readonly steps = STEPS;
  protected readonly networks = SOCIAL_NETWORKS.filter((network) => network.isConnected);
  protected readonly toneLabels = GENERATION_TONE_LABELS;
  protected readonly tones = Object.keys(GENERATION_TONE_LABELS) as GenerationTone[];
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly formatBounds = FORMAT_BOUNDS;
  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  protected readonly remainingGenerations = REMAINING_GENERATIONS;
  protected readonly roleLabels = MEDIA_REFERENCE_ROLE_LABELS;
  protected readonly roles = MEDIA_REFERENCE_ROLES;
  protected readonly angles = ANGLES;
  protected readonly quickPrompts = RETOUCH_QUICK_PROMPTS;

  /* ---------- l'étape courante ---------- */

  protected readonly step = signal(1);

  /** L'identifiant de la demande, qui porte l'adresse dès l'étape 3. */
  protected readonly requestId = signal<number | null>(null);

  /* ---------- étape 1 : forme et destination ---------- */

  protected readonly format = signal<PublicationFormat>(DEFAULT_BRIEF.format);
  protected readonly briefNetworks = signal<ReadonlySet<SocialNetworkCode>>(DEFAULT_BRIEF.networks);
  protected readonly isFormatDrawerOpen = signal(true);

  protected readonly currentFormatSpec = computed<FormatVisualSpec>(
    () => FORMAT_VISUAL_SPECS[this.format()],
  );

  /* ---------- étape 2 & 4 : le sujet et les médias de référence ---------- */

  protected readonly subject = signal(DEFAULT_BRIEF.subject);
  /** Ne nourrit que le visuel, jamais le texte — colonne `visual_description`. */
  protected readonly visualDescription = signal(DEFAULT_BRIEF.context);
  protected readonly tone = signal<GenerationTone>(DEFAULT_BRIEF.tone);
  protected readonly language = signal(DEFAULT_BRIEF.language);
  protected readonly includeHashtags = signal(DEFAULT_BRIEF.includeHashtags);
  protected readonly hashtagsMin = signal(8);
  protected readonly hashtagsMax = signal(12);
  protected readonly useKnowledgeBase = signal(true);
  protected readonly referenceIds = signal<ReadonlySet<number>>(new Set([1, 2]));

  protected readonly library = this.mediaStore.everything;

  protected readonly references = computed(() =>
    this.library().filter((entry) => this.referenceIds().has(entry.id)),
  );

  /* ---------- la bibliothèque (pop-up) ---------- */

  protected readonly isLibraryOpen = signal(false);
  protected readonly librarySearch = signal('');
  protected readonly libraryRoleFilter = signal<RoleFilter>('all');
  /** Sélection en cours dans la pop-up, validée seulement à la fermeture. */
  protected readonly libraryDraft = signal<ReadonlySet<number>>(new Set<number>());

  protected readonly roleFilterOptions = computed(() => {
    const all = this.library();
    return [
      { key: 'all' as RoleFilter, label: 'Tous', count: all.length },
      ...this.roles.map((role) => ({
        key: role as RoleFilter,
        label: this.roleLabels[role],
        count: all.filter((entry) => entry.role === role).length,
      })),
    ];
  });

  /** La recherche porte sur le nom du fichier, le rôle et la description. */
  protected readonly libraryResults = computed(() => {
    const roleFilter = this.libraryRoleFilter();
    const needle = this.librarySearch().trim().toLowerCase();
    let list = this.library();

    if (roleFilter !== 'all') {
      list = list.filter((entry) => entry.role === roleFilter);
    }

    if (!needle) return list;
    return list.filter(
      (entry) =>
        entry.fileName.toLowerCase().includes(needle) ||
        entry.description.toLowerCase().includes(needle) ||
        this.roleLabels[entry.role].toLowerCase().includes(needle),
    );
  });

  /* ---------- étape 3 : les propositions ---------- */

  protected readonly proposals = signal<readonly GenerationProposal[]>(PROPOSALS);
  protected readonly selectedId = signal(PROPOSALS[0].id);
  protected readonly isGenerating = signal(false);
  /** Numéro du lot courant — colonne `run_number`. */
  protected readonly runNumber = signal(1);
  protected readonly pageSize = signal(3);

  protected readonly selected = computed(
    () => this.proposals().find((proposal) => proposal.id === this.selectedId()) ?? PROPOSALS[0],
  );

  /* ---------- étape 4 : le visuel ---------- */

  protected readonly versions = signal<readonly VisualVersionItem[]>(
    VISUAL_VERSIONS.map((v) => ({
      label: v.label,
      origin: 'ai' as const,
      change: v.change,
      visual: v.visual,
    })),
  );
  protected readonly visualIndex = signal(0);
  protected readonly retouchDraft = signal('');
  protected readonly isVisualDragOver = signal(false);
  protected readonly visualImportError = signal<string | null>(null);

  protected readonly chatMessages = signal<readonly RetouchChatBubble[]>([
    {
      author: 'ai',
      text: "Voici trois propositions dans la palette décrite. Vous pouvez aussi importer un fichier pour l'utiliser tel quel ou me demander de le retoucher.",
    },
    {
      author: 'me',
      text: 'Agrandis le logo et remonte la date.',
    },
    {
      author: 'ai',
      text: "Visuel régénéré avec cette consigne (v3). Dites-moi si l'équilibre vous convient.",
    },
  ]);

  protected readonly currentVisual = computed(
    () => this.versions()[this.visualIndex()] ?? this.versions()[0],
  );

  /* ---------- étape 5 : récapitulatif ---------- */

  protected readonly scheduleMode = signal<'now' | 'later'>('later');
  protected readonly scheduledDate = signal('2026-09-18');
  protected readonly scheduledTime = signal('09:00');

  protected readonly targets = computed(() =>
    this.networks.filter((network) => this.briefNetworks().has(network.code)),
  );

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      for (const url of this.createdObjectUrls) {
        URL.revokeObjectURL(url);
      }
    });
  }

  /* ---------- navigation ---------- */

  /** L'étape du visuel n'existe pas quand le format n'accepte aucun média. */
  protected readonly hasVisualStep = computed(() => this.format() !== 'text');

  protected goTo(n: number): void {
    if (n === 4 && !this.hasVisualStep() && this.step() !== 4) return;
    this.step.set(n);
  }

  protected next(): void {
    const n = this.step() + 1;
    this.step.set(n === 4 && !this.hasVisualStep() ? 5 : n);
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

  /* ---------- la génération ---------- */

  /**
   * Écrit la demande, puis lance le premier lot de textes.
   *
   * C'est ce clic qui crée la ligne `generation_requests` et le premier
   * `generation_runs` ; l'identifiant obtenu porte ensuite l'adresse.
   */
  protected generateTexts(): void {
    this.requestId.set(5168);
    this.isGenerating.set(true);
    this.step.set(3);
    setTimeout(() => this.isGenerating.set(false), 900);
  }

  /** Une régénération ajoute un lot : rien n'est effacé. */
  protected regenerate(): void {
    this.runNumber.update((n) => n + 1);
    this.isGenerating.set(true);
    setTimeout(() => this.isGenerating.set(false), 900);
  }

  /** Régénère une proposition de visuel dans l'étape 4 en tenant compte des références. */
  protected regenerateVisuals(): void {
    const nextNum = this.versions().length + 1;
    const newLabel = `v${nextNum}`;
    const spec = this.currentFormatSpec();
    const refCount = this.references().length;

    const newItem: VisualVersionItem = {
      label: newLabel,
      origin: 'ai',
      change:
        refCount > 0
          ? `Régénéré avec ${refCount} média${refCount > 1 ? 's' : ''} de référence`
          : 'Régénéré à partir du brief',
      visual: {
        source: 'flyers/aws-9-16-v3.svg',
        ratio: spec.ratio,
        dimensions: spec.dimensions,
        alt: `Visuel ${newLabel} généré pour ${this.subject()}`,
      },
    };

    this.versions.update((current) => [newItem, ...current]);
    this.visualIndex.set(0);
    this.runNumber.update((n) => n + 1);
  }

  protected select(proposal: GenerationProposal): void {
    this.selectedId.set(proposal.id);
  }

  protected lengthOf(proposal: GenerationProposal): number {
    return captionLength(proposal);
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

    this.chatMessages.update((msgs) => [
      ...msgs,
      {
        author: 'ai',
        text: `Fichier « ${file.name} » importé en tant que ${newLabel}. Vous pouvez continuer directement avec ce fichier ou m'écrire une consigne (ex. « Agrandis le logo et remonte la date. ») pour le modifier.`,
      },
    ]);
  }

  /* ---------- retouche par conversation (sur visuel IA ou fichier importé) ---------- */

  protected applyQuickPrompt(prompt: string): void {
    this.retouchDraft.set(prompt);
  }

  /** Une retouche est une exécution de plus, avec le visuel courant (IA ou importé) pour source. */
  protected sendRetouch(): void {
    const prompt = this.retouchDraft().trim();
    if (!prompt) return;

    const sourceVersion = this.currentVisual();
    const nextNum = this.versions().length + 1;
    const newLabel = `v${nextNum}`;
    const spec = this.currentFormatSpec();

    const retouchedItem: VisualVersionItem = {
      label: newLabel,
      origin: 'ai',
      change: `Retouche de ${sourceVersion.label} : « ${prompt} »`,
      visual: {
        source: sourceVersion.visual.source,
        ratio: spec.ratio,
        dimensions: spec.dimensions,
        alt: `${sourceVersion.visual.alt} — retouché : ${prompt}`,
      },
    };

    this.versions.update((current) => [retouchedItem, ...current]);
    this.visualIndex.set(0);
    this.retouchDraft.set('');
    this.runNumber.update((n) => n + 1);

    const originNote =
      sourceVersion.origin === 'imported'
        ? `votre fichier importé « ${sourceVersion.fileName ?? sourceVersion.label} »`
        : `le visuel ${sourceVersion.label}`;

    this.chatMessages.update((msgs) => [
      ...msgs,
      { author: 'me', text: prompt },
      {
        author: 'ai',
        text: `Nouvelle version ${newLabel} générée à partir de ${originNote} selon votre consigne : « ${prompt} ».`,
      },
    ]);
  }
}
