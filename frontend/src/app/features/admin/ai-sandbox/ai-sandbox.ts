import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { EChartsOption } from 'echarts';

import { toApiError } from '../../../core/api/api-error';
import {
  AiModelDto,
  AiReasoningEffort,
  AiTaskCode,
  OpenRouterApi,
  OpenRouterKeyDto,
  SandboxUseCase,
  SandboxVariantResultDto,
} from '../../../core/api/openrouter.api';
import { Topbar } from '../../../layout/topbar/topbar';
import { Chart } from '../../../shared/chart/chart';
import { Icon } from '../../../shared/icon/icon';

interface SandboxVariantSlot {
  readonly slotId: string;
  readonly label: string;
  readonly modelId: string;
  readonly reasoningEffort: AiReasoningEffort | '';
  readonly temperature: number;
  readonly showRawJson: boolean;
  readonly result: SandboxVariantResultDto | null;
}

interface UseCaseConfig {
  readonly code: SandboxUseCase;
  readonly title: string;
  readonly subtitle: string;
  readonly targetTaskCode: AiTaskCode;
  readonly defaultSystemPrompt: string;
  readonly defaultUserPrompt: string;
  readonly tones: readonly string[];
  readonly defaultTone: string;
  readonly defaultJsonSchema: string;
  readonly defaultContext: string;
  readonly contextLabel: string;
}

const USE_CASES: readonly UseCaseConfig[] = [
  {
    code: 'publication_text',
    title: 'Génération de texte pour publication',
    subtitle: 'Posts LinkedIn, Facebook, Instagram orientés conversion et engagement.',
    targetTaskCode: 'text-generation',
    defaultSystemPrompt:
      "Tu es le responsable éditorial de Datum Academy. Rédige des publications engageantes, structurées et orientées conversion pour LinkedIn et Meta. Ton : professionnel, accessible, concret. Longueur : 120 à 180 mots maximum avec un appel à l'action clair.",
    defaultUserPrompt:
      "Rédige un post de lancement pour notre nouvelle cohorte intensive « Data Analytics & IA Appliquée en Entreprise » (durée 8 semaines, format hybride soir & samedi, projets réels sur données métier). Cible : analystes, chefs de projet et cadres en reconversion.",
    tones: [
      'Professionnel, accessible et concret',
      'Dynamique et engageant (LinkedIn / Meta)',
      'Pédagogique et expert',
      'Institutionnel et rassurant',
      'Orienté conversion et urgence douce',
    ],
    defaultTone: 'Professionnel, accessible et concret',
    defaultJsonSchema: JSON.stringify(
      {
        accroche: 'Phrase d’ouverture percutante',
        corps: 'Corps structuré de la publication (120-180 mots)',
        appel_action: 'CTA clair avec lien',
        hashtags: ['#DataAnalytics', '#DatumAcademy'],
      },
      null,
      2,
    ),
    defaultContext:
      'Marque : Datum Academy | Lieu : Antananarivo & Distanciel Live | Prochaine rentrée : 15 Janvier | Points forts : 70% pratique, mentorat individuel, certification projet | Lien inscription : datum-academy.mg/data-ia',
    contextLabel: 'Brief éditorial & cible',
  },
  {
    code: 'image_generation',
    title: "Génération d'image / Modification image",
    subtitle: 'Création de visuels réseaux sociaux ou retouche/analyse sur image existante.',
    targetTaskCode: 'image-generation',
    defaultSystemPrompt:
      "Tu es directeur artistique senior chez Datum Academy. Produis ou modifie des visuels professionnels, modernes et lisibles sur mobile pour LinkedIn et Meta, en respectant une palette institutionnelle (bleu nuit #0F172A, indigo #4F46E5, blanc pur) avec une hiérarchie typographique claire.",
    defaultUserPrompt:
      "Crée un visuel carré promotionnel épuré pour annoncer notre atelier pratique « IA Générative & Data pour Décideurs » : ambiance tech moderne, mise en page aérée, contraste fort, zéro texte illisible.",
    tones: [
      'Institutionnel moderne Datum Academy',
      'Minimaliste & éditorial LinkedIn',
      'Photographique studio lumineux',
      'Illustration vectorielle flat tech',
      'Dynamique & fort contraste social media',
    ],
    defaultTone: 'Institutionnel moderne Datum Academy',
    defaultJsonSchema: JSON.stringify(
      {
        prompt_visuel_final: 'Description détaillée du visuel généré ou retouché',
        palette_couleurs: ['#0F172A', '#4F46E5', '#FFFFFF'],
        texte_alternatif_seo: 'Texte alternatif accessible',
        recommandations_meta: ['Conseil lisibilité mobile'],
      },
      null,
      2,
    ),
    defaultContext:
      'Charte Datum Academy : Bleu nuit #0F172A, Indigo #4F46E5, police sans-serif géométrique, marge de sécurité 10 % sur les bords pour recadrage Meta/LinkedIn.',
    contextLabel: 'Charte graphique & contraintes visuelles',
  },
  {
    code: 'message_rag',
    title: 'Génération de texte pour Message (Base de connaissance)',
    subtitle: 'Réponses WhatsApp / Messenger / LinkedIn fondées strictement sur votre base documentaire.',
    targetTaskCode: 'text-generation',
    defaultSystemPrompt:
      "Tu es conseiller pédagogique Datum Academy sur WhatsApp et Messenger. Réponds de manière chaleureuse, claire et concise (moins de 120 mots). Utilise UNIQUEMENT les informations vérifiées dans la base de connaissances fournie, cite la référence entre crochets et propose un créneau d'échange.",
    defaultUserPrompt:
      "Bonjour, je suis comptable et je n'ai jamais codé en Python. Est-ce que je peux suivre la formation Data & IA, quel est le tarif et quelles sont les conditions pour obtenir le certificat ?",
    tones: [
      'Chaleureux, clair et rassurant',
      'Concis et direct (WhatsApp / DM)',
      'Professionnel et institutionnel',
      'Commercial doux orienté prise de RDV',
    ],
    defaultTone: 'Chaleureux, clair et rassurant',
    defaultJsonSchema: JSON.stringify(
      {
        reponse: 'Message prêt à envoyer au prospect',
        sources_citees: ['Catalogue_2026 §2.1'],
        action_suivante: 'Proposer un appel de 10 min',
        confiance: 'haute',
      },
      null,
      2,
    ),
    defaultContext:
      "[Doc: Catalogue_2026 §2.1] Prérequis : Aucun prérequis en programmation (module d'initiation Python inclus la semaine 1). Tarif total : 1 450 000 Ar (ou 320 €), payable en 3 tranches sans frais.\n[Doc: Règlement_Pédagogique_2026 §4.2] Certification délivrée sous 3 conditions : 80 % de présence live, validation des 4 jalons hebdomadaires et soutenance du projet final.\n[Doc: Créneaux_Conseillers] Appels d'orientation de 10 min disponibles Mardi et Jeudi entre 12h et 14h.",
    contextLabel: 'Base de connaissances (Extraits RAG injectés)',
  },
];

