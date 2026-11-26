import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';
import { PublicationsApi, ValidatorOptionDto } from '../../../core/api/publications.api';
import {
  CAPTION_LIMITS,
  FORMAT_BOUNDS,
  MediaKind,
  acceptsFormat,
} from '../../../core/data/platform-formats.data';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { PUBLICATION_FORMAT_LABELS, PublicationFormat } from '../../../core/models/publication';
import {
  MEETING_PUBLICATION_TYPE_LABELS,
  MeetingPublicationType,
  Webinar,
  publicationTypesFor,
} from '../../../core/models/webinar';
import { NotificationBadgeStore } from '../../../core/services/notification-badge-store';
import { WebinarStore } from '../../../core/services/webinar-store';
import { SocialNetworkCode } from '../../../core/models/social-network';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

/** Moment d'envoi. */
type Timing = 'now' | 'scheduled';

/** Un média importé par l'utilisateur. */
interface MediaItem {
  readonly id: number;
  readonly name: string;
  readonly kind: MediaKind;
  /** URL d'objet, créée à l'import et révoquée au retrait. */
  readonly url: SafeUrl;
  /** Même URL sous forme de chaîne, pour la révoquer. */
  readonly rawUrl: string;
  readonly sizeLabel: string;
  /** Taille brute, qui sert à repérer un doublon. */
  readonly sizeBytes: number;
  /** Durée formatée, pour une vidéo seulement. */
  readonly durationLabel: string | null;
  readonly durationSeconds: number | null;
}

/** Décalage d'Antananarivo par rapport à GMT, en heures. */
const LOCAL_UTC_OFFSET = 3;

/**
 * Créer une publication — maquette 3a.
 *
 * L'ordre des quatre étapes est une décision de conception, pas une
 * préférence d'écran : format → réseaux → médias → légendes.
 *
 * Le format vient en premier parce qu'il ne se devine pas. Un Reel et
 * une vidéo de fil portent le même fichier ; une story et un post aussi.
 * Seule l'intention de l'utilisateur les distingue, et aucune détection
 * sur les fichiers déposés ne peut la remplacer. Le format choisi filtre
 * ensuite les réseaux ciblables, et le couple format + réseaux fixe les
 * contraintes du dépôt : nombre de médias, nature de fichier, durée.
 * L'utilisateur ne peut donc pas déposer un fichier qui sera refusé.
 *
 * Une publication ne porte qu'un seul format, commun à tous les réseaux
 * visés : un Reel sur Instagram et un carrousel sur LinkedIn font deux
 * publications. C'est pourquoi changer de format réinitialise tout.
 *
 * L'import est réel : les fichiers sont lus par le navigateur et la durée
 * d'une vidéo est relevée sur le fichier. Rien ne quitte le poste.
 */
@Component({
  selector: 'app-publication-composer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-composer.html',
  styleUrl: './publication-composer.scss',
})
export class PublicationComposer implements OnInit {
  private readonly sanitizer = inject(DomSanitizer);
  private readonly publicationsApi = inject(PublicationsApi);
  private readonly badgeStore = inject(NotificationBadgeStore);

  protected readonly title = signal('');
  protected readonly validators = signal<readonly ValidatorOptionDto[]>([]);
  protected readonly selectedValidatorId = signal<string>('');
  protected readonly createdPublicationId = signal<number | null>(null);
  protected readonly isSending = signal(false);
  protected readonly sendError = signal<string | null>(null);

  ngOnInit(): void {
    void this.publicationsApi
      .validators()
      .then((list) => this.validators.set(list))
      .catch(() => this.validators.set([]));
  }

  protected readonly networks = SOCIAL_NETWORKS.filter((network) => network.isConnected);
  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly bounds = FORMAT_BOUNDS;
  protected readonly trail: readonly string[] = ['Publier', 'Créer une publication'];

  /* ---------- 1 · format ---------- */

  protected readonly format = signal<PublicationFormat | null>(null);

  /** Format en attente de confirmation, quand le changement efface du travail. */
  protected readonly pendingFormat = signal<PublicationFormat | null>(null);
  protected readonly resetNotice = signal<string | null>(null);

