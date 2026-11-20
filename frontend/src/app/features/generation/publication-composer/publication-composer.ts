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
import { RouterLink } from '@angular/router';

import { toApiError } from '../../../core/api/api-error';
import { MediaApi } from '../../../core/api/media.api';
import {
  PublicationDto,
  PublicationFormatDto,
  PublicationsApi,
} from '../../../core/api/publications.api';
import {
  SocialAccountDto,
  SocialAccountsApi,
  SocialPlatformDto,
} from '../../../core/api/social-accounts.api';
import { FORMAT_BOUNDS, MediaKind } from '../../../core/data/platform-formats.data';
import { PublicationFormat } from '../../../core/models/publication';
import { SocialNetworkCode } from '../../../core/models/social-network';
import {
  MEETING_PUBLICATION_TYPE_LABELS,
  MeetingPublicationType,
  Webinar,
  publicationTypesFor,
} from '../../../core/models/webinar';
import { Session } from '../../../core/services/session';
import { WebinarStore } from '../../../core/services/webinar-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';
import { NetworkLogo } from '../../../shared/network-logo/network-logo';

type Timing = 'now' | 'scheduled';

interface MediaItem {
  readonly id: number;
  readonly file: File;
  readonly name: string;
  readonly kind: MediaKind;
  readonly url: SafeUrl;
  readonly rawUrl: string;
  readonly sizeLabel: string;
  readonly sizeBytes: number;
  readonly durationLabel: string | null;
  readonly durationSeconds: number | null;
}

const LOCAL_UTC_OFFSET = 3;
const RESEAUX_CONNUS: ReadonlySet<string> = new Set([
  'facebook',
  'instagram',
  'linkedin',
  'youtube',
  'tiktok',
]);

function dateDemainIso(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}

/**
 * Créer une publication (/publications/nouvelle) — Module 08 branché sur l'API.
 *
 * Ordre imposé par la conception : format → comptes actifs → médias → légendes →
 * soumission à la validation → approbation humaine → diffusion réelle (Facebook).
 */
@Component({
  selector: 'app-publication-composer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, Topbar, Icon, NetworkLogo],
  templateUrl: './publication-composer.html',
  styleUrl: './publication-composer.scss',
})
export class PublicationComposer {
  private readonly sanitizer = inject(DomSanitizer);
  private readonly publicationsApi = inject(PublicationsApi);
  private readonly socialAccountsApi = inject(SocialAccountsApi);
  private readonly mediaApi = inject(MediaApi);
  private readonly session = inject(Session);

  protected readonly trail: readonly string[] = ['Publier', 'Créer une publication'];

  /* ---------- données chargées depuis l'API ---------- */

  protected readonly formatsApi = signal<readonly PublicationFormatDto[]>([]);
  protected readonly plateformesApi = signal<readonly SocialPlatformDto[]>([]);
  protected readonly comptesActifs = signal<readonly SocialAccountDto[]>([]);
  protected readonly chargementInit = signal(true);
  protected readonly erreurApi = signal<string | null>(null);

  protected readonly peutCreer = computed(() => this.session.has('create_publications'));
  protected readonly peutRelire = computed(() => this.session.has('review_publications'));
  protected readonly peutPublier = computed(() => this.session.has('publish_publications'));

  protected readonly plateformesParCode = computed(() => {
    const carte = new Map<string, SocialPlatformDto>();
    for (const p of this.plateformesApi()) carte.set(p.code, p);
    return carte;
  });

  /* ---------- 1 · format ---------- */

  protected readonly format = signal<PublicationFormatDto | null>(null);
  protected readonly pendingFormat = signal<PublicationFormatDto | null>(null);
  protected readonly resetNotice = signal<string | null>(null);

  protected readonly activeAccepts = computed<readonly MediaKind[]>(() => {
    const f = this.format();
    if (!f) return [];
    const borne = FORMAT_BOUNDS[f.code as PublicationFormat];
    return borne ? borne.accepts : ['image'];
  });