const REASONING_EFFORTS: readonly { readonly value: AiReasoningEffort | ''; readonly label: string }[] = [
  { value: '', label: 'Effort : Par défaut' },
  { value: 'none', label: 'reasoning.effort : none' },
  { value: 'minimal', label: 'reasoning.effort : minimal' },
  { value: 'low', label: 'reasoning.effort : low' },
  { value: 'medium', label: 'reasoning.effort : medium' },
  { value: 'high', label: 'reasoning.effort : high' },
  { value: 'xhigh', label: 'reasoning.effort : xhigh' },
];

const ASPECT_RATIOS: readonly { readonly value: string; readonly label: string }[] = [
  { value: '1:1', label: '1:1 — Carré Instagram / Facebook (1080×1080)' },
  { value: '4:5', label: '4:5 — Portrait flux Meta (1080×1350)' },
  { value: '16:9', label: '16:9 — Paysage / LinkedIn (1920×1080)' },
  { value: '9:16', label: '9:16 — Story / Reel (1080×1920)' },
];

const SLOT_LETTERS = ['A', 'B', 'C', 'D'] as const;
const MAX_VARIANTS = 4;

@Component({
  selector: 'app-ai-sandbox',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, Topbar, Icon, Chart],
  templateUrl: './ai-sandbox.html',
  styleUrl: './ai-sandbox.scss',
})
export class AiSandbox implements OnInit {
  private readonly api = inject(OpenRouterApi);

  protected readonly useCases = USE_CASES;
  protected readonly reasoningEfforts = REASONING_EFFORTS;
  protected readonly aspectRatios = ASPECT_RATIOS;

  /* ---------- États globaux ---------- */
  protected readonly loadingInit = signal<boolean>(true);
  protected readonly isRunning = signal<boolean>(false);
  protected readonly savingKey = signal<boolean>(false);
  protected readonly notice = signal<string | null>(null);
  protected readonly errorMessage = signal<string | null>(null);

