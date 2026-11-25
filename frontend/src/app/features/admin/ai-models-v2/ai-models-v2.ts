import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { toApiError } from '../../../core/api/api-error';
import {
  AiModelDto,
  AiTaskAssignmentDto,
  AiTaskCode,
  AiWorkspaceDto,
  OpenRouterApi,
  OpenRouterKeyDto,
  OpenRouterOverviewDto,
  OpenRouterProviderSort,
} from '../../../core/api/openrouter.api';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

export type V2MainTab = 'keys' | 'workspaces' | 'models';

const MAX_DISPLAYED_MODELS = 100;

@Component({
  selector: 'app-ai-models-v2',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon],
  templateUrl: './ai-models-v2.html',
  styleUrl: './ai-models-v2.scss',
})
export class AiModelsV2 implements OnInit {
  private readonly api = inject(OpenRouterApi);

  /* ---------- Navigation & états globaux ---------- */
  protected readonly activeTab = signal<V2MainTab>('keys');
  protected readonly loading = signal<boolean>(true);
  protected readonly busyAction = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  /* ---------- Données API ---------- */
  protected readonly overview = signal<OpenRouterOverviewDto | null>(null);
  protected readonly keys = signal<readonly OpenRouterKeyDto[]>([]);
  protected readonly workspaces = signal<readonly AiWorkspaceDto[]>([]);
  protected readonly models = signal<readonly AiModelDto[]>([]);
  protected readonly assignments = signal<readonly AiTaskAssignmentDto[]>([]);

  /* ---------- Formulaires Clés chiffrées ---------- */
  protected readonly mgmtKeyInput = signal<string>('');
  protected readonly mgmtLabelInput = signal<string>('Management API Key DATUM');
  protected readonly showMgmtKey = signal<boolean>(false);

  protected readonly stdKeyInput = signal<string>('');
  protected readonly stdLabelInput = signal<string>('Clé API Standard IAGORA');
  protected readonly showStdKey = signal<boolean>(false);

  /* ---------- Formulaire Workspace (création / édition) ---------- */
  protected readonly showWorkspaceForm = signal<boolean>(false);
  protected readonly editingWorkspaceId = signal<number | null>(null);
  protected readonly wsName = signal<string>('');
  protected readonly wsDescription = signal<string>('');
  protected readonly wsDefaultTextModel = signal<string>('');
  protected readonly wsDefaultImageModel = signal<string>('');
  protected readonly wsProviderSort = signal<OpenRouterProviderSort | ''>('');
  protected readonly wsMonthlyBudget = signal<string>('');

  /* ---------- Filtres Modèles ---------- */
  protected readonly modelSearch = signal<string>('');
  protected readonly modelProviderFilter = signal<string>('all');
  protected readonly modelEnabledOnly = signal<boolean>(false);
  protected readonly modelModalityFilter = signal<'all' | 'vision' | 'image-out'>('all');

  /* ---------- Sélecteurs dérivés ---------- */
  protected readonly activeManagementKey = computed(
    () => this.keys().find((k) => k.key_kind === 'management' && k.is_active) ?? null,
  );

  protected readonly activeStandardKey = computed(
    () => this.keys().find((k) => k.key_kind === 'standard' && k.is_active) ?? null,
  );

  protected readonly enabledModels = computed(() =>
    this.models().filter((m) => m.is_enabled),
  );

  protected readonly providers = computed(() => {
    const set = new Set<string>();
    for (const m of this.models()) {
      set.add(m.provider_slug);
    }
    return Array.from(set).sort();
  });

  protected readonly filteredModels = computed(() => {
    const term = this.modelSearch().trim().toLowerCase();
    const provider = this.modelProviderFilter();
    const enabledOnly = this.modelEnabledOnly();
    const modality = this.modelModalityFilter();

    let list = this.models();
    if (enabledOnly) {
      list = list.filter((m) => m.is_enabled);
    }
    if (provider !== 'all') {
      list = list.filter((m) => m.provider_slug === provider);
    }
    if (modality === 'vision') {
      list = list.filter((m) => m.input_modalities.includes('image'));
    } else if (modality === 'image-out') {
      list = list.filter((m) => m.output_modalities.includes('image'));
    }
    if (term) {
      list = list.filter(
        (m) =>
          m.name.toLowerCase().includes(term) ||
          m.openrouter_model_id.toLowerCase().includes(term) ||
          m.provider_slug.toLowerCase().includes(term) ||
          (m.description?.toLowerCase().includes(term) ?? false),
      );
    }
    return list;
  });

  protected readonly displayedModels = computed(() =>
    this.filteredModels().slice(0, MAX_DISPLAYED_MODELS),
  );

  protected readonly hasMoreModels = computed(
    () => this.filteredModels().length > MAX_DISPLAYED_MODELS,
  );

  ngOnInit(): void {
    void this.loadAll();
  }

  protected setTab(tab: V2MainTab): void {
    this.activeTab.set(tab);
    this.errorMessage.set(null);
  }

