import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  MEDIA_DESCRIPTION_STATUS_LABELS,
  MEDIA_REFERENCE_ROLE_HINTS,
  MEDIA_REFERENCE_ROLE_LABELS,
  MEDIA_REFERENCE_ROLES,
  MediaDescriptionStatus,
  MediaReference,
  MediaReferenceRole,
} from '../../../core/models/media-reference';
import { MediaReferenceStore } from '../../../core/services/media-reference-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

/** Filtre par rôle : un seul actif à la fois. */
type RoleFilter = 'all' | MediaReferenceRole;

/** La fenêtre est ouverte pour importer un fichier, ou pour modifier un média existant. */
type EditorState = { readonly mode: 'import' } | { readonly mode: 'edit'; readonly media: MediaReference };

/**
 * Médias de référence — la bibliothèque que l'IA consulte avant de
 * produire un visuel.
 *
 * Chaque média porte un rôle (ce que l'IA a le droit d'en faire) et une
 * description proposée par l'IA, qu'une personne doit relire avant
 * qu'elle serve. Une personne représentée exige un consentement écrit
 * spécifique à l'usage IA.
 */
@Component({
  selector: 'app-media-reference-list',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon],
  templateUrl: './media-reference-list.html',
  styleUrl: './media-reference-list.scss',
})
export class MediaReferenceList {
  protected readonly store = inject(MediaReferenceStore);

  protected readonly roles = MEDIA_REFERENCE_ROLES;
  protected readonly roleLabels = MEDIA_REFERENCE_ROLE_LABELS;
  protected readonly roleHints = MEDIA_REFERENCE_ROLE_HINTS;
  protected readonly statusLabels = MEDIA_DESCRIPTION_STATUS_LABELS;
  protected readonly waitingPlaceholder =
    "La proposition de l'IA apparaît une fois le fichier déposé.";

  /* ---------- recherche & filtres ---------- */

  protected readonly searchTerm = signal('');
  protected readonly filter = signal<RoleFilter>('all');

  protected readonly filters = computed(() => {
    const all = this.store.everything();
    return [
      { key: 'all' as RoleFilter, label: 'Tous', count: all.length },
      ...this.roles.map((role) => ({
        key: role as RoleFilter,
        label: this.roleLabels[role],
        count: all.filter((media) => media.role === role).length,
      })),
    ];
  });

  /** Ensemble des résultats filtrés par rôle et par recherche textuelle. */
  protected readonly filteredResults = computed(() => {
    const filter = this.filter();
    const term = this.searchTerm().trim().toLowerCase();
    let list = this.store.everything();

    if (filter !== 'all') {
      list = list.filter((media) => media.role === filter);
    }

    if (term) {
      list = list.filter(
        (media) =>
          media.fileName.toLowerCase().includes(term) ||
          media.description.toLowerCase().includes(term) ||
          this.roleLabels[media.role].toLowerCase().includes(term),
      );
    }

    return list;
  });

  /** Rétro-compatibilité pour tout appelant lisant results(). */
  protected readonly results = computed(() => this.filteredResults());

  /* ---------- pagination ---------- */

  protected readonly pageSize = signal(6);
  protected readonly currentPage = signal(1);

  protected readonly totalPages = computed(() =>
    Math.max(1, Math.ceil(this.filteredResults().length / this.pageSize())),
  );

  protected readonly paginatedResults = computed(() => {
    const start = (this.currentPage() - 1) * this.pageSize();
    return this.filteredResults().slice(start, start + this.pageSize());
  });

  protected readonly pageNumbers = computed(() =>
    Array.from({ length: this.totalPages() }, (_, i) => i + 1),
  );

  protected readonly pageStart = computed(() =>
    this.filteredResults().length === 0 ? 0 : (this.currentPage() - 1) * this.pageSize() + 1,
  );

  protected readonly pageEnd = computed(() =>
    Math.min(this.currentPage() * this.pageSize(), this.filteredResults().length),
  );

  /* ---------- compteurs de synthèse ---------- */

  protected readonly toReviewCount = computed(
    () => this.store.everything().filter((media) => media.descriptionStatus === 'ai-proposal').length,
  );

