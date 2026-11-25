import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../../environments/environment';

export type OpenRouterKeyKind = 'management' | 'standard' | 'sandbox';
export type OpenRouterProviderSort = 'price' | 'throughput' | 'latency' | 'exacto';
export type AiReasoningEffort = 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh';
export type SandboxUseCase = 'publication_text' | 'image_generation' | 'message_rag';
export type AiPromptKind = 'system' | 'template';
export type AiPromptTaskCode =
  | 'publication_description'
  | 'message_reply'
  | 'image_generation'
  | 'image_description'
  | 'rag_synthesis'
  | 'newsletter_content';
export type AiTaskCode =
  | 'text-generation'
  | 'image-description'
  | 'image-generation'
  | 'rag-embedding';

export interface OpenRouterKeyDto {
  readonly id_openrouter_api_keys: number;
  readonly key_kind: OpenRouterKeyKind;
  readonly label: string | null;
  readonly key_masked: string;
  readonly is_active: boolean;
  readonly last_verified_at: string | null;
  readonly last_verify_ok: boolean | null;
  readonly last_verify_message: string | null;
  readonly obtained_at: string;
  readonly superseded_at: string | null;
  readonly revoked_at: string | null;
  readonly created_by_name: string | null;
  readonly created_at: string;
}

export interface OpenRouterKeySaveRequest {
  readonly key_kind: OpenRouterKeyKind;
  readonly api_key: string;
  readonly label?: string | null;
  readonly verify_immediately?: boolean;
}

export interface OpenRouterKeyVerifyDto {
  readonly verified: boolean;
  readonly message: string;
  readonly key: OpenRouterKeyDto;
  readonly total_credits: number | null;
  readonly total_usage: number | null;
  readonly remaining_credits: number | null;
  readonly key_label: string | null;
  readonly limit_remaining: number | null;
  readonly is_free_tier: boolean | null;
}

export interface OpenRouterCreditsDto {
  readonly available: boolean;
  readonly total_credits: number | null;
  readonly total_usage: number | null;
  readonly remaining_credits: number | null;
  readonly error: string | null;
}

export interface OpenRouterOverviewDto {
  readonly management_key: OpenRouterKeyDto | null;
  readonly standard_key: OpenRouterKeyDto | null;
  readonly credits: OpenRouterCreditsDto;
  readonly workspaces_count: number;
  readonly selected_workspace_name: string | null;
  readonly models_total_count: number;
  readonly models_enabled_count: number;
}

export interface OpenRouterActivityItemDto {
  readonly date: string;
  readonly model: string;
  readonly provider_name: string | null;
  readonly workspace_id: string | null;
  readonly workspace_name: string | null;
  readonly usage_usd: number;
  readonly requests: number;
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly reasoning_tokens: number;
}

export interface OpenRouterWorkspaceCostDto {
  readonly workspace_id: string;
  readonly workspace_name: string;
  readonly cost_usd: number;
  readonly requests: number;
  readonly tokens: number;
}

export interface OpenRouterDailyPointDto {
  readonly date: string;
  readonly cost_usd: number;
  readonly tokens: number;
  readonly requests: number;
}

export interface OpenRouterModelCostDto {
  readonly model: string;
  readonly cost_usd: number;
  readonly requests: number;
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly reasoning_tokens: number;
}

export interface OpenRouterRemoteKeyDto {
  readonly hash: string;
  readonly label: string;
  readonly limit: number | null;
  readonly limit_remaining: number | null;
  readonly usage: number;
  readonly usage_daily: number | null;
  readonly usage_weekly: number | null;
  readonly usage_monthly: number | null;
  readonly disabled: boolean;
  readonly expires_at: string | null;
  readonly created_at: string | null;
}

export interface OpenRouterDashboardDto {
  readonly scope_workspace_id: string | null;
  readonly scope_label: string;
  readonly credits: OpenRouterCreditsDto;
  readonly total_cost_usd: number;
  readonly total_requests: number;
  readonly total_prompt_tokens: number;
  readonly total_completion_tokens: number;
  readonly total_reasoning_tokens: number;
  readonly avg_cost_per_request_usd: number;
  readonly active_remote_keys_count: number;
  readonly total_remote_keys_count: number;
  readonly daily_series: readonly OpenRouterDailyPointDto[];
  readonly by_model: readonly OpenRouterModelCostDto[];
  readonly by_workspace: readonly OpenRouterWorkspaceCostDto[];
  readonly activity: readonly OpenRouterActivityItemDto[];
  readonly remote_keys: readonly OpenRouterRemoteKeyDto[];
  readonly warnings: readonly string[];
}