  /** Bornes du format retenu. Sans format, rien n'est permis. */
  protected readonly activeBounds = computed(() => {
    const format = this.format();
    return format ? FORMAT_BOUNDS[format] : null;
  });

  /** Ce format attend-il des médias ? « Texte seul » n'en attend aucun. */
  protected readonly wantsMedia = computed(() => (this.activeBounds()?.maxMediaCount ?? 0) > 0);

  /** Types de fichiers ouverts au sélecteur, selon le format. */
  protected readonly acceptAttribute = computed(() => {
    const accepts = this.activeBounds()?.accepts ?? [];
    const parts: string[] = [];
    if (accepts.includes('image')) parts.push('image/*');
    if (accepts.includes('video')) parts.push('video/*');
    if (accepts.includes('document')) parts.push('application/pdf');
    return parts.join(',');
  });

  /**
   * Choisit un format.
   *
   * Changer de format réinitialise les réseaux, les médias et les
   * légendes : ils dépendent tous du format. On demande confirmation
   * seulement s'il y a quelque chose à perdre — sinon le clic serait
   * ralenti pour rien.
   */
  protected chooseFormat(next: PublicationFormat): void {
    if (this.format() === next) return;
    if (this.format() === null || !this.hasWorkToLose()) {
      this.applyFormat(next);
      return;
    }
    this.pendingFormat.set(next);
  }

  protected confirmFormatChange(): void {
    const next = this.pendingFormat();
    if (!next) return;
    this.applyFormat(next);
    this.pendingFormat.set(null);
    this.resetNotice.set(
      `Format passé à « ${this.formatLabels[next].toLowerCase()} » : réseaux, médias et légendes ont été réinitialisés.`,
    );
  }

  protected cancelFormatChange(): void {
    this.pendingFormat.set(null);
  }

  /** Y a-t-il une saisie que le changement de format effacerait ? */
  private hasWorkToLose(): boolean {
    return (
      this.media().length > 0 ||
      this.selectedNetworks().size > 0 ||
      Object.values(this.captions()).some((text) => text.trim().length > 0)
    );
  }

  private applyFormat(next: PublicationFormat): void {
    for (const item of this.media()) URL.revokeObjectURL(item.rawUrl);
    this.media.set([]);
    this.selectedNetworks.set(new Set());
    this.captions.set({});
    this.importError.set(null);
    this.format.set(next);
  }

  /* ---------- 2 · réseaux ---------- */

  protected readonly selectedNetworks = signal<ReadonlySet<SocialNetworkCode>>(new Set());

  /** Ce réseau accepte-t-il le format retenu ? */
  protected isNetworkAvailable(code: SocialNetworkCode): boolean {
    const format = this.format();
    return format !== null && acceptsFormat(code, format);
  }

  /** Pourquoi un réseau est fermé — affiché à côté de son nom. */
  protected networkReason(code: SocialNetworkCode): string {
    const format = this.format();
    if (!format) return 'Choisissez un format.';
    return `${this.formatLabels[format]} n'est pas accepté ici.`;
  }

  protected toggleNetwork(code: SocialNetworkCode): void {
    if (!this.isNetworkAvailable(code)) return;
    this.selectedNetworks.update((current) => {
      const next = new Set(current);
      if (!next.delete(code)) next.add(code);
      return next;
    });
    // L'aperçu doit rester sur un réseau réellement visé.
    const selected = [...this.selectedNetworks()];
    if (selected.length && !this.selectedNetworks().has(this.previewNetwork())) {
      this.previewNetwork.set(selected[0]);
    }
  }

  protected readonly selectedNetworkList = computed(() =>
    this.networks.filter((network) => this.selectedNetworks().has(network.code)),
  );

  protected readonly selectedNetworkLabels = computed(() =>
    this.selectedNetworkList().map((network) => network.label),
  );

  /* ---------- 3 · médias ---------- */

  protected readonly media = signal<readonly MediaItem[]>([]);
  protected readonly isDragOver = signal(false);
  protected readonly importError = signal<string | null>(null);
  private nextMediaId = 1;
  private dragIndex: number | null = null;

