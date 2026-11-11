import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  AI_PROVIDERS,
  AI_PROVIDER_LABELS,
  AI_SPECIALTIES,
  AI_SPECIALTY_HINTS,
  AI_SPECIALTY_LABELS,
  AI_STATUS_LABELS,
  AiModel,
  AiProvider,
  AiSpecialty,
  ProviderConfig,
  TaskAssignments,
} from '../../../core/models/ai-model';
import { AiModelsStore } from '../../../core/services/ai-models-store';
import { Topbar } from '../../../layout/topbar/topbar';
import { Icon } from '../../../shared/icon/icon';

type FilterType = 'all' | AiSpecialty;
export type AiModelsMainTab = 'models' | 'stats' | 'providers';

@Component({
  selector: 'app-ai-models',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon],
  templateUrl: './ai-models.html',
  styleUrl: './ai-models.scss',
})
export class AiModels {
  protected readonly store = inject(AiModelsStore);

  protected readonly specialties = AI_SPECIALTIES;
  protected readonly specialtyLabels = AI_SPECIALTY_LABELS;
  protected readonly specialtyHints = AI_SPECIALTY_HINTS;
  protected readonly providers = AI_PROVIDERS;
  protected readonly providerLabels = AI_PROVIDER_LABELS;
  protected readonly statusLabels = AI_STATUS_LABELS;

  /* ---------- Onglet principal (Option A : 3 onglets métier) ---------- */
  protected readonly activeTab = signal<AiModelsMainTab>('models');

  /* ---------- filtres & recherche ---------- */
  protected readonly filter = signal<FilterType>('all');
  protected readonly searchTerm = signal<string>('');

  /* ---------- interface & notifications ---------- */
  protected readonly notice = signal<string | null>(null);
  protected readonly showApiKey = signal<boolean>(false);

  /* ---------- champs d'édition locale du provider sélectionné ---------- */
  protected readonly editEndpoint = signal<string>('');
  protected readonly editApiKey = signal<string>('');
  protected readonly editTemperature = signal<number>(0.7);
  protected readonly editMaxTokens = signal<number>(2048);
  protected readonly editMonthlyBudget = signal<number>(50);
  protected readonly editMonthlyTokenQuota = signal<number>(4000000);

  constructor() {
    this.syncEditFields(this.store.selectedProvider());
  }

  /* Modèles filtrés */
  protected readonly filteredModels = computed(() => {
    const activeFilter = this.filter();
    const term = this.searchTerm().trim().toLowerCase();
    let list = this.store.models();

    if (activeFilter !== 'all') {
      list = list.filter((m) => m.specialties.includes(activeFilter));
    }

    if (term) {
      list = list.filter(
        (m) =>
          m.name.toLowerCase().includes(term) ||
          m.technicalId.toLowerCase().includes(term) ||
          this.providerLabels[m.provider].toLowerCase().includes(term) ||
          m.description.toLowerCase().includes(term),
      );
    }

    return list;
  });

  /* Modèles disponibles par spécialité pour les cartes d'assignation */
  protected readonly textModels = computed(() =>
    this.store.models().filter((m) => m.specialties.includes('text-generation')),
  );

  protected readonly visionModels = computed(() =>
    this.store.models().filter((m) => m.specialties.includes('image-description')),
  );

  protected readonly imageModels = computed(() =>
    this.store.models().filter((m) => m.specialties.includes('image-generation')),
  );

  protected readonly ragModels = computed(() =>
    this.store.models().filter((m) => m.specialties.includes('rag-embedding')),
  );

  /* Modèle actuellement assigné pour chaque tâche */
  protected readonly currentTextModel = computed(() =>
    this.store.models().find((m) => m.id === this.store.assignments().textModelId),
  );

  protected readonly currentVisionModel = computed(() =>
    this.store.models().find((m) => m.id === this.store.assignments().visionModelId),
  );

  protected readonly currentImageModel = computed(() =>
    this.store.models().find((m) => m.id === this.store.assignments().imageModelId),
  );

  protected readonly currentRagModel = computed(() =>
    this.store.models().find((m) => m.id === this.store.assignments().ragModelId),
  );

  /* Formatage lisible des tokens (ex: 1 420 000 -> 1,42 M ou 620 k) */
  protected formatTokens(n: number): string {
    if (n >= 1_000_000) {
      return (n / 1_000_000).toFixed(2).replace('.', ',') + ' M';
    }
    if (n >= 1_000) {
      return Math.round(n / 1_000) + ' k';
    }
    return String(n);
  }

