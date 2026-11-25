import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { toApiError } from '../../../core/api/api-error';
import {
  AiPromptDto,
  AiPromptKind,
  AiPromptTaskCode,
  AiPromptTaskDto,
  OpenRouterApi,
} from '../../../core/api/openrouter.api';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

@Component({
  selector: 'app-ai-prompts',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon],
  templateUrl: './ai-prompts.html',
  styleUrl: './ai-prompts.scss',
})
export class AiPrompts {
  private readonly api = inject(OpenRouterApi);

  /** Injecté par la route (`data: { kind: 'system' | 'template' }`) via `withComponentInputBinding()`. */
  readonly kind = input<AiPromptKind>('system');

  constructor() {
    effect(() => {
      const currentKind = this.kind();
      void this.loadAll(currentKind);
    });
  }

  /* ---------- États globaux ---------- */
  protected readonly loading = signal<boolean>(true);
  protected readonly busyAction = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  /* ---------- Données API ---------- */
  protected readonly tasks = signal<readonly AiPromptTaskDto[]>([]);
  protected readonly selectedTaskCode = signal<AiPromptTaskCode>('publication_description');
  protected readonly prompts = signal<readonly AiPromptDto[]>([]);
  protected readonly searchTerm = signal<string>('');

  /* ---------- Pop-up agrandi (détail gabarit) ---------- */
  protected readonly expandedPrompt = signal<AiPromptDto | null>(null);

  /* ---------- Modale Création / Édition ---------- */
  protected readonly showEditorModal = signal<boolean>(false);
  protected readonly editingPromptId = signal<number | null>(null);
  protected readonly formTitle = signal<string>('');
  protected readonly formDescription = signal<string>('');
  protected readonly formContent = signal<string>('');
  protected readonly formIsDefault = signal<boolean>(false);

  /* ---------- Sélecteurs dérivés ---------- */
  protected readonly isSystemKind = computed(() => this.kind() === 'system');

  protected readonly pageTitle = computed(() =>
    this.isSystemKind() ? 'Prompts système' : 'Prompt templates (Gabarits)',
  );

  protected readonly pageSubtitle = computed(() =>
    this.isSystemKind()
      ? 'Définissez le rôle, le ton et les règles système versionnées appliquées par défaut à chaque tâche IA.'
      : 'Créez et versionnez vos gabarits de prompts réutilisables (avec variables {{...}}) par tâche métier.',
  );

  protected readonly selectedTask = computed(
    () => this.tasks().find((t) => t.code === this.selectedTaskCode()) ?? null,
  );