  constructor() {
    // Les URL d'objet survivent au composant : sans révocation, le
    // navigateur garde les fichiers en mémoire jusqu'au rechargement.
    inject(DestroyRef).onDestroy(() => {
      for (const item of this.media()) URL.revokeObjectURL(item.rawUrl);
    });
  }

  protected readonly hasMedia = computed(() => this.media().length > 0);
  protected readonly mediaCount = computed(() => this.media().length);

  /** Place restante avant le plafond du format. */
  protected readonly remainingSlots = computed(() => {
    const max = this.activeBounds()?.maxMediaCount ?? 0;
    return Math.max(0, max - this.media().length);
  });

  /** Première vidéo importée — celle dont on affiche la durée. */
  protected readonly firstVideo = computed(
    () => this.media().find((item) => item.kind === 'video') ?? null,
  );

  protected onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(input.files);
    // Remettre le champ à zéro : sans cela, réimporter le même fichier
    // ne déclenche pas d'événement.
    input.value = '';
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    this.addFiles(event.dataTransfer?.files ?? null);
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  protected onDragLeave(): void {
    this.isDragOver.set(false);
  }

  /**
   * Ajoute des fichiers, en appliquant les règles du format.
   *
   * Trois refus possibles, dits séparément : nature de fichier non
   * attendue par le format, plafond atteint, et doublon. Un même média ne
   * peut pas figurer deux fois dans un carrousel — la base l'interdit par
   * une contrainte d'unicité, l'écran le dit avant.
   */
  private addFiles(files: FileList | null): void {
    const bounds = this.activeBounds();
    if (!bounds || !files || files.length === 0) return;
    this.importError.set(null);

    const wrongKind: string[] = [];
    const duplicates: string[] = [];
    let overflow = false;

    for (const file of Array.from(files)) {
      const kind = detectKind(file);
      if (!kind || !bounds.accepts.includes(kind)) {
        wrongKind.push(file.name);
        continue;
      }
      if (this.media().some((item) => item.name === file.name && item.sizeBytes === file.size)) {
        duplicates.push(file.name);
        continue;
      }
      if (this.media().length >= bounds.maxMediaCount) {
        overflow = true;
        continue;
      }

      const rawUrl = URL.createObjectURL(file);
      const item: MediaItem = {
        id: this.nextMediaId++,
        name: file.name,
        kind,
        url: this.sanitizer.bypassSecurityTrustUrl(rawUrl),
        rawUrl,
        sizeLabel: formatSize(file.size),
        sizeBytes: file.size,
        durationLabel: null,
        durationSeconds: null,
      };
      this.media.update((current) => [...current, item]);
      if (kind === 'video') this.readDuration(item);
    }

    const messages: string[] = [];
    if (wrongKind.length) {
      messages.push(
        `${wrongKind.join(', ')} — ce format attend ${describeAccepts(bounds.accepts)}.`,
      );
    }
    if (duplicates.length) {
      messages.push(
        `${duplicates.join(', ')} — déjà dans la sélection. Un même média ne peut figurer qu'une fois.`,
      );
    }
    if (overflow) {
      messages.push(
        `Plafond atteint : ${bounds.maxMediaCount} média${bounds.maxMediaCount > 1 ? 's' : ''} au maximum pour ce format.`,
      );
    }
    this.importError.set(messages.length ? messages.join(' ') : null);
  }

  /** Relève la durée réelle du fichier vidéo, sans le lire. */
  private readDuration(item: MediaItem): void {
    const probe = document.createElement('video');
    probe.preload = 'metadata';
    probe.onloadedmetadata = () => {
      const seconds = Math.round(probe.duration);
      this.media.update((current) =>
        current.map((entry) =>
          entry.id === item.id
            ? { ...entry, durationSeconds: seconds, durationLabel: formatDuration(seconds) }
            : entry,
        ),
      );
    };
    probe.src = item.rawUrl;
  }

  protected removeMedia(id: number): void {
    const item = this.media().find((entry) => entry.id === id);
    if (item) URL.revokeObjectURL(item.rawUrl);
    this.media.update((current) => current.filter((entry) => entry.id !== id));
    this.importError.set(null);
  }