  protected formatCurrency(usd: number): string {
    return usd.toFixed(2).replace('.', ',') + ' $';
  }

  protected getProviderBudgetPct(cfg: ProviderConfig): number {
    if (cfg.monthlyBudgetLimitUsd <= 0) return 0;
    return Math.min(
      100,
      Math.round((cfg.spentUsdThisMonth / cfg.monthlyBudgetLimitUsd) * 100),
    );
  }

  protected getProviderTokenPct(cfg: ProviderConfig): number {
    if (cfg.monthlyTokenQuota <= 0) return 0;
    return Math.min(
      100,
      Math.round((cfg.tokensUsedThisMonth / cfg.monthlyTokenQuota) * 100),
    );
  }

  /* Changement d'onglet principal */
  protected setMainTab(tab: AiModelsMainTab): void {
    this.activeTab.set(tab);
  }

  /* Ouvrir directement la configuration d'un fournisseur depuis les stats ou le tableau */
  protected openProviderConfig(provider: AiProvider): void {
    this.selectProvider(provider);
    this.activeTab.set('providers');
  }

  /* Changement d'onglet fournisseur */
  protected selectProvider(provider: AiProvider): void {
    this.store.selectedProvider.set(provider);
    this.syncEditFields(provider);
  }

  private syncEditFields(provider: AiProvider): void {
    const cfg =
      this.store.providerConfigs().find((c) => c.provider === provider) ??
      this.store.providerConfigs()[0];
    this.editEndpoint.set(cfg.endpointUrl);
    this.editApiKey.set(cfg.apiKeyMasked);
    this.editTemperature.set(cfg.temperature);
    this.editMaxTokens.set(cfg.maxTokens);
    this.editMonthlyBudget.set(cfg.monthlyBudgetLimitUsd);
    this.editMonthlyTokenQuota.set(cfg.monthlyTokenQuota);
    this.showApiKey.set(false);
  }

  protected async testCurrentProvider(): Promise<void> {
    const p = this.store.selectedProvider();
    await this.store.testConnection(p);
    this.showNotice(`Connexion à ${this.providerLabels[p]} testée avec succès.`);
  }

  protected async testAllProviders(): Promise<void> {
    await this.store.testAll();
    this.showNotice('Toutes les liaisons API ont été vérifiées avec succès.');
  }

  protected saveProviderConfig(): void {
    const provider = this.store.selectedProvider();
    this.store.updateProviderConfig(provider, {
      endpointUrl: this.editEndpoint().trim(),
      apiKeyMasked: this.editApiKey().trim(),
      temperature: this.editTemperature(),
      maxTokens: this.editMaxTokens(),
      monthlyBudgetLimitUsd: this.editMonthlyBudget(),
      monthlyTokenQuota: this.editMonthlyTokenQuota(),
    });
    this.showNotice(`Configuration et quotas de ${this.providerLabels[provider]} enregistrés.`);
  }

  protected onAssignmentChange(key: keyof TaskAssignments, modelId: string): void {
    this.store.setAssignment(key, modelId);
    const model = this.store.models().find((m) => m.id === modelId);
    this.showNotice(`Modèle ${model?.name ?? modelId} assigné par défaut.`);
  }

  protected isModelActiveForAnyTask(modelId: string): boolean {
    const a = this.store.assignments();
    return (
      a.textModelId === modelId ||
      a.visionModelId === modelId ||
      a.imageModelId === modelId ||
      a.ragModelId === modelId
    );
  }

  protected getModelRoleLabel(modelId: string): string | null {
    const a = this.store.assignments();
    const roles: string[] = [];
    if (a.textModelId === modelId) roles.push('Texte');
    if (a.visionModelId === modelId) roles.push('Vision');
    if (a.imageModelId === modelId) roles.push('Image');
    if (a.ragModelId === modelId) roles.push('RAG');
    return roles.length ? roles.join(', ') : null;
  }

  protected toggleModel(model: AiModel): void {
    this.store.toggleModelStatus(model.id);
  }

  private showNotice(msg: string): void {
    this.notice.set(msg);
    setTimeout(() => {
      if (this.notice() === msg) this.notice.set(null);
    }, 4000);
  }
}