  protected readonly filteredPrompts = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const list = this.prompts();
    if (!term) return list;
    return list.filter(
      (p) =>
        p.title.toLowerCase().includes(term) ||
        p.content.toLowerCase().includes(term) ||
        (p.description?.toLowerCase().includes(term) ?? false) ||
        `v${p.version_number}`.includes(term),
    );
  });

  private loadSeq = 0;
  private lastTaskLoadFailed = false;

  protected async loadAll(kindOverride?: AiPromptKind): Promise<void> {
    const seq = ++this.loadSeq;
    this.loading.set(true);
    this.errorMessage.set(null);
    this.lastTaskLoadFailed = false;
    this.prompts.set([]);
    this.expandedPrompt.set(null);
    this.showEditorModal.set(false);
    try {
      const kind = kindOverride ?? this.kind();
      const tasks = await this.api.listPromptTasks(kind);
      if (seq !== this.loadSeq) return;
      this.tasks.set(tasks);

      const currentCode = this.selectedTaskCode();
      const targetCode = tasks.some((t) => t.code === currentCode)
        ? currentCode
        : (tasks[0]?.code ?? 'publication_description');
      this.selectedTaskCode.set(targetCode);

      const prompts = await this.api.listPrompts(kind, targetCode);
      if (seq !== this.loadSeq) return;
      this.prompts.set(prompts);
    } catch (err) {
      if (seq !== this.loadSeq) return;
      this.lastTaskLoadFailed = true;
      this.errorMessage.set(toApiError(err).message);
    } finally {
      if (seq === this.loadSeq) {
        this.loading.set(false);
      }
    }
  }

  protected async selectTask(code: AiPromptTaskCode): Promise<void> {
    if (this.selectedTaskCode() === code && !this.lastTaskLoadFailed) return;
    const seq = ++this.loadSeq;
    this.selectedTaskCode.set(code);
    this.searchTerm.set('');
    this.prompts.set([]);
    this.loading.set(true);
    this.errorMessage.set(null);
    this.lastTaskLoadFailed = false;
    try {
      const prompts = await this.api.listPrompts(this.kind(), code);
      if (seq !== this.loadSeq) return;
      this.prompts.set(prompts);
    } catch (err) {
      if (seq !== this.loadSeq) return;
      this.lastTaskLoadFailed = true;
      this.errorMessage.set(toApiError(err).message);
    } finally {
      if (seq === this.loadSeq) {
        this.loading.set(false);
      }
    }
  }

  /* =========================================================================
     Actions Gabarits : Agrandir, Activer par défaut, Créer, Modifier, Dupliquer, Supprimer
     ========================================================================= */

  protected openCreateModal(): void {
    this.editingPromptId.set(null);
    this.formTitle.set('');
    this.formDescription.set('');
    this.formContent.set('');
    this.formIsDefault.set(this.prompts().length === 0);
    this.showEditorModal.set(true);
    this.errorMessage.set(null);
  }

  protected openEditModal(prompt: AiPromptDto): void {
    this.expandedPrompt.set(null);
    this.editingPromptId.set(prompt.id_ai_prompts);
    this.formTitle.set(prompt.title);
    this.formDescription.set(prompt.description ?? '');
    this.formContent.set(prompt.content);
    this.formIsDefault.set(prompt.is_default);
    this.showEditorModal.set(true);
    this.errorMessage.set(null);
  }

  protected openDuplicateAsNewVersion(prompt: AiPromptDto): void {
    this.expandedPrompt.set(null);
    this.editingPromptId.set(null);
    this.formTitle.set(`${prompt.title}`);
    this.formDescription.set(prompt.description ?? '');
    this.formContent.set(prompt.content);
    this.formIsDefault.set(false);
    this.showEditorModal.set(true);
    this.errorMessage.set(null);
  }

  protected async submitEditor(): Promise<void> {
    const title = this.formTitle().trim();
    const content = this.formContent().trim();
    if (title.length < 2 || !content) {
      this.errorMessage.set('Le titre (min 2 car.) et le contenu du prompt sont obligatoires.');
      return;
    }

    this.busyAction.set('save-prompt');
    this.errorMessage.set(null);
    try {
      const editId = this.editingPromptId();
      if (editId === null) {
        const created = await this.api.createPrompt({
          prompt_kind: this.kind(),
          task_code: this.selectedTaskCode(),
          title,
          content,
          description: this.formDescription().trim() || null,
          is_default: this.formIsDefault(),
        });
        this.flashNotice(`Version v${created.version_number} « ${created.title} » créée.`);
      } else {
        const updated = await this.api.updatePrompt(editId, {
          title,
          content,
          description: this.formDescription().trim() || null,
        });
        this.flashNotice(`Version v${updated.version_number} « ${updated.title} » mise à jour.`);
      }

      this.showEditorModal.set(false);
      await this.refreshCurrentTask();
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async activateDefault(prompt: AiPromptDto): Promise<void> {
    if (prompt.is_default) return;
    this.busyAction.set(`default-${prompt.id_ai_prompts}`);
    this.errorMessage.set(null);
    try {
      const updated = await this.api.setDefaultPrompt(prompt.id_ai_prompts);
      await this.refreshCurrentTask();
      if (this.expandedPrompt()?.id_ai_prompts === updated.id_ai_prompts) {
        this.expandedPrompt.set(updated);
      }
      this.flashNotice(`v${updated.version_number} « ${updated.title} » activé par défaut.`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async deletePrompt(prompt: AiPromptDto): Promise<void> {
    this.busyAction.set(`delete-${prompt.id_ai_prompts}`);
    this.errorMessage.set(null);
    try {
      await this.api.deletePrompt(prompt.id_ai_prompts);
      if (this.expandedPrompt()?.id_ai_prompts === prompt.id_ai_prompts) {
        this.expandedPrompt.set(null);
      }
      await this.refreshCurrentTask();
      this.flashNotice(`v${prompt.version_number} « ${prompt.title} » supprimé.`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  private async refreshCurrentTask(): Promise<void> {
    const seq = ++this.loadSeq;
    const kind = this.kind();
    const taskCode = this.selectedTaskCode();
    try {
      const [tasks, prompts] = await Promise.all([
        this.api.listPromptTasks(kind),
        this.api.listPrompts(kind, taskCode),
      ]);
      if (seq !== this.loadSeq) return;
      this.lastTaskLoadFailed = false;
      this.tasks.set(tasks);
      this.prompts.set(prompts);
    } finally {
      if (seq === this.loadSeq) {
        this.loading.set(false);
      }
    }
  }

  /* ---------- Utilitaires ---------- */

  protected extractVariables(content: string): readonly string[] {
    const matches = content.match(/\{\{[^}]+\}\}/g);
    if (!matches) return [];
    return Array.from(new Set(matches));
  }

  protected estimateTokens(charCount: number): number {
    return Math.max(1, Math.round(charCount / 3.7));
  }

  protected async copyContent(content: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(content);
      this.flashNotice('Contenu du prompt copié dans le presse-papiers.');
    } catch {
      this.errorMessage.set('Impossible de copier dans le presse-papiers.');
    }
  }

  protected formatDate(iso: string): string {
    const d = new Date(iso);
    return Number.isNaN(d.getTime())
      ? iso
      : d.toLocaleString('fr-FR', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
  }

  private flashNotice(msg: string): void {
    this.notice.set(msg);
    setTimeout(() => {
      if (this.notice() === msg) this.notice.set(null);
    }, 4500);
  }
}