  protected readonly wantsMedia = computed(() => (this.format()?.max_media_count ?? 0) > 0);

  protected readonly acceptAttribute = computed(() => {
    const accepts = this.activeAccepts();
    const parts: string[] = [];
    if (accepts.includes('image')) parts.push('image/*');
    if (accepts.includes('video')) parts.push('video/*');
    if (accepts.includes('document')) parts.push('application/pdf');
    return parts.join(',');
  });

  protected hintFormat(f: PublicationFormatDto): string {
    const borne = FORMAT_BOUNDS[f.code as PublicationFormat];
    if (borne) return borne.hint;
    if (f.max_media_count === 0) return 'sans média';
    if (f.min_media_count === f.max_media_count) return `${f.max_media_count} média`;
    return `${f.min_media_count} à ${f.max_media_count} médias`;
  }

  protected chooseFormat(next: PublicationFormatDto): void {
    if (this.format()?.code === next.code) return;
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
      `Format passé à « ${next.label.toLowerCase()} » : comptes, médias et légendes ont été réinitialisés.`,
    );
  }

  protected cancelFormatChange(): void {
    this.pendingFormat.set(null);
  }

  private hasWorkToLose(): boolean {
    return (
      this.media().length > 0 ||
      this.selectedAccountIds().size > 0 ||
      Object.values(this.captions()).some((text) => (text ?? '').trim().length > 0)
    );
  }

  private applyFormat(next: PublicationFormatDto): void {
    for (const item of this.media()) URL.revokeObjectURL(item.rawUrl);
    this.media.set([]);
    this.selectedAccountIds.set(new Set());
    this.captions.set({});
    this.importError.set(null);
    this.format.set(next);
  }

  /* ---------- 2 · comptes réseaux sociaux actifs ---------- */

  protected readonly selectedAccountIds = signal<ReadonlySet<number>>(new Set());

  protected isAccountAvailable(compte: SocialAccountDto): boolean {
    const fmt = this.format();
    return fmt !== null && fmt.platforms.includes(compte.platform_code);
  }

  protected accountReason(compte: SocialAccountDto): string {
    const fmt = this.format();
    if (!fmt) return 'Choisissez un format.';
    return `${fmt.label} n'est pas accepté sur ${compte.platform_label}.`;
  }

  protected toggleAccount(compte: SocialAccountDto): void {
    if (!this.isAccountAvailable(compte)) return;
    this.selectedAccountIds.update((current) => {
      const next = new Set(current);
      if (!next.delete(compte.id_social_accounts)) next.add(compte.id_social_accounts);
      return next;
    });
    const selected = this.selectedAccounts();
    if (selected.length && !this.selectedAccountIds().has(this.previewAccountId() ?? -1)) {
      this.previewAccountId.set(selected[0].id_social_accounts);
    }
  }

  protected readonly selectedAccounts = computed(() =>
    this.comptesActifs().filter((c) => this.selectedAccountIds().has(c.id_social_accounts)),
  );

  protected codeReseau(code: string): SocialNetworkCode {
    return (RESEAUX_CONNUS.has(code) ? code : 'facebook') as SocialNetworkCode;
  }

  /* ---------- 3 · médias ---------- */

  protected readonly media = signal<readonly MediaItem[]>([]);
  protected readonly isDragOver = signal(false);
  protected readonly importError = signal<string | null>(null);
  private nextMediaId = 1;
  private dragIndex: number | null = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      for (const item of this.media()) URL.revokeObjectURL(item.rawUrl);
    });
    void this.chargerReferentiels();
  }

  protected async chargerReferentiels(): Promise<void> {
    this.chargementInit.set(true);
    this.erreurApi.set(null);
    try {
      const [formats, plateformes, comptes] = await Promise.all([
        this.publicationsApi.formats(),
        this.socialAccountsApi.platforms(),
        this.socialAccountsApi.list(),
      ]);
      this.formatsApi.set(formats);
      this.plateformesApi.set(plateformes);
      this.comptesActifs.set(comptes.filter((c) => c.status_code === 'active'));
    } catch (err) {
      this.erreurApi.set(toApiError(err).message);
    } finally {
      this.chargementInit.set(false);
    }
  }

  protected readonly hasMedia = computed(() => this.media().length > 0);
  protected readonly mediaCount = computed(() => this.media().length);

  protected readonly remainingSlots = computed(() => {
    const max = this.format()?.max_media_count ?? 0;
    return Math.max(0, max - this.media().length);
  });

  protected readonly firstVideo = computed(
    () => this.media().find((item) => item.kind === 'video') ?? null,
  );

  protected onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.addFiles(input.files);
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
    const fmt = this.format();
    if (!fmt || !files || files.length === 0) return;
    this.importError.set(null);

    const accepts = this.activeAccepts();
    const wrongKind: string[] = [];
    const duplicates: string[] = [];
    let overflow = false;

    for (const file of Array.from(files)) {
      const kind = detectKind(file);
      if (!kind || !accepts.includes(kind)) {
        wrongKind.push(file.name);
        continue;
      }
      if (this.media().some((item) => item.name === file.name && item.sizeBytes === file.size)) {
        duplicates.push(file.name);
        continue;
      }
      if (this.media().length >= fmt.max_media_count) {
        overflow = true;
        continue;
      }

      const rawUrl = URL.createObjectURL(file);
      const item: MediaItem = {
        id: this.nextMediaId++,
        file,
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
      messages.push(`${wrongKind.join(', ')} — ce format attend ${describeAccepts(accepts)}.`);
    }
    if (duplicates.length) {
      messages.push(`${duplicates.join(', ')} — déjà dans la sélection.`);
    }
    if (overflow) {
      messages.push(
        `Plafond atteint : ${fmt.max_media_count} média${fmt.max_media_count > 1 ? 's' : ''} au maximum.`,
      );
    }
    this.importError.set(messages.length ? messages.join(' ') : null);
  }

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

  /* ---------- 4 · légendes (par compte cible) ---------- */

  protected readonly captions = signal<Readonly<Partial<Record<number, string>>>>({});

  protected captionFor(accountId: number): string {
    return this.captions()[accountId] ?? '';
  }

  protected setCaption(accountId: number, text: string): void {
    this.captions.update((current) => ({ ...current, [accountId]: text }));
  }

  protected captionLimit(platformCode: string): number {
    return this.plateformesParCode().get(platformCode)?.max_description_length ?? 2200;
  }

  protected isCaptionOverLimit(compte: SocialAccountDto): boolean {
    return this.captionFor(compte.id_social_accounts).length > this.captionLimit(compte.platform_code);
  }

  protected copyCaptionToAll(sourceAccountId: number): void {
    const text = this.captionFor(sourceAccountId);
    this.captions.update((current) => {
      const next = { ...current };
      for (const acc of this.selectedAccounts()) next[acc.id_social_accounts] = text;
      return next;
    });
  }

  protected readonly hasEmptyCaption = computed(() =>
    this.selectedAccounts().some((acc) => !this.captionFor(acc.id_social_accounts).trim()),
  );

  protected readonly hasCaptionOverLimit = computed(() =>
    this.selectedAccounts().some((acc) => this.isCaptionOverLimit(acc)),
  );

  /* ---------- aperçu ---------- */

  protected readonly previewAccountId = signal<number | null>(null);

  protected readonly previewRatio = computed(() => {
    const code = this.format()?.code;
    if (code === 'reel' || code === 'story') return '9 / 16';
    if (code === 'video') return '16 / 9';
    return '4 / 5';
  });

  protected readonly previewMedia = computed(() => this.media()[0] ?? null);

  protected readonly previewCaption = computed(() => {
    const id = this.previewAccountId();
    return id !== null ? this.captionFor(id) : '';
  });

  /* ---------- 5 · événement lié (maquette conservée) ---------- */

  private readonly webinarStore = inject(WebinarStore);
  protected readonly typeLabels = MEETING_PUBLICATION_TYPE_LABELS;
  protected readonly webinarOptions = this.webinarStore.everything;
  protected readonly linkedWebinarId = signal<number | null>(null);
  protected readonly linkedType = signal<MeetingPublicationType | null>(null);

  protected readonly linkedWebinar = computed<Webinar | null>(() => {
    const id = this.linkedWebinarId();
    return id === null ? null : (this.webinarStore.findById(id) ?? null);
  });

  protected readonly linkedWebinarKey = computed(() => String(this.linkedWebinarId() ?? ''));

  protected readonly availableTypes = computed<readonly MeetingPublicationType[]>(() => {
    const webinar = this.linkedWebinar();
    return webinar ? publicationTypesFor(webinar.status) : [];
  });

  protected chooseWebinar(value: string): void {
    const id = value === '' ? null : Number(value);
    this.linkedWebinarId.set(id);
    const webinar = id === null ? null : (this.webinarStore.findById(id) ?? null);
    const types = webinar ? publicationTypesFor(webinar.status) : [];
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

  /* ---------- 6 · programmation, soumission, validation et diffusion ---------- */

  protected readonly timing = signal<Timing>('now');
  protected readonly scheduledDate = signal(dateDemainIso());
  protected readonly scheduledTime = signal('18:30');

  protected readonly isSummaryOpen = signal(false);
  protected readonly envoiEnCours = signal(false);
  protected readonly actionPubEnCours = signal<'approve' | 'publish' | null>(null);
  protected readonly publicationCreee = signal<PublicationDto | null>(null);
  protected readonly successMessage = signal<string | null>(null);

  protected readonly canSubmit = computed(
    () => this.peutCreer() && this.blockers().length === 0 && !this.envoiEnCours(),
  );

  protected readonly blockers = computed<readonly string[]>(() => {
    const fmt = this.format();
    const missing: string[] = [];
    if (!fmt) return ['un format'];
    if (this.selectedAccountIds().size === 0) missing.push('au moins un compte actif');
    if (this.mediaCount() < fmt.min_media_count) {
      const need = fmt.min_media_count - this.mediaCount();
      missing.push(`${need} média${need > 1 ? 's' : ''} de plus`);
    }
    if (this.selectedAccountIds().size > 0 && this.hasEmptyCaption()) {
      missing.push('une légende pour chaque compte');
    }
    if (this.hasCaptionOverLimit()) missing.push('des légendes sous la limite');
    if (this.linkedWebinarId() !== null && this.linkedType() === null) {
      missing.push("le type de publication pour l'événement lié");
    }
    return missing;
  });

  protected readonly localSchedule = computed(() => {
    if (this.timing() === 'now') return 'dès validation';
    return `${formatDate(this.scheduledDate())} à ${this.scheduledTime()}`;
  });

  protected readonly gmtSchedule = computed(() => {
    if (this.timing() === 'now') return null;
    const utc = this.scheduledIsoUtc();
    if (!utc) return null;
    return `${formatDate(utc.slice(0, 10))} à ${utc.slice(11, 16)} GMT`;
  });

  private scheduledIsoUtc(): string {
    if (this.timing() === 'now') {
      return new Date().toISOString();
    }
    const [year, month, day] = this.scheduledDate().split('-').map(Number);
    const [hour, minute] = this.scheduledTime().split(':').map(Number);
    if ([year, month, day, hour, minute].some(Number.isNaN)) {
      return new Date().toISOString();
    }
    return new Date(Date.UTC(year, month - 1, day, hour - LOCAL_UTC_OFFSET, minute)).toISOString();
  }

  protected openSummary(): void {
    if (!this.canSubmit()) return;
    this.erreurApi.set(null);
    this.isSummaryOpen.set(true);
  }

  protected closeSummary(): void {
    if (this.envoiEnCours()) return;
    this.isSummaryOpen.set(false);
  }

  /** Upload réel des médias via /api/v1/media puis création de la publication via /api/v1/publications. */
  protected async confirmSend(): Promise<void> {
    const fmt = this.format();
    if (!fmt || !this.canSubmit()) return;

    this.envoiEnCours.set(true);
    this.erreurApi.set(null);
    this.successMessage.set(null);

    try {
      const mediaIds: number[] = [];
      for (const item of this.media()) {
        const uploaded = await this.mediaApi.upload(item.file, item.name);
        mediaIds.push(uploaded.id_media);
      }

      const scheduledAt = this.scheduledIsoUtc();
      const targets = this.selectedAccounts().map((acc) => ({
        id_social_accounts: acc.id_social_accounts,
        description: this.captionFor(acc.id_social_accounts).trim(),
        scheduled_at: scheduledAt,
      }));

      const cree = await this.publicationsApi.create({
        format_code: fmt.code,
        media_ids: mediaIds,
        targets,
      });

      this.publicationCreee.set(cree);
      this.isSummaryOpen.set(false);
      this.successMessage.set(
        `Publication #${cree.id_publications} enregistrée et soumise à la validation humaine.`,
      );
    } catch (err) {
      this.erreurApi.set(toApiError(err).message);
      this.isSummaryOpen.set(false);
    } finally {
      this.envoiEnCours.set(false);
    }
  }

  protected async approuverPublication(): Promise<void> {
    const pub = this.publicationCreee();
    if (!pub || this.actionPubEnCours() !== null) return;
    this.actionPubEnCours.set('approve');
    this.erreurApi.set(null);
    try {
      const maj = await this.publicationsApi.approve(pub.id_publications);
      this.publicationCreee.set(maj);
      this.successMessage.set(
        `Publication #${maj.id_publications} validée. Vous pouvez maintenant la diffuser.`,
      );
    } catch (err) {
      this.erreurApi.set(toApiError(err).message);
    } finally {
      this.actionPubEnCours.set(null);
    }
  }

  protected async publierMaintenant(): Promise<void> {
    const pub = this.publicationCreee();
    if (!pub || this.actionPubEnCours() !== null) return;
    this.actionPubEnCours.set('publish');
    this.erreurApi.set(null);
    try {
      const res = await this.publicationsApi.publish(pub.id_publications);
      this.publicationCreee.set(res.publication);
      if (res.ok) {
        this.successMessage.set(`Diffusion réussie : ${res.message}`);
      } else {
        this.erreurApi.set(res.message);
      }
    } catch (err) {
      this.erreurApi.set(toApiError(err).message);
    } finally {
      this.actionPubEnCours.set(null);
    }
  }

  protected classeStatutPub(code: string): string {
    switch (code) {
      case 'published':
        return 'status-published';
      case 'approved':
      case 'scheduled':
        return 'status-review';
      case 'pending_review':
      case 'partially_published':
        return 'status-scheduled';
      case 'failed':
      case 'needs_correction':
        return 'status-failed';
      default:
        return 'status-draft';
    }
  }
}

function detectKind(file: File): MediaKind | null {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type.startsWith('video/')) return 'video';
  if (file.type === 'application/pdf') return 'document';
  return null;
}

function describeAccepts(accepts: readonly MediaKind[]): string {
  const words = accepts.map((kind) =>
    kind === 'image' ? 'des images' : kind === 'video' ? 'une vidéo' : 'un PDF',
  );
  if (words.length === 0) return 'aucun média';
  if (words.length === 1) return words[0];
  return `${words.slice(0, -1).join(', ')} ou ${words[words.length - 1]}`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—';
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes} min ${String(rest).padStart(2, '0')} s` : `${rest} s`;
}

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
