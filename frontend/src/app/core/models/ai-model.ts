/**
 * Modèles IA et fournisseurs — configuration du moteur d'intelligence artificielle.
 */

export type AiSpecialty =
  | 'text-generation'
  | 'image-description'
  | 'image-generation'
  | 'rag-embedding';

export const AI_SPECIALTIES: readonly AiSpecialty[] = [
  'text-generation',
  'image-description',
  'image-generation',
  'rag-embedding',
];

export const AI_SPECIALTY_LABELS: Readonly<Record<AiSpecialty, string>> = {
  'text-generation': 'Génération de texte',
  'image-description': "Description d'image (Vision)",
  'image-generation': "Génération & retouche d'image",
  'rag-embedding': 'RAG / Embedding',
};

export const AI_SPECIALTY_HINTS: Readonly<Record<AiSpecialty, string>> = {
  'text-generation': 'Rédaction de publications, angles éditoriaux, variations et réponses messagerie.',
  'image-description': 'Analyse sémantique des médias de référence (logos, portraits, chartes, salles).',
  'image-generation': 'Création de visuels aux formats réseaux, modifiable par conversation avec le modèle.',
  'rag-embedding': 'Vectorisation et recherche documentaire dans la base de connaissances Datum Academy.',
};

export type AiProvider =
  | 'anthropic'
  | 'openai'
  | 'google'
  | 'mistral'
  | 'black-forest-labs'
  | 'local';

export const AI_PROVIDERS: readonly AiProvider[] = [
  'anthropic',
  'openai',
  'google',
  'mistral',
  'black-forest-labs',
  'local',
];

export const AI_PROVIDER_LABELS: Readonly<Record<AiProvider, string>> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google Cloud (Gemini)',
  mistral: 'Mistral AI',
  'black-forest-labs': 'Black Forest Labs / HF',
  local: 'Hébergement local (Ollama)',
};

export type AiModelStatus = 'active' | 'inactive' | 'testing' | 'error';

export const AI_STATUS_LABELS: Readonly<Record<AiModelStatus, string>> = {
  active: 'Opérationnel',
  inactive: 'Inactif',
  testing: 'En test',
  error: 'Erreur connexion',
};

export interface AiModelUsageStats {
  /** Nombre total d'appels API sur les 30 derniers jours. */
  readonly callsCount: number;
  /** Tokens d'entrée consommés (prompt + contexte RAG). */
  readonly promptTokens: number;
  /** Tokens de sortie générés. */
  readonly completionTokens: number;
  /** Tokens lus depuis le cache (économie de coût). */
  readonly cachedTokens?: number;
  /** Nombre d'images générées ou retouchées par conversation (pour les modèles image). */
  readonly imagesGenerated?: number;
  /** Coût cumulé sur 30 jours en USD. */
  readonly costUsd: number;
  /** Taux de succès des appels en %. */
  readonly successRatePct: number;
  /** Part d'utilisation relative parmi tous les appels (%). */
  readonly sharePct: number;
}

export interface AiModel {
  readonly id: string;
  readonly name: string;
  readonly technicalId: string;
  readonly provider: AiProvider;
  readonly specialties: readonly AiSpecialty[];
  readonly status: AiModelStatus;
  readonly latencyMs: number;
  readonly contextWindowTokens?: number;
  readonly costEstimate: string;
  readonly description: string;
  /** Pour la génération d'image : permet la retouche par conversation consigne par consigne. */
  readonly supportsConversationRetouch?: boolean;
  /** Statistiques d'usage et de consommation sur 30 jours. */
  readonly usage: AiModelUsageStats;
}

/** Affectation du modèle actif par défaut pour chaque spécialité métier. */
export interface TaskAssignments {
  readonly textModelId: string;
  readonly visionModelId: string;
  readonly imageModelId: string;
  readonly ragModelId: string;
}

/** Paramètres d'accès, d'exécution et de quotas d'un fournisseur. */
export interface ProviderConfig {
  readonly provider: AiProvider;
  readonly apiKeyMasked: string;
  readonly endpointUrl: string;
  readonly temperature: number;
  readonly maxTokens: number;
  readonly isConnected: boolean;
  readonly lastPingMs?: number;
  readonly lastTestedAt?: string;
  /** Plafond budgétaire mensuel en USD (0 = gratuit/illimité local). */
  readonly monthlyBudgetLimitUsd: number;
  /** Montant dépensé sur le mois en cours en USD. */
  readonly spentUsdThisMonth: number;
  /** Quota mensuel de tokens alloué au fournisseur. */
  readonly monthlyTokenQuota: number;
  /** Tokens consommés sur le mois en cours. */
  readonly tokensUsedThisMonth: number;
}