  /**
   * Déplace un média dans l'ordre du carrousel.
   *
   * C'est ce geste qui fixe `carousel_position` : la position d'une
   * vignette est son rang dans la liste, à partir de 1.
   */
  protected moveMedia(from: number, to: number): void {
    if (to < 0 || to >= this.media().length || from === to) return;
    this.media.update((current) => {
      const next = [...current];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }

  protected onTileDragStart(index: number): void {
    this.dragIndex = index;
  }

  protected onTileDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  protected onTileDrop(index: number, event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    if (this.dragIndex !== null) this.moveMedia(this.dragIndex, index);
    this.dragIndex = null;
  }

  /* ---------- 4 · légendes ---------- */

  /**
   * Une légende par réseau.
   *
   * La légende vit sur la cible, pas sur la publication : les limites de
   * longueur diffèrent d'un réseau à l'autre, et une proposition générée
   * par l'IA est produite par plateforme.
   */
  protected readonly captions = signal<Readonly<Partial<Record<SocialNetworkCode, string>>>>({});

  protected captionFor(code: SocialNetworkCode): string {
    return this.captions()[code] ?? '';
  }

  protected setCaption(code: SocialNetworkCode, text: string): void {
    this.captions.update((current) => ({ ...current, [code]: text }));
  }

  protected captionLimit(code: SocialNetworkCode): number {
    return CAPTION_LIMITS[code];
  }

  protected isCaptionOverLimit(code: SocialNetworkCode): boolean {
    return this.captionFor(code).length > CAPTION_LIMITS[code];
  }

  /** Recopie une légende sur tous les autres réseaux visés. */
  protected copyCaptionToAll(source: SocialNetworkCode): void {
    const text = this.captionFor(source);
    this.captions.update((current) => {
      const next = { ...current };
      for (const network of this.selectedNetworkList()) next[network.code] = text;
      return next;
    });
  }

  protected readonly hasEmptyCaption = computed(() =>
    this.selectedNetworkList().some((network) => !this.captionFor(network.code).trim()),
  );

  protected readonly hasCaptionOverLimit = computed(() =>
    this.selectedNetworkList().some((network) => this.isCaptionOverLimit(network.code)),
  );

  /* ---------- aperçu ---------- */

  protected readonly previewNetwork = signal<SocialNetworkCode>('instagram');

  /** Rapport d'image de l'aperçu, selon le format retenu. */
  protected readonly previewRatio = computed(() => {
    const format = this.format();
    if (format === 'reel' || format === 'story') return '9 / 16';
    if (format === 'video') return '16 / 9';
    return '4 / 5';
  });

  /** Média montré dans l'aperçu : le premier de l'ordre retenu. */
  protected readonly previewMedia = computed(() => this.media()[0] ?? null);

  protected readonly previewCaption = computed(() => this.captionFor(this.previewNetwork()));

  /* ---------- événement lié ---------- */

  /**
   * Lien facultatif avec un événement — une ligne de `meeting_publications`.
   *
   * L'ordre est celui de la décision du 11/11/2026 : on choisit l'événement
   * d'abord, puis le type de publication. Le type reste grisé tant
   * qu'aucun événement n'est choisi, et ses valeurs dépendent du statut de
   * l'événement : promotion avant la séance, compte rendu ou rediffusion après.
   * La vidéo d'une rediffusion s'importe à l'étape « Médias », comme toute vidéo.
   */
  private readonly webinarStore = inject(WebinarStore);
  protected readonly typeLabels = MEETING_PUBLICATION_TYPE_LABELS;
  protected readonly webinarOptions = this.webinarStore.everything;
  protected readonly linkedWebinarId = signal<number | null>(null);
  protected readonly linkedType = signal<MeetingPublicationType | null>(null);

  protected readonly linkedWebinar = computed<Webinar | null>(() => {
    const id = this.linkedWebinarId();
    return id === null ? null : (this.webinarStore.findById(id) ?? null);
  });

  /** Valeur de la liste déroulante, qui ne manipule que des chaînes. */
  protected readonly linkedWebinarKey = computed(() => String(this.linkedWebinarId() ?? ''));

  protected readonly availableTypes = computed<readonly MeetingPublicationType[]>(() => {
    const webinar = this.linkedWebinar();
    return webinar ? publicationTypesFor(webinar.status) : [];
  });

  /** Fragment ajouté au message de confirmation quand un événement est lié. */
  protected readonly linkedSummary = computed(() => {
    const webinar = this.linkedWebinar();
    const type = this.linkedType();
    return webinar && type
      ? `, liée à « ${webinar.title} » (${MEETING_PUBLICATION_TYPE_LABELS[type].toLowerCase()})`
      : '';
  });

  protected chooseWebinar(value: string): void {
    const id = value === '' ? null : Number(value);
    this.linkedWebinarId.set(id);
    const webinar = id === null ? null : (this.webinarStore.findById(id) ?? null);
    const types = webinar ? publicationTypesFor(webinar.status) : [];
    // Un seul type possible : il est présélectionné. Sinon, l'utilisateur choisit.
    this.linkedType.set(types.length === 1 ? types[0] : null);
  }

  protected chooseType(value: string): void {
    this.linkedType.set(value === '' ? null : (value as MeetingPublicationType));
  }

  protected webinarOptionLabel(webinar: Webinar): string {
    const when = webinar.date ? `${webinar.date.day} ${webinar.date.month.toLowerCase()}` : 'sans date';
    const state = webinar.status === 'draft' ? ' (brouillon)' : webinar.status === 'past' ? ' (passé)' : '';
    return `${webinar.title} — ${when}${state}`;
  }

  /* ---------- programmation et envoi ---------- */

  protected readonly timing = signal<Timing>('scheduled');
  protected readonly scheduledDate = signal('2026-10-12');
  protected readonly scheduledTime = signal('18:30');

  protected readonly isSummaryOpen = signal(false);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly draftMessage = signal<string | null>(null);

  protected readonly canSubmit = computed(() => this.blockers().length === 0);

  /** Ce qui manque encore, listé sous le bouton d'envoi. */
  protected readonly blockers = computed<readonly string[]>(() => {
    const bounds = this.activeBounds();
    const missing: string[] = [];
    if (!bounds) return ['un format'];
    if (this.selectedNetworks().size === 0) missing.push('au moins un réseau');
    if (this.mediaCount() < bounds.minMediaCount) {
      const need = bounds.minMediaCount - this.mediaCount();
      missing.push(`${need} média${need > 1 ? 's' : ''} de plus`);
    }
    if (this.selectedNetworks().size > 0 && this.hasEmptyCaption()) {
      missing.push('une légende pour chaque réseau');
    }
    if (this.hasCaptionOverLimit()) missing.push('des légendes sous la limite');
    if (this.linkedWebinarId() !== null && this.linkedType() === null) {
      missing.push("le type de publication pour l'événement lié");
    }
    return missing;
  });

  /** Date et heure de programmation, telles que saisies (UTC+3). */
  protected readonly localSchedule = computed(() => {
    if (this.timing() === 'now') return 'dès validation';
    return `${formatDate(this.scheduledDate())} à ${this.scheduledTime()}`;
  });

  /**
   * La même échéance exprimée en GMT.
   *
   * Les plateformes raisonnent en UTC : afficher les deux évite de
   * découvrir après coup qu'une publication est partie trois heures trop
   * tôt.
   */
  protected readonly gmtSchedule = computed(() => {
    if (this.timing() === 'now') return null;
    const [year, month, day] = this.scheduledDate().split('-').map(Number);
    const [hour, minute] = this.scheduledTime().split(':').map(Number);
    if ([year, month, day, hour, minute].some(Number.isNaN)) return null;
    const utc = new Date(Date.UTC(year, month - 1, day, hour - LOCAL_UTC_OFFSET, minute));
    return `${formatDate(utc.toISOString().slice(0, 10))} à ${utc
      .toISOString()
      .slice(11, 16)} GMT`;
  });

  protected openSummary(): void {
    if (!this.canSubmit()) return;
    this.successMessage.set(null);
    this.isSummaryOpen.set(true);
  }

  protected closeSummary(): void {
    this.isSummaryOpen.set(false);
  }

  protected async confirmSend(): Promise<void> {
    if (this.isSending()) return;
    const format = this.format();
    if (!format) return;

    this.isSending.set(true);
    this.sendError.set(null);
    this.draftMessage.set(null);
    try {
      const created = await this.publicationsApi.create(this.buildPayload(true));
      this.isSummaryOpen.set(false);
      this.createdPublicationId.set(created.id_publications);
      const networks = this.selectedNetworkLabels().join(', ');
      const when = this.timing() === 'now' ? 'dès validation' : this.localSchedule();
      this.successMessage.set(
        `Publication « ${created.title} » envoyée à la validation pour ${networks}, départ ${when}${this.linkedSummary()}. Le validateur a reçu une notification.`,
      );
      void this.badgeStore.refresh();
    } catch {
      this.isSummaryOpen.set(false);
      this.sendError.set("Impossible d'envoyer la publication à la validation.");
    } finally {
      this.isSending.set(false);
    }
  }

  protected async saveDraft(): Promise<void> {
    if (this.isSending()) return;
    const format = this.format() ?? 'text';
    const networks = [...this.selectedNetworks()];
    if (networks.length === 0) {
      this.draftMessage.set('Choisissez au moins un réseau avant d’enregistrer le brouillon.');
      return;
    }

    this.isSending.set(true);
    this.sendError.set(null);
    this.successMessage.set(null);
    try {
      const created = await this.publicationsApi.create(this.buildPayload(false, format));
      this.createdPublicationId.set(created.id_publications);
      this.draftMessage.set(`Brouillon « ${created.title} » enregistré.`);
    } catch {
      this.sendError.set("Impossible d'enregistrer le brouillon.");
    } finally {
      this.isSending.set(false);
    }
  }

  private buildPayload(submitForValidation: boolean, fallbackFormat?: PublicationFormat) {
    const format = this.format() ?? fallbackFormat ?? 'text';
    const networks = [...this.selectedNetworks()];
    const captionsMap: Record<string, string> = {};
    for (const code of networks) {
      captionsMap[code] = this.captionFor(code);
    }
    const primaryCaption =
      networks.map((code) => this.captionFor(code).trim()).find((text) => text.length > 0) ?? '';
    const derivedTitle =
      this.title().trim() ||
      primaryCaption.split('\n')[0].slice(0, 80).trim() ||
      `Publication ${this.formatLabels[format]}`;

    let scheduledIso: string | null = null;
    if (this.timing() === 'scheduled') {
      const [year, month, day] = this.scheduledDate().split('-').map(Number);
      const [hour, minute] = this.scheduledTime().split(':').map(Number);
      if (![year, month, day, hour, minute].some(Number.isNaN)) {
        scheduledIso = new Date(
          Date.UTC(year, month - 1, day, hour - LOCAL_UTC_OFFSET, minute),
        ).toISOString();
      }
    }

    const validatorId = this.selectedValidatorId() ? Number(this.selectedValidatorId()) : null;

    return {
      title: derivedTitle,
      caption: primaryCaption,
      captions_by_platform: captionsMap,
      format_code: format,
      platform_codes: networks,
      media_items: this.media().map((item) => ({
        name: item.name,
        kind: item.kind,
        size_label: item.sizeLabel,
        duration_label: item.durationLabel,
      })),
      scheduled_at: scheduledIso,
      id_users_validator: validatorId,
      submit_for_validation: submitForValidation,
    };
  }
}

/** Nature d'un fichier, d'après son type MIME. */
function detectKind(file: File): MediaKind | null {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type.startsWith('video/')) return 'video';
  if (file.type === 'application/pdf') return 'document';
  return null;
}

/** Phrase disant ce qu'un format accepte. */
function describeAccepts(accepts: readonly MediaKind[]): string {
  const words = accepts.map((kind) =>
    kind === 'image' ? 'des images' : kind === 'video' ? 'une vidéo' : 'un PDF',
  );
  if (words.length === 0) return 'aucun média';
  if (words.length === 1) return words[0];
  return `${words.slice(0, -1).join(', ')} ou ${words[words.length - 1]}`;
}

/** Taille de fichier lisible. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
}

/** Durée en minutes et secondes. */
function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—';
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes} min ${String(rest).padStart(2, '0')} s` : `${rest} s`;
}

/** Date au format « 12 octobre 2026 ». */
function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