  /* ---------- Données API ---------- */
  protected readonly models = signal<readonly AiModelDto[]>([]);
  protected readonly keys = signal<readonly OpenRouterKeyDto[]>([]);
  protected readonly sessionCostUsd = signal<number>(0);
  protected readonly lastKeySource = signal<'sandbox' | 'standard' | null>(null);

  /* ---------- Modale clé Sandbox chiffrée ---------- */
  protected readonly showSandboxKeyModal = signal<boolean>(false);
  protected readonly sandboxKeyInput = signal<string>('');
  protected readonly sandboxKeyLabel = signal<string>('Clé Sandbox isolée DATUM');
  protected readonly showSandboxKeyPlain = signal<boolean>(false);

  /* ---------- Étape 1 : Cas d'utilisation strict & Prompts ---------- */
  protected readonly selectedUseCase = signal<SandboxUseCase>('publication_text');
  protected readonly systemPrompt = signal<string>(USE_CASES[0].defaultSystemPrompt);
  protected readonly userPrompt = signal<string>(USE_CASES[0].defaultUserPrompt);
  protected readonly tone = signal<string>(USE_CASES[0].defaultTone);
  protected readonly jsonOutputEnabled = signal<boolean>(false);
  protected readonly jsonOutputSchema = signal<string>(USE_CASES[0].defaultJsonSchema);
  protected readonly knowledgeContext = signal<string>(USE_CASES[0].defaultContext);
  protected readonly showContextDrawer = signal<boolean>(false);

  /* ---------- Options spécifiques Image ---------- */
  protected readonly imageMode = signal<'create' | 'edit'>('create');
  protected readonly imageAspectRatio = signal<string>('1:1');
  protected readonly referenceImageUrl = signal<string>('');

  /* ---------- Étape 2 : 2 Blocs par défaut (A & B) + ajout jusqu'à 4 ---------- */
  protected readonly variants = signal<readonly SandboxVariantSlot[]>([
    {
      slotId: 'A',
      label: 'Modèle A',
      modelId: 'google/gemini-2.5-flash',
      reasoningEffort: 'low',
      temperature: 0.4,
      showRawJson: false,
      result: null,
    },
    {
      slotId: 'B',
      label: 'Modèle B',
      modelId: 'google/gemini-2.5-flash',
      reasoningEffort: 'high',
      temperature: 0.4,
      showRawJson: false,
      result: null,
    },
  ]);

  /* ---------- Preset Production retenu ---------- */
  protected readonly retainedPresetJson = signal<string | null>(null);
  protected readonly retainedPresetLabel = signal<string | null>(null);

  /* ---------- Sélecteurs dérivés ---------- */
  protected readonly currentUseCaseConfig = computed(
    () => USE_CASES.find((u) => u.code === this.selectedUseCase()) ?? USE_CASES[0],
  );

  protected readonly activeSandboxKey = computed(
    () => this.keys().find((k) => k.key_kind === 'sandbox' && k.is_active) ?? null,
  );

  protected readonly activeStandardKey = computed(
    () => this.keys().find((k) => k.key_kind === 'standard' && k.is_active) ?? null,
  );

  protected readonly canAddVariant = computed(() => this.variants().length < MAX_VARIANTS);