  protected readonly missingConsentCount = computed(
    () =>
      this.store.everything().filter((media) => media.depictsPerson && !media.consentCollected)
        .length,
  );

  protected readonly notice = signal<string | null>(null);
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;

  /* ---------- visionneuse (lightbox & défilement) ---------- */

  protected readonly viewingMediaId = signal<number | null>(null);

  protected readonly viewingIndex = computed(() => {
    const id = this.viewingMediaId();
    if (id === null) return -1;
    return this.filteredResults().findIndex((m) => m.id === id);
  });

  protected readonly viewingMedia = computed(() => {
    const idx = this.viewingIndex();
    return idx >= 0 ? this.filteredResults()[idx] : null;
  });

  protected readonly hasPrevViewer = computed(() => this.viewingIndex() > 0);
  protected readonly hasNextViewer = computed(
    () => this.viewingIndex() >= 0 && this.viewingIndex() < this.filteredResults().length - 1,
  );

  /* ---------- fenêtre Importer / Modifier ---------- */

  protected readonly editor = signal<EditorState | null>(null);
  protected readonly isImport = computed(() => this.editor()?.mode === 'import');

  protected readonly file = signal<File | null>(null);
  protected readonly fileError = signal<string | null>(null);
  protected readonly isDragOver = signal(false);

  /** Aucun rôle présélectionné : le choix doit être conscient. */
  protected readonly role = signal<MediaReferenceRole | null>(null);
  protected readonly description = signal('');
  private readonly originalDescription = signal('');
  private readonly originalStatus = signal<MediaDescriptionStatus>('ai-proposal');
  protected readonly hasReviewed = signal(false);
  protected readonly depictsPerson = signal(false);
  protected readonly consentCollected = signal(false);

  protected readonly isDescriptionModified = computed(
    () => this.description() !== this.originalDescription(),
  );

  /** « Proposition IA — à relire » tant que le texte n'a pas bougé, « Relue et modifiée » ensuite. */
  protected readonly descriptionLabel = computed(() =>
    this.isDescriptionModified() ? 'Relue et modifiée' : this.statusLabels[this.originalStatus()],
  );

  protected readonly descriptionTone = computed(() =>
    this.isDescriptionModified() || this.originalStatus() === 'reviewed' ? 'st-done' : 'st-todo',
  );

  /** Ce qui manque encore pour enregistrer, dans l'ordre de la fenêtre. */
  protected readonly missing = computed<readonly string[]>(() => {
    const missing: string[] = [];
    if (this.isImport() && !this.file()) missing.push('un fichier');
    if (!this.role()) missing.push('un rôle');
    if (!this.description().trim()) missing.push('une description');
    if (!this.hasReviewed()) missing.push('la relecture');
    if (this.depictsPerson() && !this.consentCollected()) missing.push('le consentement');
    return missing;
  });

