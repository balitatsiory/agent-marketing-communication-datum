import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { SOCIAL_NETWORKS } from '../../../core/data/social-networks.data';
import { PUBLICATION_FORMAT_LABELS, PublicationFormat } from '../../../core/models/publication';
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
  readonly kind: 'image' | 'video';
  /** URL d'objet, créée à l'import et révoquée au retrait. */
  readonly url: SafeUrl;
  /** Même URL sous forme de chaîne, pour la révoquer. */
  readonly rawUrl: string;
  readonly sizeLabel: string;
  /** Durée formatée, pour une vidéo seulement. */
  readonly durationLabel: string | null;
  readonly durationSeconds: number | null;
}

/** Contrainte de chaque format, affichée sous son nom. */
const FORMAT_HINTS: Readonly<Record<PublicationFormat, string>> = {
  reel: '9:16 vidéo',
  carousel: '2 à 10 médias',
  image: '1:1 · 4:5',
  story: '24 h',
  video: 'Facebook et YouTube',
};

/** Longueur maximale d'une légende Instagram — la plus contraignante. */
const CAPTION_LIMIT = 2200;

/** Décalage d'Antananarivo par rapport à GMT, en heures. */
const LOCAL_UTC_OFFSET = 3;

/**
 * Créer une publication — maquette 3a.
 *
 * Les cinq étapes suivent l'ordre de décision réel : on choisit d'abord
 * le média, puis le format — parce que c'est le média qui dit quels
 * formats sont possibles. Importer une vidéo ferme le carrousel ; une
 * seule image ferme le reel.
 *
 * L'import est réel : les fichiers sont lus par le navigateur, l'aperçu
 * montre le média, et la durée d'une vidéo est relevée sur le fichier.
 * Rien ne quitte le poste — il n'y a pas encore de backend.
 */
@Component({
  selector: 'app-publication-composer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-composer.html',
  styleUrl: './publication-composer.scss',
})
export class PublicationComposer {
  private readonly sanitizer = inject(DomSanitizer);

  protected readonly networks = SOCIAL_NETWORKS.filter((network) => network.isConnected);
  protected readonly formats = Object.keys(PUBLICATION_FORMAT_LABELS) as PublicationFormat[];
  protected readonly formatLabels = PUBLICATION_FORMAT_LABELS;
  protected readonly formatHints = FORMAT_HINTS;
  protected readonly captionLimit = CAPTION_LIMIT;
  protected readonly trail: readonly string[] = ['Publier', 'Créer une publication'];

  protected readonly caption = signal('');
  protected readonly format = signal<PublicationFormat | null>(null);
  protected readonly timing = signal<Timing>('scheduled');
  protected readonly scheduledDate = signal('2026-10-12');
  protected readonly scheduledTime = signal('18:30');

  protected readonly media = signal<readonly MediaItem[]>([]);
  protected readonly isDragOver = signal(false);
  protected readonly importError = signal<string | null>(null);

  /** Pop-up de résumé avant envoi. */
  protected readonly isSummaryOpen = signal(false);
  protected readonly successMessage = signal<string | null>(null);
  protected readonly draftMessage = signal<string | null>(null);

  private nextMediaId = 1;

  constructor() {
    // Les URL d'objet survivent au composant : sans révocation, le
    // navigateur garde les fichiers en mémoire jusqu'au rechargement.
    inject(DestroyRef).onDestroy(() => {
      for (const item of this.media()) URL.revokeObjectURL(item.rawUrl);
    });
  }

  /* ---------- médias ---------- */

  protected readonly imageCount = computed(
    () => this.media().filter((item) => item.kind === 'image').length,
  );
  protected readonly videoCount = computed(
    () => this.media().filter((item) => item.kind === 'video').length,
  );
  protected readonly hasMedia = computed(() => this.media().length > 0);

  /** Première vidéo importée — celle dont on affiche la durée. */
  protected readonly firstVideo = computed(
    () => this.media().find((item) => item.kind === 'video') ?? null,
  );

  /**
   * Formats compatibles avec les médias importés.
   *
   * Sans média, aucun format n'est proposé : le choix n'aurait pas de sens.
   */
  protected readonly availableFormats = computed<readonly PublicationFormat[]>(() => {
    if (!this.hasMedia()) return [];
    if (this.videoCount() > 0) return ['reel', 'video', 'story'];
    if (this.imageCount() > 1) return ['carousel', 'image', 'story'];
    return ['image', 'story'];
  });

  protected isFormatAvailable(format: PublicationFormat): boolean {
    return this.availableFormats().includes(format);
  }

  /** Pourquoi un format est fermé — affiché au survol. */
  protected formatReason(format: PublicationFormat): string {
    if (!this.hasMedia()) return 'Importez un média pour choisir un format.';
    if (this.videoCount() > 0) return 'Une vidéo a été importée : ce format attend des images.';
    if (format === 'reel' || format === 'video') return 'Ce format attend une vidéo.';
    if (format === 'carousel') return 'Un carrousel demande au moins deux images.';
    return '';
  }

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