export interface AiWorkspaceDto {
  readonly id_ai_workspaces: number;
  readonly openrouter_workspace_id: string;
  readonly name: string;
  readonly slug: string | null;
  readonly description: string | null;
  readonly default_text_model: string | null;
  readonly default_image_model: string | null;
  readonly default_provider_sort: string | null;
  readonly monthly_budget_usd: number | null;
  readonly is_default: boolean;
  readonly is_selected: boolean;
  readonly last_synced_at: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface AiWorkspaceCreateRequest {
  readonly name: string;
  readonly description?: string | null;
  readonly default_text_model?: string | null;
  readonly default_image_model?: string | null;
  readonly default_provider_sort?: OpenRouterProviderSort | null;
  readonly monthly_budget_usd?: number | null;
}

export interface AiWorkspaceUpdateRequest {
  readonly name?: string | null;
  readonly description?: string | null;
  readonly default_text_model?: string | null;
  readonly default_image_model?: string | null;
  readonly default_provider_sort?: OpenRouterProviderSort | null;
  readonly monthly_budget_usd?: number | null;
  readonly is_selected?: boolean | null;
}

export interface AiWorkspaceSyncDto {
  readonly synced_count: number;
  readonly message: string;
  readonly workspaces: readonly AiWorkspaceDto[];
}

export interface AiModelDto {
  readonly id_ai_models: number;
  readonly openrouter_model_id: string;
  readonly name: string;
  readonly provider_slug: string;
  readonly description: string | null;
  readonly context_length: number | null;
  readonly pricing_prompt: string | null;
  readonly pricing_completion: string | null;
  readonly input_modalities: readonly string[];
  readonly output_modalities: readonly string[];
  readonly is_enabled: boolean;
  readonly last_synced_at: string | null;
}

export interface AiModelsSyncDto {
  readonly synced_count: number;
  readonly enabled_count: number;
  readonly message: string;
}

export interface AiTaskAssignmentDto {
  readonly task_code: AiTaskCode;
  readonly task_label: string;
  readonly id_ai_models: number | null;
  readonly model_name: string | null;
  readonly openrouter_model_id: string | null;
  readonly id_ai_workspaces: number | null;
  readonly workspace_name: string | null;
  readonly reasoning_effort: AiReasoningEffort | null;
  readonly updated_at: string;
}

export interface AiTaskAssignmentUpdateRequest {
  readonly id_ai_models: number | null;
  readonly id_ai_workspaces?: number | null;
  readonly reasoning_effort?: AiReasoningEffort | null;
}

export interface SandboxVariantInputDto {
  readonly slot_id: string;
  readonly model_id: string;
  readonly reasoning_effort: AiReasoningEffort | null;
  readonly temperature: number;
}

export interface SandboxCompareRequestDto {
  readonly use_case: SandboxUseCase;
  readonly system_prompt: string;
  readonly user_prompt: string;
  readonly tone?: string | null;
  readonly max_tokens?: number | null;
  readonly json_output_enabled: boolean;
  readonly json_output_schema?: string | null;
  readonly knowledge_context?: string | null;
  readonly image_mode?: 'create' | 'edit';
  readonly image_aspect_ratio?: string | null;
  readonly reference_image_url?: string | null;
  readonly reference_image_urls?: readonly string[];
  readonly reference_media_notes?: readonly string[];
  readonly variants: readonly SandboxVariantInputDto[];
}

export interface SandboxVariantResultDto {
  readonly slot_id: string;
  readonly model_id: string;
  readonly reasoning_effort: AiReasoningEffort | null;
  readonly temperature: number;
  readonly ok: boolean;
  readonly error: string | null;
  readonly text: string;
  readonly images: readonly string[];
  readonly stored_image_keys?: readonly string[];
  readonly reasoning_trace: string | null;
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly visible_tokens: number;
  readonly reasoning_tokens: number;
  readonly cached_tokens: number;
  readonly total_tokens: number;
  readonly cost_usd: number;
  readonly projected_monthly_5k_usd: number;
  readonly latency_ms: number;
  readonly raw_usage_json: Record<string, unknown> | null;
  readonly raw_response_json?: Record<string, unknown> | null;
}

export interface SandboxCompareResponseDto {
  readonly id_ai_sandbox_runs: number | null;
  readonly use_case: SandboxUseCase;
  readonly key_source: 'sandbox' | 'standard';
  readonly key_masked: string;
  readonly total_batch_cost_usd: number;
  readonly results: readonly SandboxVariantResultDto[];
  readonly created_at: string | null;
}

export interface SandboxRunHistoryDto {
  readonly id_ai_sandbox_runs: number;
  readonly use_case: SandboxUseCase;
  readonly system_prompt: string;
  readonly user_prompt: string;
  readonly tone: string | null;
  readonly json_output_enabled: boolean;
  readonly json_output_schema: string | null;
  readonly knowledge_context: string | null;
  readonly image_mode: 'create' | 'edit' | null;
  readonly image_aspect_ratio: string | null;
  readonly key_source: 'sandbox' | 'standard';
  readonly key_masked: string;
  readonly total_batch_cost_usd: number;
  readonly variants: readonly SandboxVariantInputDto[];
  readonly results: readonly SandboxVariantResultDto[];
  readonly created_by_name: string | null;
  readonly created_at: string;
}

export interface AiPromptTaskDto {
  readonly code: AiPromptTaskCode;
  readonly label: string;
  readonly description: string;
  readonly count: number;
  readonly has_default: boolean;
}

export interface AiPromptDto {
  readonly id_ai_prompts: number;
  readonly prompt_kind: AiPromptKind;
  readonly task_code: AiPromptTaskCode;
  readonly title: string;
  readonly version_number: number;
  readonly content: string;
  readonly char_count: number;
  readonly description: string | null;
  readonly is_default: boolean;
  readonly created_by_name: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface AiPromptCreateRequest {
  readonly prompt_kind: AiPromptKind;
  readonly task_code: AiPromptTaskCode;
  readonly title: string;
  readonly content: string;
  readonly description?: string | null;
  readonly is_default?: boolean;
}

export interface AiPromptUpdateRequest {
  readonly title?: string;
  readonly content?: string;
  readonly description?: string | null;
}

/* ---------- Génération de publications v2 ---------- */

export interface ActivePromptSummaryDto {
  readonly id_ai_prompts: number;
  readonly title: string;
  readonly version_number: number;
}

export interface ActiveTaskModelSummaryDto {
  readonly task_code: AiTaskCode;
  readonly model_id: string | null;
  readonly model_name: string | null;
  readonly reasoning_effort: AiReasoningEffort | null;
}

export interface PublicationGenerationContextDto {
  readonly has_api_key: boolean;
  readonly key_source: 'standard' | 'sandbox' | null;
  readonly text_model: ActiveTaskModelSummaryDto;
  readonly image_model: ActiveTaskModelSummaryDto;
  readonly text_system_prompt: ActivePromptSummaryDto | null;
  readonly text_template_prompt: ActivePromptSummaryDto | null;
  readonly image_system_prompt: ActivePromptSummaryDto | null;
  readonly image_template_prompt: ActivePromptSummaryDto | null;
}

export interface PublicationTextGenerationRequestDto {
  readonly subject: string;
  readonly format: string;
  readonly networks: readonly string[];
  readonly tone: string;
  readonly language: string;
  readonly hashtags_min: number;
  readonly hashtags_max: number;
  readonly use_knowledge_base: boolean;
  readonly run_number: number;
  readonly angles?: readonly string[];
}

export interface PublicationTextProposalDto {
  readonly id: string;
  readonly network: string;
  readonly angle: string;
  readonly run_number: number;
  readonly title: string;
  readonly paragraphs: readonly string[];
  readonly hashtags: readonly string[];
  readonly extra_hashtag_count: number;
}

export interface PublicationTextGenerationResponseDto {
  readonly run_number: number;
  readonly model_id: string;
  readonly model_name: string | null;
  readonly reasoning_effort: AiReasoningEffort | null;
  readonly system_prompt_label: string | null;
  readonly template_prompt_label: string | null;
  readonly key_source: 'standard' | 'sandbox';
  readonly latency_ms: number;
  readonly total_tokens: number;
  readonly cost_usd: number;
  readonly proposals_by_network: Readonly<Record<string, readonly PublicationTextProposalDto[]>>;
}

export interface PublicationVisualGenerationRequestDto {
  readonly mode: 'create' | 'retouch';
  readonly subject: string;
  readonly visual_description: string;
  readonly selected_caption: string;
  readonly format: string;
  readonly aspect_ratio: string;
  readonly retouch_instruction?: string | null;
  readonly source_image_url?: string | null;
  readonly reference_media_ids: readonly number[];
}

export interface PublicationVisualGenerationResponseDto {
  readonly image_url: string;
  readonly storage_key: string | null;
  readonly id_media: number | null;
  readonly assistant_message: string;
  readonly model_id: string;
  readonly model_name: string | null;
  readonly reasoning_effort: AiReasoningEffort | null;
  readonly system_prompt_label: string | null;
  readonly template_prompt_label: string | null;
  readonly key_source: 'standard' | 'sandbox';
  readonly latency_ms: number;
  readonly cost_usd: number;
}

@Injectable({ providedIn: 'root' })
export class OpenRouterApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/openrouter`;

  overview(): Promise<OpenRouterOverviewDto> {
    return firstValueFrom(this.http.get<OpenRouterOverviewDto>(`${this.base}/overview`));
  }

  dashboard(workspaceId?: string | null): Promise<OpenRouterDashboardDto> {
    let params = new HttpParams();
    if (workspaceId) {
      params = params.set('workspace_id', workspaceId);
    }
    return firstValueFrom(
      this.http.get<OpenRouterDashboardDto>(`${this.base}/dashboard`, { params }),
    );
  }

  /* ---------- Clés chiffrées ---------- */

  listKeys(): Promise<readonly OpenRouterKeyDto[]> {
    return firstValueFrom(this.http.get<OpenRouterKeyDto[]>(`${this.base}/keys`));
  }

  saveKey(payload: OpenRouterKeySaveRequest): Promise<OpenRouterKeyVerifyDto> {
    return firstValueFrom(this.http.post<OpenRouterKeyVerifyDto>(`${this.base}/keys`, payload));
  }

  verifyKey(idKey: number): Promise<OpenRouterKeyVerifyDto> {
    return firstValueFrom(
      this.http.post<OpenRouterKeyVerifyDto>(`${this.base}/keys/${idKey}/verify`, {}),
    );
  }

  revokeKey(idKey: number): Promise<OpenRouterKeyDto> {
    return firstValueFrom(
      this.http.post<OpenRouterKeyDto>(`${this.base}/keys/${idKey}/revoke`, {}),
    );
  }

  /* ---------- Workspaces ---------- */

  listWorkspaces(): Promise<readonly AiWorkspaceDto[]> {
    return firstValueFrom(this.http.get<AiWorkspaceDto[]>(`${this.base}/workspaces`));
  }

  syncWorkspaces(): Promise<AiWorkspaceSyncDto> {
    return firstValueFrom(this.http.post<AiWorkspaceSyncDto>(`${this.base}/workspaces/sync`, {}));
  }

  createWorkspace(payload: AiWorkspaceCreateRequest): Promise<AiWorkspaceDto> {
    return firstValueFrom(this.http.post<AiWorkspaceDto>(`${this.base}/workspaces`, payload));
  }

  updateWorkspace(idWorkspace: number, payload: AiWorkspaceUpdateRequest): Promise<AiWorkspaceDto> {
    return firstValueFrom(
      this.http.patch<AiWorkspaceDto>(`${this.base}/workspaces/${idWorkspace}`, payload),
    );
  }

  deleteWorkspace(idWorkspace: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/workspaces/${idWorkspace}`));
  }

  /* ---------- Modèles & Affectations ---------- */

  listModels(filters?: {
    search?: string;
    provider?: string;
    enabledOnly?: boolean;
  }): Promise<readonly AiModelDto[]> {
    let params = new HttpParams();
    if (filters?.search) params = params.set('search', filters.search);
    if (filters?.provider) params = params.set('provider', filters.provider);
    if (filters?.enabledOnly) params = params.set('enabled_only', 'true');
    return firstValueFrom(this.http.get<AiModelDto[]>(`${this.base}/models`, { params }));
  }

  syncModels(): Promise<AiModelsSyncDto> {
    return firstValueFrom(this.http.post<AiModelsSyncDto>(`${this.base}/models/sync`, {}));
  }

  toggleModel(idModel: number, isEnabled: boolean): Promise<AiModelDto> {
    return firstValueFrom(
      this.http.patch<AiModelDto>(`${this.base}/models/${idModel}`, { is_enabled: isEnabled }),
    );
  }

  listAssignments(): Promise<readonly AiTaskAssignmentDto[]> {
    return firstValueFrom(this.http.get<AiTaskAssignmentDto[]>(`${this.base}/assignments`));
  }

  updateAssignment(
    taskCode: AiTaskCode,
    payload: AiTaskAssignmentUpdateRequest,
  ): Promise<AiTaskAssignmentDto> {
    return firstValueFrom(
      this.http.put<AiTaskAssignmentDto>(`${this.base}/assignments/${taskCode}`, payload),
    );
  }

  /* ---------- Bac à sable IA ---------- */

  compareSandbox(payload: SandboxCompareRequestDto): Promise<SandboxCompareResponseDto> {
    return firstValueFrom(
      this.http.post<SandboxCompareResponseDto>(`${this.base}/sandbox/compare`, payload),
    );
  }

  listSandboxHistory(useCase?: SandboxUseCase | null, limit = 50): Promise<readonly SandboxRunHistoryDto[]> {
    let params = new HttpParams().set('limit', String(limit));
    if (useCase) {
      params = params.set('use_case', useCase);
    }
    return firstValueFrom(
      this.http.get<SandboxRunHistoryDto[]>(`${this.base}/sandbox/history`, { params }),
    );
  }

  deleteSandboxHistory(idRun: number): Promise<void> {
    return firstValueFrom(
      this.http.delete<void>(`${this.base}/sandbox/history/${idRun}`),
    );
  }

  /* ---------- Prompts système & Prompt templates ---------- */

  listPromptTasks(kind: AiPromptKind): Promise<readonly AiPromptTaskDto[]> {
    const params = new HttpParams().set('kind', kind);
    return firstValueFrom(
      this.http.get<AiPromptTaskDto[]>(`${this.base}/prompts/tasks`, { params }),
    );
  }

  listPrompts(kind: AiPromptKind, taskCode?: AiPromptTaskCode | null): Promise<readonly AiPromptDto[]> {
    let params = new HttpParams().set('kind', kind);
    if (taskCode) {
      params = params.set('task_code', taskCode);
    }
    return firstValueFrom(
      this.http.get<AiPromptDto[]>(`${this.base}/prompts`, { params }),
    );
  }

  createPrompt(payload: AiPromptCreateRequest): Promise<AiPromptDto> {
    return firstValueFrom(this.http.post<AiPromptDto>(`${this.base}/prompts`, payload));
  }

  updatePrompt(idPrompt: number, payload: AiPromptUpdateRequest): Promise<AiPromptDto> {
    return firstValueFrom(
      this.http.patch<AiPromptDto>(`${this.base}/prompts/${idPrompt}`, payload),
    );
  }

  setDefaultPrompt(idPrompt: number): Promise<AiPromptDto> {
    return firstValueFrom(
      this.http.post<AiPromptDto>(`${this.base}/prompts/${idPrompt}/set-default`, {}),
    );
  }

  deletePrompt(idPrompt: number): Promise<void> {
    return firstValueFrom(this.http.delete<void>(`${this.base}/prompts/${idPrompt}`));
  }

  /* ---------- Génération de publications v2 ---------- */

  generationContext(): Promise<PublicationGenerationContextDto> {
    return firstValueFrom(
      this.http.get<PublicationGenerationContextDto>(`${this.base}/generation/context`),
    );
  }

  generatePublicationTexts(
    payload: PublicationTextGenerationRequestDto,
  ): Promise<PublicationTextGenerationResponseDto> {
    return firstValueFrom(
      this.http.post<PublicationTextGenerationResponseDto>(`${this.base}/generation/texts`, payload),
    );
  }

  generatePublicationVisual(
    payload: PublicationVisualGenerationRequestDto,
  ): Promise<PublicationVisualGenerationResponseDto> {
    return firstValueFrom(
      this.http.post<PublicationVisualGenerationResponseDto>(
        `${this.base}/generation/visual`,
        payload,
      ),
    );
  }
}