  protected readonly canSave = computed(() => this.missing().length === 0);

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.noticeTimer));
  }

  /* ---------- gestion clavier globale ---------- */

  @HostListener('window:keydown', ['$event'])
  protected onKeyDown(event: KeyboardEvent): void {
    if (this.viewingMedia()) {
      if (event.key === 'Escape') {
        this.closeViewer();
      } else if (event.key === 'ArrowLeft') {
        this.prevViewer();
      } else if (event.key === 'ArrowRight') {
        this.nextViewer();
      }
    } else if (this.editor()) {
      if (event.key === 'Escape') {
        this.close();
      }
    }
  }

  /* ---------- actions recherche & filtres ---------- */

  protected onSearch(term: string): void {
    this.searchTerm.set(term);
    this.currentPage.set(1);
  }

  protected clearSearch(): void {
    this.searchTerm.set('');
    this.currentPage.set(1);
  }

  protected setFilter(role: RoleFilter): void {
    this.filter.set(role);
    this.currentPage.set(1);
  }

  /* ---------- actions pagination ---------- */

  protected goToPage(page: number): void {
    const target = Math.max(1, Math.min(page, this.totalPages()));
    this.currentPage.set(target);
  }

  protected prevPage(): void {
    this.goToPage(this.currentPage() - 1);
  }

  protected nextPage(): void {
    this.goToPage(this.currentPage() + 1);
  }

  protected setPageSize(size: number): void {
    this.pageSize.set(size);
    this.currentPage.set(1);
  }

  /* ---------- actions visionneuse ---------- */

  protected openViewer(media: MediaReference): void {
    this.viewingMediaId.set(media.id);
  }

  protected closeViewer(): void {
    this.viewingMediaId.set(null);
  }

  protected prevViewer(): void {
    if (this.hasPrevViewer()) {
      const prev = this.filteredResults()[this.viewingIndex() - 1];
      if (prev) this.viewingMediaId.set(prev.id);
    }
  }

  protected nextViewer(): void {
    if (this.hasNextViewer()) {
      const next = this.filteredResults()[this.viewingIndex() + 1];
      if (next) this.viewingMediaId.set(next.id);
    }
  }

  protected openEditFromViewer(media: MediaReference): void {
    this.closeViewer();
    this.openEdit(media);
  }

  /* ---------- actions éditeur (importer / modifier) ---------- */

  protected openImport(): void {
    this.resetEditor();
    this.editor.set({ mode: 'import' });
  }

  protected openEdit(media: MediaReference): void {
    this.resetEditor();
    this.role.set(media.role);
    this.description.set(media.description);
    this.originalDescription.set(media.description);
    this.originalStatus.set(media.descriptionStatus);
    // Une description déjà relue n'a pas à être re-certifiée pour changer de rôle.
    this.hasReviewed.set(media.descriptionStatus === 'reviewed');
    this.depictsPerson.set(media.depictsPerson);
    this.consentCollected.set(media.consentCollected);
    this.editor.set({ mode: 'edit', media });
  }

  protected close(): void {
    this.editor.set(null);
  }

  protected save(): void {
    const editor = this.editor();
    const role = this.role();
    if (!editor || !role || !this.canSave()) return;

    const draft = {
      role,
      description: this.description(),
      depictsPerson: this.depictsPerson(),
      consentCollected: this.consentCollected(),
    };

    if (editor.mode === 'import') {
      const file = this.file();
      if (!file) return;
      const media = this.store.add(file, draft);
      // Le nouveau média doit rester visible : on quitte un filtre qui le cacherait.
      if (this.filter() !== 'all' && this.filter() !== media.role) this.filter.set('all');
      this.searchTerm.set('');
      this.currentPage.set(1);
      this.showNotice(`« ${media.fileName} » ajouté à la bibliothèque.`);
    } else {
      this.store.update(editor.media.id, draft);
      this.showNotice(`« ${editor.media.fileName} » mis à jour.`);
    }
    this.close();
  }

  /* ---------- fichier ---------- */

  protected onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.acceptFile(file);
    // Permet de re-choisir le même fichier après l'avoir remplacé.
    input.value = '';
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.acceptFile(file);
  }

  /** Un fichier accepté appelle une nouvelle proposition, à relire de nouveau. */
  private acceptFile(file: File): void {
    if (!file.type.startsWith('image/')) {
      this.fileError.set(`« ${file.name} » n'est pas une image. Formats acceptés : PNG, JPG, WebP, SVG.`);
      return;
    }
    this.fileError.set(null);
    this.file.set(file);
    const proposal = this.store.proposeDescription(file);
    this.description.set(proposal);
    this.originalDescription.set(proposal);
    this.originalStatus.set('ai-proposal');
    this.hasReviewed.set(false);
  }

  /* ---------- cases à cocher ---------- */

  protected setDepictsPerson(value: boolean): void {
    this.depictsPerson.set(value);
    if (!value) this.consentCollected.set(false);
  }

  protected formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
  }

  private resetEditor(): void {
    this.file.set(null);
    this.fileError.set(null);
    this.isDragOver.set(false);
    this.role.set(null);
    this.description.set('');
    this.originalDescription.set('');
    this.originalStatus.set('ai-proposal');
    this.hasReviewed.set(false);
    this.depictsPerson.set(false);
    this.consentCollected.set(false);
  }

  private showNotice(message: string): void {
    clearTimeout(this.noticeTimer);
    this.notice.set(message);
    this.noticeTimer = setTimeout(() => this.notice.set(null), 4000);
  }
}