  private addFiles(files: FileList | null): void {
    if (!files || files.length === 0) return;
    this.importError.set(null);

    const rejected: string[] = [];

    for (const file of Array.from(files)) {
      const isImage = file.type.startsWith('image/');
      const isVideo = file.type.startsWith('video/');
      if (!isImage && !isVideo) {
        rejected.push(file.name);
        continue;
      }
      if (this.media().length >= 10) {
        rejected.push(file.name);
        continue;
      }

      const rawUrl = URL.createObjectURL(file);
      const item: MediaItem = {
        id: this.nextMediaId++,
        name: file.name,
        kind: isVideo ? 'video' : 'image',
        url: this.sanitizer.bypassSecurityTrustUrl(rawUrl),
        rawUrl,
        sizeLabel: formatSize(file.size),
        durationLabel: null,
        durationSeconds: null,
      };
      this.media.update((current) => [...current, item]);
      if (isVideo) this.readDuration(item);
    }

    if (rejected.length) {
      this.importError.set(
        this.media().length >= 10
          ? 'Dix médias au maximum par publication.'
          : `Format non pris en charge : ${rejected.join(', ')}. Images et vidéos seulement.`,
      );
    }

    // Le format retenu peut être devenu impossible.
    this.realignFormat();
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

    this.realignFormat();
  }

  /**
   * Remet le format sur une valeur possible.
   *
   * Retirer un média peut fermer le format retenu : laisser l'étape vide
   * obligerait à y revenir sans le dire.
   */
  private realignFormat(): void {
    const current = this.format();
    const available = this.availableFormats();
    if (current && available.includes(current)) return;
    this.format.set(available[0] ?? null);
  }

  /* ---------- aperçu ---------- */

  protected readonly previewNetwork = signal<SocialNetworkCode>('instagram');

  /** Rapport d'image de l'aperçu, selon le format retenu. */
  protected readonly previewRatio = computed(() => {
    const format = this.format();
    if (format === 'reel' || format === 'story') return '9 / 16';
    if (format === 'video') return '16 / 9';
    return '4 / 5';
  });

  /** Média montré dans l'aperçu : le premier importé. */
  protected readonly previewMedia = computed(() => this.media()[0] ?? null);

  /* ---------- légende et envoi ---------- */

  protected readonly captionLength = computed(() => this.caption().length);
  protected readonly isOverLimit = computed(() => this.captionLength() > CAPTION_LIMIT);

  protected readonly selectedNetworks = signal<ReadonlySet<SocialNetworkCode>>(
    new Set(SOCIAL_NETWORKS.filter((network) => network.isConnected).slice(0, 2).map((n) => n.code)),
  );

  protected readonly canSubmit = computed(
    () =>
      this.hasMedia() &&
      this.format() !== null &&
      this.caption().trim().length > 0 &&
      this.selectedNetworks().size > 0 &&
      !this.isOverLimit(),
  );

  /** Ce qui manque encore, listé sous le bouton d'envoi. */
  protected readonly blockers = computed<readonly string[]>(() => {
    const missing: string[] = [];
    if (!this.hasMedia()) missing.push('un média');
    if (!this.format()) missing.push('un format');
    if (!this.caption().trim()) missing.push('une description');
    if (this.selectedNetworks().size === 0) missing.push('au moins une plateforme');
    if (this.isOverLimit()) missing.push('une légende sous la limite');
    return missing;
  });

  protected toggleNetwork(code: SocialNetworkCode): void {
    this.selectedNetworks.update((current) => {
      const next = new Set(current);
      if (!next.delete(code)) next.add(code);
      return next;
    });
  }

  protected readonly selectedNetworkLabels = computed(() =>
    this.networks
      .filter((network) => this.selectedNetworks().has(network.code))
      .map((network) => network.label),
  );

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

  /**
   * Envoi simulé.
   *
   * Rien ne part : le message de confirmation le dit, plutôt que de
   * laisser croire à une publication réelle.
   */
  protected confirmSend(): void {
    const networks = this.selectedNetworkLabels().join(', ');
    const when = this.timing() === 'now' ? 'dès validation' : this.localSchedule();
    this.isSummaryOpen.set(false);
    this.successMessage.set(
      `Publication envoyée à la validation pour ${networks}, départ ${when} — simulation, rien n'a été publié.`,
    );
  }

  protected saveDraft(): void {
    const pieces = [
      this.media().length
        ? `${this.media().length} média${this.media().length > 1 ? 's' : ''}`
        : 'sans média',
      this.format() ? this.formatLabels[this.format()!].toLowerCase() : 'sans format',
    ];
    this.draftMessage.set(
      `Brouillon enregistré — ${pieces.join(', ')}. Simulation, rien n'a été envoyé.`,
    );
  }
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
