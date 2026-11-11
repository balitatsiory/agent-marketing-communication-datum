import { Injectable, computed, signal } from '@angular/core';
import {
  AI_MODELS,
  DEFAULT_TASK_ASSIGNMENTS,
  INITIAL_PROVIDER_CONFIGS,
} from '../data/ai-models.data';
import { AiModel, AiProvider, ProviderConfig, TaskAssignments } from '../models/ai-model';

@Injectable({ providedIn: 'root' })
export class AiModelsStore {
  readonly models = signal<readonly AiModel[]>(AI_MODELS);
  readonly assignments = signal<TaskAssignments>(DEFAULT_TASK_ASSIGNMENTS);
  readonly providerConfigs = signal<readonly ProviderConfig[]>(INITIAL_PROVIDER_CONFIGS);

  readonly selectedProvider = signal<AiProvider>('anthropic');
  readonly isTesting = signal<boolean>(false);

  readonly currentProviderConfig = computed(() => {
    const current = this.selectedProvider();
    return (
      this.providerConfigs().find((cfg) => cfg.provider === current) ??
      this.providerConfigs()[0]
    );
  });

  /** Statistiques consolidées d'usage sur 30 jours. */
  readonly usageSummary = computed(() => {
    const allModels = this.models();
    const configs = this.providerConfigs();

    const connectedProvidersCount = configs.filter((c) => c.isConnected).length;

    const totalCalls = allModels.reduce((acc, m) => acc + m.usage.callsCount, 0);
    const totalPromptTokens = allModels.reduce((acc, m) => acc + m.usage.promptTokens, 0);
    const totalCompletionTokens = allModels.reduce(
      (acc, m) => acc + m.usage.completionTokens,
      0,
    );
    const totalTokensSpent = totalPromptTokens + totalCompletionTokens;
    const totalCachedTokens = allModels.reduce(
      (acc, m) => acc + (m.usage.cachedTokens ?? 0),
      0,
    );
    const totalImages = allModels.reduce(
      (acc, m) => acc + (m.usage.imagesGenerated ?? 0),
      0,
    );
    const totalCostUsd = allModels.reduce((acc, m) => acc + m.usage.costUsd, 0);

    const totalBudgetLimitUsd = configs.reduce(
      (acc, c) => acc + c.monthlyBudgetLimitUsd,
      0,
    );
    const remainingBudgetUsd = Math.max(0, totalBudgetLimitUsd - totalCostUsd);
    const budgetUsedPct =
      totalBudgetLimitUsd > 0
        ? Math.min(100, Math.round((totalCostUsd / totalBudgetLimitUsd) * 100))
        : 0;

    const totalTokenQuota = configs.reduce((acc, c) => acc + c.monthlyTokenQuota, 0);
    const remainingTokens = Math.max(0, totalTokenQuota - totalTokensSpent);
    const tokenQuotaUsedPct =
      totalTokenQuota > 0
        ? Math.min(100, Math.round((totalTokensSpent / totalTokenQuota) * 100))
        : 0;

    const sortedByCalls = [...allModels].sort(
      (a, b) => b.usage.callsCount - a.usage.callsCount,
    );
    const topModel = sortedByCalls[0];
    const topModels = sortedByCalls.slice(0, 4);

    const avgSuccessRate =
      allModels.length > 0
        ? +(
            allModels.reduce((acc, m) => acc + m.usage.successRatePct, 0) /
            allModels.length
          ).toFixed(1)
        : 100;

    /* Répartition par spécialité métier IAGORA */
    const specialtyBreakdown = [
      {
        key: 'text-generation' as const,
        label: 'Génération de texte',
        hint: 'Publications, déclinaisons réseaux & messagerie',
        calls: 2715,
        sharePct: 62,
        tokensOrUnits: '3,12 M tokens',
        costUsd: 19.65,
      },
      {
        key: 'rag-embedding' as const,
        label: 'RAG / Embedding',
        hint: 'Indexation pgvector & recherche documentaire',
        calls: 747,
        sharePct: 17,
        tokensOrUnits: '930 k tokens',
        costUsd: 0.45,
      },
      {
        key: 'image-description' as const,
        label: "Description d'image (Vision)",
        hint: 'Analyse sémantique des médias de référence',
        calls: 705,
        sharePct: 16,
        tokensOrUnits: '724 k tokens',
        costUsd: 6.85,
      },
      {
        key: 'image-generation' as const,
        label: "Génération & retouche d'image",
        hint: 'Création visuelle & retouche par conversation',
        calls: 218,
        sharePct: 5,
        tokensOrUnits: '218 visuels',
        costUsd: 9.25,
      },
    ];

    return {
      connectedProvidersCount,
      totalProvidersCount: configs.length,
      totalCalls,
      dailyAvgCalls: Math.round(totalCalls / 30),
      totalPromptTokens,
      totalCompletionTokens,
      totalTokensSpent,
      totalCachedTokens,
      totalTokenQuota,
      remainingTokens,
      tokenQuotaUsedPct,
      totalImages,
      totalCostUsd,
      totalBudgetLimitUsd,
      remainingBudgetUsd,
      budgetUsedPct,
      topModel,
      topModels,
      sortedByCalls,
      avgSuccessRate,
      specialtyBreakdown,
    };
  });

  setAssignment(taskKey: keyof TaskAssignments, modelId: string): void {
    this.assignments.update((curr) => ({
      ...curr,
      [taskKey]: modelId,
    }));
  }

  toggleModelStatus(modelId: string): void {
    this.models.update((list) =>
      list.map((m) => {
        if (m.id !== modelId) return m;
        return {
          ...m,
          status: m.status === 'active' ? 'inactive' : 'active',
        };
      }),
    );
  }

  updateProviderConfig(provider: AiProvider, patch: Partial<ProviderConfig>): void {
    this.providerConfigs.update((configs) =>
      configs.map((c) => (c.provider === provider ? { ...c, ...patch } : c)),
    );
  }

  async testConnection(provider: AiProvider): Promise<boolean> {
    this.isTesting.set(true);
    await new Promise((resolve) => setTimeout(resolve, 600));

    const simulatedLatency = Math.floor(Math.random() * 80) + 90;
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');

    this.updateProviderConfig(provider, {
      isConnected: true,
      lastPingMs: simulatedLatency,
      lastTestedAt: `À l’instant (${hours}:${minutes})`,
    });

    this.isTesting.set(false);
    return true;
  }

  async testAll(): Promise<void> {
    this.isTesting.set(true);
    await new Promise((resolve) => setTimeout(resolve, 800));

    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(
      now.getMinutes(),
    ).padStart(2, '0')}`;

    this.providerConfigs.update((configs) =>
      configs.map((cfg) => ({
        ...cfg,
        isConnected: true,
        lastPingMs: Math.floor(Math.random() * 120) + 60,
        lastTestedAt: `À l’instant (${timeStr})`,
      })),
    );

    this.isTesting.set(false);
  }
}