  protected async loadAll(): Promise<void> {
    this.loading.set(true);
    this.errorMessage.set(null);
    try {
      const [overview, keys, workspaces, models, assignments] = await Promise.all([
        this.api.overview(),
        this.api.listKeys(),
        this.api.listWorkspaces(),
        this.api.listModels(),
        this.api.listAssignments(),
      ]);
      this.overview.set(overview);
      this.keys.set(keys);
      this.workspaces.set(workspaces);
      this.models.set(models);
      this.assignments.set(assignments);

      // Si les deux clés sont déjà configurées, ouvrir par défaut sur Workspaces ou Modèles
      if (this.activeTab() === 'keys' && overview.management_key && overview.standard_key) {
        this.activeTab.set('workspaces');
      }
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.loading.set(false);
    }
  }

  /* =========================================================================
     1. Clés API OpenRouter chiffrées
     ========================================================================= */

  protected async saveKey(kind: 'management' | 'standard'): Promise<void> {
    const rawKey = (kind === 'management' ? this.mgmtKeyInput() : this.stdKeyInput()).trim();
    const label = (kind === 'management' ? this.mgmtLabelInput() : this.stdLabelInput()).trim();

    if (rawKey.length < 8) {
      this.errorMessage.set('Veuillez coller une clé OpenRouter valide (au moins 8 caractères).');
      return;
    }

    this.busyAction.set(`save-${kind}`);
    this.errorMessage.set(null);
    try {
      const res = await this.api.saveKey({
        key_kind: kind,
        api_key: rawKey,
        label: label || null,
        verify_immediately: true,
      });

      if (kind === 'management') {
        this.mgmtKeyInput.set('');
        this.showMgmtKey.set(false);
      } else {
        this.stdKeyInput.set('');
        this.showStdKey.set(false);
      }

      await this.refreshKeysAndOverview();
      if (res.verified) {
        this.flashNotice(`Clé chiffrée enregistrée et vérifiée : ${res.message}`);
      } else {
        this.flashNotice(`Clé chiffrée enregistrée en base. Vérification OpenRouter : ${res.message}`);
      }
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async verifyKey(key: OpenRouterKeyDto): Promise<void> {
    this.busyAction.set(`verify-${key.id_openrouter_api_keys}`);
    this.errorMessage.set(null);
    try {
      const res = await this.api.verifyKey(key.id_openrouter_api_keys);
      await this.refreshKeysAndOverview();
      if (res.verified) {
        this.flashNotice(res.message);
      } else {
        this.errorMessage.set(res.message);
      }
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async revokeKey(key: OpenRouterKeyDto): Promise<void> {
    this.busyAction.set(`revoke-${key.id_openrouter_api_keys}`);
    this.errorMessage.set(null);
    try {
      await this.api.revokeKey(key.id_openrouter_api_keys);
      await this.refreshKeysAndOverview();
      this.flashNotice(`Clé ${key.key_masked} révoquée.`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  private async refreshKeysAndOverview(): Promise<void> {
    const [overview, keys] = await Promise.all([this.api.overview(), this.api.listKeys()]);
    this.overview.set(overview);
    this.keys.set(keys);
  }

  /* =========================================================================
     2. Workspaces OpenRouter
     ========================================================================= */

  protected async syncWorkspaces(): Promise<void> {
    this.busyAction.set('sync-workspaces');
    this.errorMessage.set(null);
    try {
      const res = await this.api.syncWorkspaces();
      this.workspaces.set(res.workspaces);
      this.overview.set(await this.api.overview());
      this.flashNotice(res.message);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected openCreateWorkspace(): void {
    this.editingWorkspaceId.set(null);
    this.wsName.set('');
    this.wsDescription.set('');
    this.wsDefaultTextModel.set('');
    this.wsDefaultImageModel.set('');
    this.wsProviderSort.set('');
    this.wsMonthlyBudget.set('');
    this.showWorkspaceForm.set(true);
    this.errorMessage.set(null);
  }

  protected openEditWorkspace(ws: AiWorkspaceDto): void {
    this.editingWorkspaceId.set(ws.id_ai_workspaces);
    this.wsName.set(ws.name);
    this.wsDescription.set(ws.description ?? '');
    this.wsDefaultTextModel.set(ws.default_text_model ?? '');
    this.wsDefaultImageModel.set(ws.default_image_model ?? '');
    this.wsProviderSort.set((ws.default_provider_sort as OpenRouterProviderSort | null) ?? '');
    this.wsMonthlyBudget.set(ws.monthly_budget_usd !== null ? String(ws.monthly_budget_usd) : '');
    this.showWorkspaceForm.set(true);
    this.errorMessage.set(null);
  }

  protected cancelWorkspaceForm(): void {
    this.showWorkspaceForm.set(false);
    this.editingWorkspaceId.set(null);
  }

  protected async submitWorkspaceForm(): Promise<void> {
    const name = this.wsName().trim();
    if (!name) {
      this.errorMessage.set('Le nom du workspace est obligatoire.');
      return;
    }

    const budgetRaw = this.wsMonthlyBudget().trim();
    const budget = budgetRaw !== '' && !Number.isNaN(Number(budgetRaw)) ? Number(budgetRaw) : null;
    const sortVal = this.wsProviderSort();

    this.busyAction.set('save-workspace');
    this.errorMessage.set(null);
    try {
      const editId = this.editingWorkspaceId();
      if (editId === null) {
        await this.api.createWorkspace({
          name,
          description: this.wsDescription().trim() || null,
          default_text_model: this.wsDefaultTextModel().trim() || null,
          default_image_model: this.wsDefaultImageModel().trim() || null,
          default_provider_sort: sortVal || null,
          monthly_budget_usd: budget,
        });
        this.flashNotice(`Workspace « ${name} » créé sur OpenRouter et enregistré.`);
      } else {
        await this.api.updateWorkspace(editId, {
          name,
          description: this.wsDescription().trim() || null,
          default_text_model: this.wsDefaultTextModel().trim() || null,
          default_image_model: this.wsDefaultImageModel().trim() || null,
          default_provider_sort: sortVal || null,
          monthly_budget_usd: budget,
        });
        this.flashNotice(`Workspace « ${name} » mis à jour.`);
      }

      this.showWorkspaceForm.set(false);
      this.editingWorkspaceId.set(null);
      const [workspaces, overview] = await Promise.all([
        this.api.listWorkspaces(),
        this.api.overview(),
      ]);
      this.workspaces.set(workspaces);
      this.overview.set(overview);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async selectWorkspace(ws: AiWorkspaceDto): Promise<void> {
    this.busyAction.set(`select-ws-${ws.id_ai_workspaces}`);
    this.errorMessage.set(null);
    try {
      await this.api.updateWorkspace(ws.id_ai_workspaces, { is_selected: true });
      const [workspaces, overview] = await Promise.all([
        this.api.listWorkspaces(),
        this.api.overview(),
      ]);
      this.workspaces.set(workspaces);
      this.overview.set(overview);
      this.flashNotice(`Workspace actif IAGORA défini sur « ${ws.name} ».`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async deleteWorkspace(ws: AiWorkspaceDto): Promise<void> {
    this.busyAction.set(`delete-ws-${ws.id_ai_workspaces}`);
    this.errorMessage.set(null);
    try {
      await this.api.deleteWorkspace(ws.id_ai_workspaces);
      const [workspaces, overview] = await Promise.all([
        this.api.listWorkspaces(),
        this.api.overview(),
      ]);
      this.workspaces.set(workspaces);
      this.overview.set(overview);
      this.flashNotice(`Workspace « ${ws.name} » supprimé.`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  /* =========================================================================
     3. Modèles IA & Affectations
     ========================================================================= */

  protected async syncModels(): Promise<void> {
    this.busyAction.set('sync-models');
    this.errorMessage.set(null);
    try {
      const res = await this.api.syncModels();
      const [models, overview] = await Promise.all([
        this.api.listModels(),
        this.api.overview(),
      ]);
      this.models.set(models);
      this.overview.set(overview);
      this.flashNotice(res.message);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async toggleModel(model: AiModelDto): Promise<void> {
    this.busyAction.set(`toggle-model-${model.id_ai_models}`);
    this.errorMessage.set(null);
    try {
      const updated = await this.api.toggleModel(model.id_ai_models, !model.is_enabled);
      this.models.update((list) =>
        list.map((m) => (m.id_ai_models === updated.id_ai_models ? updated : m)),
      );
      this.overview.set(await this.api.overview());
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  protected async onAssignmentChange(
    assignment: AiTaskAssignmentDto,
    modelIdRaw: string,
  ): Promise<void> {
    const idModel = modelIdRaw ? Number(modelIdRaw) : null;
    this.busyAction.set(`assign-${assignment.task_code}`);
    this.errorMessage.set(null);
    try {
      const updated = await this.api.updateAssignment(assignment.task_code as AiTaskCode, {
        id_ai_models: idModel,
        id_ai_workspaces: assignment.id_ai_workspaces,
      });
      this.assignments.update((list) =>
        list.map((a) => (a.task_code === updated.task_code ? updated : a)),
      );
      this.flashNotice(
        updated.model_name
          ? `Modèle « ${updated.model_name} » affecté à ${updated.task_label}.`
          : `Affectation retirée pour ${updated.task_label}.`,
      );
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.busyAction.set(null);
    }
  }

  /* ---------- Formatters ---------- */

  protected formatUsd(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    return value.toFixed(2).replace('.', ',') + ' $';
  }

  protected formatPricePerMillion(rawPerToken: string | null): string {
    if (!rawPerToken) return '—';
    const num = Number(rawPerToken);
    if (Number.isNaN(num)) return rawPerToken;
    if (num === 0) return 'Gratuit';
    const perM = num * 1_000_000;
    return `${perM.toFixed(2).replace('.', ',')} $/M`;
  }

  protected formatContext(tokens: number | null): string {
    if (!tokens) return '—';
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1).replace('.', ',')} M`;
    if (tokens >= 1_000) return `${Math.round(tokens / 1_000)} k`;
    return String(tokens);
  }

  protected formatDate(iso: string | null): string {
    if (!iso) return 'Jamais';
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
    }, 5000);
  }
}