  /** Modèles proposés : activés d'abord, puis le reste du catalogue (filtrés si cas image). */
  protected readonly selectableModels = computed(() => {
    const all = this.models();
    const isImage = this.selectedUseCase() === 'image_generation';
    const sorted = [...all].sort((a, b) => {
      if (isImage) {
        const aImg = a.output_modalities.includes('image') ? 1 : 0;
        const bImg = b.output_modalities.includes('image') ? 1 : 0;
        if (aImg !== bImg) return bImg - aImg;
      }
      if (a.is_enabled !== b.is_enabled) return a.is_enabled ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    return sorted;
  });

  protected readonly estimatedInputTokens = computed(() => {
    const totalChars =
      this.systemPrompt().length +
      this.userPrompt().length +
      this.tone().length +
      this.knowledgeContext().length +
      (this.jsonOutputEnabled() ? this.jsonOutputSchema().length : 0);
    return Math.max(30, Math.round(totalChars / 3.7));
  });

  protected readonly executedResults = computed(() =>
    this.variants()
      .map((v) => ({ slot: v, res: v.result }))
      .filter((x): x is { slot: SandboxVariantSlot; res: SandboxVariantResultDto } => x.res !== null && x.res.ok),
  );

  /* ---------- Diagnostic FinOps automatique ---------- */
  protected readonly finopsDiagnostic = computed(() => {
    const list = this.executedResults();
    if (list.length < 2) return null;
    const sorted = [...list].sort(
      (a, b) => a.res.projected_monthly_5k_usd - b.res.projected_monthly_5k_usd,
    );
    const cheapest = sorted[0];
    const priciest = sorted[sorted.length - 1];
    const diff = Math.max(0, priciest.res.projected_monthly_5k_usd - cheapest.res.projected_monthly_5k_usd);
    const pct =
      priciest.res.projected_monthly_5k_usd > 0
        ? Math.round((diff / priciest.res.projected_monthly_5k_usd) * 100)
        : 0;
    return {
      cheapestSlot: cheapest.slot.slotId,
      cheapestModel: cheapest.slot.modelId,
      cheapestEffort: cheapest.slot.reasoningEffort || 'défaut',
      cheapestMonthly: cheapest.res.projected_monthly_5k_usd,
      priciestSlot: priciest.slot.slotId,
      priciestModel: priciest.slot.modelId,
      priciestEffort: priciest.slot.reasoningEffort || 'défaut',
      priciestMonthly: priciest.res.projected_monthly_5k_usd,
      diffMonthly: diff,
      pctSaved: pct,
    };
  });

  /* ---------- Graphiques ECharts Comparatifs ---------- */
  protected readonly tokensChartOption = computed<EChartsOption>(() => {
    const list = this.executedResults();
    const labels = list.map(
      (x) =>
        `Mod. ${x.slot.slotId} (${(x.slot.modelId.split('/').pop() ?? x.slot.modelId).slice(0, 18)} · ${x.slot.reasoningEffort || 'défaut'})`,
    );

    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0, itemWidth: 12, itemHeight: 12 },
      grid: { left: 52, right: 16, top: 18, bottom: 42 },
      xAxis: { type: 'category', data: labels },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
      },
      series: [
        {
          name: 'Prompt',
          type: 'bar',
          stack: 'tokens',
          barMaxWidth: 44,
          itemStyle: { color: '#6366f1' },
          data: list.map((x) => x.res.prompt_tokens),
        },
        {
          name: 'Sortie visible',
          type: 'bar',
          stack: 'tokens',
          barMaxWidth: 44,
          itemStyle: { color: '#10b981' },
          data: list.map((x) => x.res.visible_tokens),
        },
        {
          name: 'Raisonnement interne',
          type: 'bar',
          stack: 'tokens',
          barMaxWidth: 44,
          itemStyle: { color: '#f59e0b', borderRadius: [6, 6, 0, 0] },
          data: list.map((x) => x.res.reasoning_tokens),
        },
      ],
    };
  });

  protected readonly monthlyCostChartOption = computed<EChartsOption>(() => {
    const list = this.executedResults();
    const palette = ['#10b981', '#f59e0b', '#4f46e5', '#06b6d4'];
    const labels = list.map((x) => `Modèle ${x.slot.slotId}`);

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        valueFormatter: (v) => `$${Number(v ?? 0).toFixed(2)} / mois`,
      },
      grid: { left: 56, right: 16, top: 18, bottom: 30 },
      xAxis: { type: 'category', data: labels },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } },
        axisLabel: { formatter: (v: number) => `$${v}` },
      },
      series: [
        {
          name: 'Projection 5 000 req/mois',
          type: 'bar',
          barMaxWidth: 48,
          data: list.map((x, idx) => ({
            value: x.res.projected_monthly_5k_usd,
            itemStyle: { color: palette[idx % palette.length], borderRadius: [6, 6, 0, 0] },
          })),
        },
      ],
    };
  });

  ngOnInit(): void {
    void this.loadInitialData();
  }

  protected async loadInitialData(): Promise<void> {
    this.loadingInit.set(true);
    this.errorMessage.set(null);
    try {
      const [models, keys] = await Promise.all([this.api.listModels(), this.api.listKeys()]);
      this.models.set(models);
      this.keys.set(keys);

      // Pré-sélectionner des modèles réellement présents dans le catalogue activé si disponible
      const enabled = models.filter((m) => m.is_enabled);
      const pool = enabled.length > 0 ? enabled : models;
      if (pool.length > 0) {
        const firstId = pool[0].openrouter_model_id;
        const secondId = (pool[1] ?? pool[0]).openrouter_model_id;
        this.variants.update((list) =>
          list.map((v, idx) => ({
            ...v,
            modelId: idx === 0 ? firstId : idx === 1 ? secondId : v.modelId,
          })),
        );
      }
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.loadingInit.set(false);
    }
  }

  /* =========================================================================
     Sélection Cas d'utilisation strict
     ========================================================================= */

  protected selectUseCase(code: SandboxUseCase): void {
    this.selectedUseCase.set(code);
    const cfg = USE_CASES.find((u) => u.code === code) ?? USE_CASES[0];
    this.systemPrompt.set(cfg.defaultSystemPrompt);
    this.userPrompt.set(cfg.defaultUserPrompt);
    this.tone.set(cfg.defaultTone);
    this.jsonOutputSchema.set(cfg.defaultJsonSchema);
    this.knowledgeContext.set(cfg.defaultContext);
    this.showContextDrawer.set(code === 'message_rag');
    this.errorMessage.set(null);

    // Si bascule sur génération d'image, proposer un modèle image-output s'il existe dans le catalogue
    if (code === 'image_generation') {
      const imgModels = this.models().filter((m) => m.output_modalities.includes('image'));
      if (imgModels.length > 0) {
        this.variants.update((list) =>
          list.map((v, idx) => ({
            ...v,
            modelId: (imgModels[idx] ?? imgModels[0]).openrouter_model_id,
            result: null,
          })),
        );
        return;
      }
    }
    this.variants.update((list) => list.map((v) => ({ ...v, result: null })));
  }

  protected onReferenceImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (file.size > 6 * 1024 * 1024) {
      this.errorMessage.set("L'image de référence ne doit pas dépasser 6 Mo.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        this.referenceImageUrl.set(reader.result);
      }
    };
    reader.readAsDataURL(file);
  }

  /* =========================================================================
     Gestion des blocs Modèles (2 par défaut + bouton Ajouter jusqu'à 4)
     ========================================================================= */

  protected addVariantSlot(): void {
    const current = this.variants();
    if (current.length >= MAX_VARIANTS) return;

    const usedIds = new Set(current.map((v) => v.slotId));
    const nextLetter = SLOT_LETTERS.find((l) => !usedIds.has(l)) ?? String(current.length + 1);
    const pool = this.selectableModels();
    const defaultModel =
      pool[current.length]?.openrouter_model_id ??
      current[0]?.modelId ??
      'google/gemini-2.5-flash';

    this.variants.set([
      ...current,
      {
        slotId: nextLetter,
        label: `Modèle ${nextLetter}`,
        modelId: defaultModel,
        reasoningEffort: 'low',
        temperature: 0.4,
        showRawJson: false,
        result: null,
      },
    ]);
  }

  protected removeVariantSlot(slotId: string): void {
    if (this.variants().length <= 2) return;
    this.variants.update((list) => list.filter((v) => v.slotId !== slotId));
  }

  protected updateVariant(slotId: string, patch: Partial<SandboxVariantSlot>): void {
    this.variants.update((list) =>
      list.map((v) => (v.slotId === slotId ? { ...v, ...patch } : v)),
    );
  }

  /* =========================================================================
     Exécution parallèle ("Générer")
     ========================================================================= */

  protected async runComparison(): Promise<void> {
    if (!this.userPrompt().trim()) {
      this.errorMessage.set('Veuillez renseigner un User Prompt avant de générer.');
      return;
    }
    if (this.selectedUseCase() === 'image_generation' && this.imageMode() === 'edit' && !this.referenceImageUrl().trim()) {
      this.errorMessage.set("En mode Modification d'image, fournissez une image de référence (fichier ou URL).");
      return;
    }

    this.isRunning.set(true);
    this.errorMessage.set(null);

    try {
      const response = await this.api.compareSandbox({
        use_case: this.selectedUseCase(),
        system_prompt: this.systemPrompt().trim(),
        user_prompt: this.userPrompt().trim(),
        tone: this.tone().trim() || null,
        json_output_enabled: this.jsonOutputEnabled(),
        json_output_schema: this.jsonOutputEnabled() ? this.jsonOutputSchema().trim() : null,
        knowledge_context: this.knowledgeContext().trim() || null,
        image_mode: this.imageMode(),
        image_aspect_ratio: this.selectedUseCase() === 'image_generation' ? this.imageAspectRatio() : null,
        reference_image_url:
          this.selectedUseCase() === 'image_generation' && this.imageMode() === 'edit'
            ? this.referenceImageUrl().trim() || null
            : null,
        variants: this.variants().map((v) => ({
          slot_id: v.slotId,
          model_id: v.modelId.trim(),
          reasoning_effort: v.reasoningEffort || null,
          temperature: v.temperature,
        })),
      });

      const bySlot = new Map(response.results.map((r) => [r.slot_id, r]));
      this.variants.update((list) =>
        list.map((v) => ({ ...v, result: bySlot.get(v.slotId) ?? null })),
      );
      this.sessionCostUsd.update((c) => c + response.total_batch_cost_usd);
      this.lastKeySource.set(response.key_source);

      this.flashNotice(
        `Comparaison terminée (${response.results.length} modèles) — Coût réel du run : ${this.formatCost6(response.total_batch_cost_usd)} via clé ${response.key_source === 'sandbox' ? 'Sandbox isolée' : 'Standard'}.`,
      );
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.isRunning.set(false);
    }
  }

  /* =========================================================================
     Enregistrement clé Sandbox chiffrée (Fernet en base)
     ========================================================================= */

  protected async saveSandboxKey(): Promise<void> {
    const raw = this.sandboxKeyInput().trim();
    if (raw.length < 8) {
      this.errorMessage.set('Veuillez coller une clé OpenRouter Sandbox valide.');
      return;
    }
    this.savingKey.set(true);
    this.errorMessage.set(null);
    try {
      const res = await this.api.saveKey({
        key_kind: 'sandbox',
        api_key: raw,
        label: this.sandboxKeyLabel().trim() || 'Clé Sandbox isolée',
        verify_immediately: true,
      });
      this.keys.set(await this.api.listKeys());
      this.sandboxKeyInput.set('');
      this.showSandboxKeyModal.set(false);
      this.flashNotice(`Clé Sandbox chiffrée en base : ${res.message}`);
    } catch (err) {
      this.errorMessage.set(toApiError(err).message);
    } finally {
      this.savingKey.set(false);
    }
  }

  /* =========================================================================
     Preset Production (applique directement sur /modeles-ia_v2 + snippet JSON)
     ========================================================================= */

  protected async applyAsProductionPreset(slot: SandboxVariantSlot): Promise<void> {
    const cfg = this.currentUseCaseConfig();
    const snippetObj: Record<string, unknown> = {
      use_case: cfg.code,
      task_code: cfg.targetTaskCode,
      model: slot.modelId,
      temperature: slot.temperature,
      ...(slot.reasoningEffort ? { reasoning: { effort: slot.reasoningEffort } } : {}),
    };
    this.retainedPresetJson.set(JSON.stringify(snippetObj, null, 2));
    this.retainedPresetLabel.set(`Modèle ${slot.slotId} (${slot.modelId}) · ${cfg.title}`);

    // Si le modèle existe en base locale, l'affecter aussi directement à la spécialité métier IAGORA
    const found = this.models().find((m) => m.openrouter_model_id === slot.modelId);
    if (found) {
      try {
        await this.api.updateAssignment(cfg.targetTaskCode, {
          id_ai_models: found.id_ai_models,
          reasoning_effort: (slot.reasoningEffort || null) as AiReasoningEffort | null,
        });
        this.flashNotice(
          `Preset Production enregistré et appliqué sur « ${cfg.targetTaskCode} » (${found.name}, effort ${slot.reasoningEffort || 'défaut'}).`,
        );
        return;
      } catch (err) {
        this.errorMessage.set(toApiError(err).message);
        return;
      }
    }

    this.flashNotice(`Preset Production prêt à copier pour ${slot.modelId}.`);
  }

  protected async copyPresetJson(): Promise<void> {
    const text = this.retainedPresetJson();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      this.flashNotice('Configuration JSON copiée dans le presse-papiers.');
    } catch {
      this.errorMessage.set('Impossible de copier automatiquement dans le presse-papiers.');
    }
  }

  /* ---------- Formatters ---------- */

  protected formatCost6(v: number): string {
    return '$' + Number(v).toFixed(6);
  }

  protected formatCost2(v: number): string {
    return '$' + Number(v).toFixed(2);
  }

  protected formatJson(obj: unknown): string {
    return JSON.stringify(obj, null, 2);
  }

  protected getReasoningPct(res: SandboxVariantResultDto): number {
    if (res.completion_tokens <= 0) return 0;
    return Number(((res.reasoning_tokens / res.completion_tokens) * 100).toFixed(1));
  }

  private flashNotice(msg: string): void {
    this.notice.set(msg);
    setTimeout(() => {
      if (this.notice() === msg) this.notice.set(null);
    }, 5500);
  }
}
