import axios, { AxiosInstance } from 'axios';
import { SERVICE_ENDPOINTS } from '../config/services';
import { authService } from '../features/auth/services/authService';
import type { ResearchModelOption, ResearchStockRow } from '../features/research/types';
export type { ResearchModelOption, ResearchStockRow } from '../features/research/types';

export type ResearchSignal = 'buy' | 'hold' | 'sell';
export type ResearchConfidence = 'high' | 'medium' | 'watch';

export interface ResearchRunOption {
  runId: string;
  modelId: string;
  inferenceDate: string | null;
  targetDate: string | null;
  status: 'completed' | 'running' | 'failed';
  universeLabel: string;
  stockCount?: number;
  avgScore?: number;
  lastUpdatedAt?: string | null;
}

export interface ResearchOverviewData {
  activeModelId: string | null;
  activeRunId: string | null;
  models: ResearchModelOption[];
  runs: ResearchRunOption[];
  summary: {
    total: number;
    avgScore: number;
    highConfidenceCount: number;
    strongCount: number;
    lastUpdatedAt: string | null;
  };
  filters: {
    sectors: string[];
    concepts: string[];
    indices?: string[];
  };
  items: ResearchStockRow[];
  pagination?: {
    limit: number;
    offset: number;
    returned: number;
    total: number;
    hasMore: boolean;
  };
}

export interface ResearchOverviewQuery {
  modelId?: string;
  runId?: string;
  keyword?: string;
  minScore?: number;
  minConsecutiveLimitUpDays?: number;
  minTurnoverRate?: number;
  maxTurnoverRate?: number;
  minAmount?: number;
  maxAmount?: number;
  volumeTrendOnly?: boolean;
  highConfidenceOnly?: boolean;
  sectors?: string[];
  concepts?: string[];
  indices?: string[];
  sortBy?: 'score' | 'latest_change' | 'amount' | 'turnover_rate' | 'consecutive_limit_up_days' | 'updated_at';
  limit?: number;
  offset?: number;
}

export interface FactorCandidate {
  id: string;
  name: string;
  expression: string;
  expressionHash: string;
  description?: string | null;
  source: string;
  family?: string | null;
  status: 'draft' | 'evaluating' | 'validated' | 'rejected' | 'promoted' | 'archived';
  tags: string[];
  metadata: Record<string, any>;
  latestRun?: FactorEvaluationRun | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorEvaluationRun {
  id: string;
  candidateId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | string;
  params: Record<string, any>;
  metrics?: Record<string, any> | null;
  gateDecision: {
    eligible?: boolean;
    reasons?: string[];
    [key: string]: any;
  };
  reportUrl?: string | null;
  errorMessage?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorValueItem {
  candidateId: string;
  runId: string;
  tradeDate: string | null;
  symbol: string;
  factorValue: number | null;
  source: string;
  createdAt: string | null;
}

export interface FactorRunValuesResult {
  run: FactorEvaluationRun;
  summary: {
    total: number;
    tradeDateCount: number;
    symbolCount: number;
    minTradeDate: string | null;
    maxTradeDate: string | null;
    minFactorValue: number | null;
    maxFactorValue: number | null;
    nullValueCount?: number;
    invalidSymbolCount?: number;
    sourceCount?: number;
    invalidSymbolSamples?: string[];
    sourceDistribution?: Array<{ source: string; count: number }>;
    recentDateDistribution?: Array<{ tradeDate: string | null; count: number }>;
  };
  items: FactorValueItem[];
  pagination: {
    limit: number;
    offset: number;
    returned: number;
    hasMore: boolean;
  };
}

export interface FactorFeaturePromotion {
  id: string;
  candidateId: string;
  runId: string;
  featureKey: string;
  featureId: string;
  versionId?: string | null;
  status: 'materialized' | 'pending_materialization' | 'unknown' | string;
  materializationStatus: 'materialized' | 'pending_materialization' | 'unknown' | string;
  metadata: Record<string, any>;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorSignalRun {
  id: string;
  candidateId: string;
  factorRunId: string;
  tradeDate: string | null;
  status: string;
  topN: number;
  bottomN: number;
  longShort: boolean;
  publishStream: boolean;
  signalCount: number;
  streamPublishedCount: number;
  metadata: Record<string, any>;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorCampaignItem {
  campaignId: string;
  candidateId?: string | null;
  runId?: string | null;
  generation: number;
  rankNo: number;
  expression: string;
  status: string;
  score?: number | null;
  reason?: string | null;
  metrics?: Record<string, any> | null;
  metadata?: Record<string, any> | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorCampaign {
  id: string;
  name: string;
  strategy: string;
  status: string;
  seedExpression?: string | null;
  params: Record<string, any>;
  summary: Record<string, any>;
  metadata: Record<string, any>;
  items: FactorCampaignItem[];
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorCampaignWorkerEvent {
  id: string;
  eventType: string;
  campaignId?: string | null;
  tenantId?: string | null;
  userId?: string | null;
  workerId?: string | null;
  attemptNo?: number | null;
  durationMs?: number | null;
  heartbeatAt?: string | null;
  status: string;
  details: Record<string, any>;
  createdAt: string | null;
}

export interface FactorValueBackfillJob {
  id: string;
  tenantId: string;
  userId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | string;
  target: {
    runIds?: string[];
    candidateIds?: string[];
    promotionIds?: string[];
    [key: string]: any;
  };
  params: Record<string, any>;
  result?: Record<string, any> | null;
  errorMessage?: string | null;
  workerId?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorValueBackfillEvent {
  id: string;
  jobId?: string | null;
  tenantId?: string | null;
  userId?: string | null;
  workerId?: string | null;
  eventType: string;
  status: string;
  details: Record<string, any>;
  createdAt: string | null;
}

export interface FactorTrainingRun {
  id: string;
  promotionId: string;
  candidateId: string;
  factorRunId: string;
  trainingRunId?: string | null;
  status: string;
  trainingStatus?: string | null;
  trainingProgress?: number | null;
  trainingResult?: Record<string, any>;
  trainingComparison?: Record<string, any>;
  trainingGate?: Record<string, any>;
  featureKey: string;
  featureSetVersionId?: string | null;
  requestPayload: Record<string, any>;
  response: Record<string, any>;
  metadata: Record<string, any>;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface FactorApprovalAudit {
  id: string;
  tenantId: string;
  userId: string;
  trainingId: string;
  factorRunId?: string | null;
  promotionId?: string | null;
  candidateId?: string | null;
  modelId: string;
  action: string;
  status: string;
  reason?: string | null;
  idempotent: boolean;
  requestMetadata: Record<string, any>;
  approval: Record<string, any>;
  defaultModel: Record<string, any>;
  gate: Record<string, any>;
  createdAt: string | null;
}

export interface FactorApprovalRequest {
  id: string;
  tenantId: string;
  userId: string;
  trainingId: string;
  modelId: string;
  status: string;
  requestedBy?: string | null;
  requestReason?: string | null;
  requestMetadata: Record<string, any>;
  reviewerUserId?: string | null;
  reviewerNote?: string | null;
  decision: Record<string, any>;
  reviewedAt?: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  idempotent?: boolean;
}

export interface FactorApprovalPolicy {
  tenantId: string;
  enabled: boolean;
  allowDirectApproval: boolean;
  allowSelfApproval: boolean;
  minApprovals: number;
  reviewerPermission: string;
  metadata: Record<string, any>;
  updatedBy?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface FactorHealthAlert {
  level: 'critical' | 'warning' | 'info' | string;
  code: string;
  message: string;
  count?: number;
  [key: string]: any;
}

export interface FactorResearchHealth {
  tenantId: string;
  userId: string;
  windowHours: number;
  status: 'healthy' | 'warning' | 'critical' | string;
  statusCounts: Record<string, Record<string, number>>;
  indicators: Record<string, number>;
  slo?: {
    status?: 'met' | 'breached' | string;
    metrics?: Record<string, number | null>;
    objectives?: Record<string, number>;
    breaches?: string[];
    windowHours?: number;
  };
  quotaPolicy: Record<string, number | string | boolean | null>;
  alerts: FactorHealthAlert[];
  generatedAt: string | null;
}

interface FactorCandidatesResponse {
  code: number;
  message: string;
  data: {
    items: FactorCandidate[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorCandidateResponse {
  code: number;
  message: string;
  data: {
    candidate: FactorCandidate;
  };
}

interface FactorRunResponse {
  code: number;
  message: string;
  data: {
    run: FactorEvaluationRun;
  };
}

interface FactorRunValuesResponse {
  code: number;
  message: string;
  data: FactorRunValuesResult;
}

interface FactorPromotionResponse {
  code: number;
  message: string;
  data: {
    promotion: FactorFeaturePromotion;
  };
}

interface FactorPromotionsResponse {
  code: number;
  message: string;
  data: {
    items: FactorFeaturePromotion[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorSignalRunResponse {
  code: number;
  message: string;
  data: {
    signalRun: FactorSignalRun;
  };
}

interface FactorSignalRunsResponse {
  code: number;
  message: string;
  data: {
    items: FactorSignalRun[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorCampaignResponse {
  code: number;
  message: string;
  data: {
    campaign: FactorCampaign;
  };
}

interface FactorCampaignsResponse {
  code: number;
  message: string;
  data: {
    items: FactorCampaign[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorCampaignWorkerEventsResponse {
  code: number;
  message: string;
  data: {
    items: FactorCampaignWorkerEvent[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorValueBackfillJobResponse {
  code: number;
  message: string;
  data: {
    job: FactorValueBackfillJob;
  };
}

interface FactorValueBackfillJobsResponse {
  code: number;
  message: string;
  data: {
    items: FactorValueBackfillJob[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorValueBackfillEventsResponse {
  code: number;
  message: string;
  data: {
    items: FactorValueBackfillEvent[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorTrainingRunResponse {
  code: number;
  message: string;
  data: {
    training: FactorTrainingRun;
    approval?: Record<string, any>;
    defaultModel?: Record<string, any>;
  };
}

interface FactorTrainingRunsResponse {
  code: number;
  message: string;
  data: {
    items: FactorTrainingRun[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorApprovalAuditsResponse {
  code: number;
  message: string;
  data: {
    items: FactorApprovalAudit[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorApprovalRequestResponse {
  code: number;
  message: string;
  data: {
    request: FactorApprovalRequest;
    approvalResult?: Record<string, any> | null;
  };
}

interface FactorApprovalRequestsResponse {
  code: number;
  message: string;
  data: {
    items: FactorApprovalRequest[];
    total: number;
    pagination: {
      limit: number;
      offset: number;
      returned: number;
      hasMore: boolean;
    };
  };
}

interface FactorApprovalPolicyResponse {
  code: number;
  message: string;
  data: {
    policy: FactorApprovalPolicy;
  };
}

interface FactorResearchHealthResponse {
  code: number;
  message: string;
  data: {
    health: FactorResearchHealth;
  };
}

interface PermissionCheckResponse {
  code: number;
  message: string;
  data: {
    has_permission: boolean;
    permission_code: string;
  };
}

interface ResearchOverviewResponse {
  code: number;
  message: string;
  data: ResearchOverviewData;
}

interface ResearchModelsResponse {
  code: number;
  message: string;
  data: {
    models: ResearchModelOption[];
  };
}

interface ResearchRunsResponse {
  code: number;
  message: string;
  data: {
    runs: ResearchRunOption[];
  };
}

interface ResearchUniverseResponse {
  code: number;
  message: string;
  data: {
    runId: string;
    summary: ResearchOverviewData['summary'];
    items: ResearchStockRow[];
    pagination?: ResearchOverviewData['pagination'];
  };
}

class ResearchService {
  private client: AxiosInstance;
  private readonly baseURL = (import.meta as any).env?.VITE_USER_API_URL || SERVICE_ENDPOINTS.USER_SERVICE;

  constructor() {
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 120000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use((config) => {
      const token = authService.getAccessToken();
      if (token) {
        if (config.headers && typeof config.headers.set === 'function') {
          config.headers.set('Authorization', `Bearer ${token}`);
        } else if (config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }

      const tenantId = authService.getTenantId?.() || 'default';
      if (config.headers && typeof config.headers.set === 'function') {
        if (!config.headers.has('X-Tenant-Id') && !config.headers.has('x-tenant-id')) {
          config.headers.set('X-Tenant-Id', tenantId);
        }
      } else if (config.headers) {
        if (!config.headers['X-Tenant-Id'] && !config.headers['x-tenant-id']) {
          config.headers['X-Tenant-Id'] = tenantId;
        }
      }
      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      async (error) => authService.handle401Error(error, this.client)
    );
  }

  async getOverview(query: ResearchOverviewQuery): Promise<ResearchOverviewData> {
    const params = new URLSearchParams();

    const append = (key: string, value: string | number | boolean | undefined | null): void => {
      if (value === undefined || value === null || value === '') return;
      params.append(key, String(value));
    };

    append('model_id', query.modelId);
    append('run_id', query.runId);
    append('keyword', query.keyword?.trim());
    append('min_score', query.minScore);
    append('min_consecutive_limit_up_days', query.minConsecutiveLimitUpDays);
    append('min_turnover_rate', query.minTurnoverRate);
    append('max_turnover_rate', query.maxTurnoverRate);
    append('min_amount', query.minAmount);
    append('max_amount', query.maxAmount);
    append('volume_trend_only', query.volumeTrendOnly);
    append('high_confidence_only', query.highConfidenceOnly);
    append('sort_by', query.sortBy);
    append('limit', query.limit);
    append('offset', query.offset);

    (query.sectors || []).forEach((sector) => append('sectors', sector));
    (query.concepts || []).forEach((concept) => append('concepts', concept));
    (query.indices || []).forEach((indexName) => append('indices', indexName));

    const queryString = params.toString();
    const url = queryString ? `/research/overview?${queryString}` : '/research/overview';
    const resp = await this.client.get<ResearchOverviewResponse>(url);
    return resp.data.data;
  }

  // ============ 自选接口 ============

  async addToWatchlist(symbol: string, options?: { runId?: string; stockName?: string; featuresSnapshot?: any }): Promise<void> {
    await this.client.post(`/research/watchlist/${symbol}`, {
      run_id: options?.runId,
      stock_name: options?.stockName,
      features_snapshot: options?.featuresSnapshot
    });
  }

  async removeFromWatchlist(symbol: string): Promise<void> {
    await this.client.delete(`/research/watchlist/${symbol}`);
  }

  async getWatchlist(limit = 50, offset = 0): Promise<{ items: WatchlistItem[]; total: number }> {
    const resp = await this.client.get<WatchlistResponse>(`/research/watchlist?limit=${limit}&offset=${offset}`);
    return resp.data.data;
  }

  // ============ 研究池接口 ============

  async addToResearchPool(symbol: string, options?: {
    runId?: string;
    stockName?: string;
    modelId?: string;
    fusionScore?: number;
    thesisSummary?: string;
    featuresSnapshot?: any;
  }): Promise<void> {
    await this.client.post(`/research/pool/${symbol}`, {
      run_id: options?.runId,
      stock_name: options?.stockName,
      model_id: options?.modelId,
      fusion_score: options?.fusionScore,
      thesis_summary: options?.thesisSummary,
      features_snapshot: options?.featuresSnapshot
    });
  }

  async removeFromResearchPool(symbol: string): Promise<void> {
    await this.client.delete(`/research/pool/${symbol}`);
  }

  async getResearchPool(options?: { status?: string; limit?: number; offset?: number }): Promise<{ items: ResearchPoolItem[]; total: number }> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    if (options?.limit) params.append('limit', String(options.limit));
    if (options?.offset) params.append('offset', String(options.offset));
    const url = params.toString() ? `/research/pool?${params}` : '/research/pool';
    const resp = await this.client.get<ResearchPoolResponse>(url);
    return resp.data.data;
  }

  async getFeaturesBySymbols(symbols: string[], options?: { lite?: boolean }): Promise<ResearchStockRow[]> {
    if (!symbols || symbols.length === 0) return [];
    const lite = options?.lite ? '?lite=true' : '';
    const resp = await this.client.post<{ data: { items: ResearchStockRow[] } }>(`/research/symbols/features${lite}`, { symbols });
    return resp.data?.data?.items || [];
  }

  // ============ K 线数据接口 ============

  async getKlineData(symbol: string, days = 60): Promise<KlineDataItem[]> {
    const resp = await this.client.get<KlineResponse>(`/research/kline/${symbol}?days=${days}`);
    return resp.data.data.items || [];
  }

  // ============ 兼容方法（对接模型中心） ============

  async getAvailableModels(): Promise<ResearchModelOption[]> {
    // 使用轻量接口避免 overview 重查询导致首屏模型加载超时
    try {
      const resp = await this.client.get<ResearchModelsResponse>('/research/models');
      return resp.data?.data?.models || [];
    } catch (error) {
      console.error('[ResearchService] getAvailableModels failed:', error);
      return [];
    }
  }

  async getInferenceRuns(modelId: string): Promise<ResearchRunOption[]> {
    // 使用轻量接口避免 overview 重查询导致批次加载超时
    try {
      const resp = await this.client.get<ResearchRunsResponse>(`/research/runs?model_id=${encodeURIComponent(modelId)}`);
      return resp.data?.data?.runs || [];
    } catch (error) {
      console.error('[ResearchService] getInferenceRuns failed:', error);
      return [];
    }
  }

  async getResearchUniverse(runId: string, limit: number = 2000, offset: number = 0): Promise<{ candidates: any[], summary: any }> {
    const resp = await this.client.get<ResearchUniverseResponse>(
      `/research/universe?run_id=${encodeURIComponent(runId)}&limit=${limit}&offset=${offset}`
    );
    const data = resp.data.data;
    return {
      candidates: data.items || [],
      summary: data.summary || { total: 0, avgScore: 0, highConfidenceCount: 0, strongCount: 0, lastUpdatedAt: null }
    };
  }

  async checkPermission(permissionCode: string): Promise<boolean> {
    try {
      const params = new URLSearchParams({ permission_code: permissionCode });
      const resp = await this.client.get<PermissionCheckResponse>(`/rbac/check-permission?${params.toString()}`);
      return Boolean(resp.data?.data?.has_permission);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return false;
      }
      console.error('[ResearchService] checkPermission failed:', error);
      return false;
    }
  }

  // ============ 因子研究接口 ============

  async listFactorCandidates(options?: { status?: string; limit?: number; offset?: number }): Promise<{
    items: FactorCandidate[];
    total: number;
    pagination: FactorCandidatesResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    params.append('limit', String(options?.limit ?? 50));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorCandidatesResponse>(`/research/factors/candidates?${params.toString()}`);
    return resp.data.data;
  }

  async getFactorResearchHealth(windowHours = 24): Promise<FactorResearchHealth> {
    const params = new URLSearchParams({ window_hours: String(windowHours) });
    const resp = await this.client.get<FactorResearchHealthResponse>(`/research/factors/health?${params.toString()}`);
    return resp.data.data.health;
  }

  async createFactorCandidate(payload: {
    name?: string;
    expression: string;
    description?: string;
    source?: string;
    family?: string;
    tags?: string[];
    metadata?: Record<string, any>;
  }): Promise<FactorCandidate> {
    const resp = await this.client.post<FactorCandidateResponse>('/research/factors/candidates', payload);
    return resp.data.data.candidate;
  }

  async evaluateFactorCandidate(candidateId: string, payload: {
    universe: string;
    start_date: string;
    end_date: string;
    n_groups: number;
    holding_period: number;
    neutralize_industry: boolean;
    neutralize_cap: boolean;
    validation_profile?: string;
    metadata?: Record<string, any>;
  }): Promise<FactorEvaluationRun> {
    const resp = await this.client.post<FactorRunResponse>(
      `/research/factors/candidates/${candidateId}/evaluate`,
      payload
    );
    return resp.data.data.run;
  }

  async getFactorEvaluationRun(runId: string): Promise<FactorEvaluationRun> {
    const resp = await this.client.get<FactorRunResponse>(`/research/factors/runs/${runId}`);
    return resp.data.data.run;
  }

  async listFactorRunValues(runId: string, options?: { limit?: number; offset?: number }): Promise<FactorRunValuesResult> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 100));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorRunValuesResponse>(`/research/factors/runs/${runId}/values?${params.toString()}`);
    return resp.data.data;
  }

  async createFactorValueBackfillJob(payload: {
    run_ids?: string[];
    candidate_ids?: string[];
    promotion_ids?: string[];
    start_date?: string;
    end_date?: string;
    universe?: string;
    holding_period?: number;
    dry_run?: boolean;
    max_runs?: number;
    metadata?: Record<string, any>;
  }): Promise<FactorValueBackfillJob> {
    const resp = await this.client.post<FactorValueBackfillJobResponse>(
      '/research/factors/value-backfills',
      payload
    );
    return resp.data.data.job;
  }

  async listFactorValueBackfillJobs(options?: { status?: string; limit?: number; offset?: number }): Promise<{
    items: FactorValueBackfillJob[];
    total: number;
    pagination: FactorValueBackfillJobsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    params.append('limit', String(options?.limit ?? 10));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorValueBackfillJobsResponse>(`/research/factors/value-backfills?${params.toString()}`);
    return resp.data.data;
  }

  async runFactorValueBackfillJob(jobId: string): Promise<FactorValueBackfillJob> {
    const resp = await this.client.post<FactorValueBackfillJobResponse>(
      `/research/factors/value-backfills/${jobId}/run`,
      {}
    );
    return resp.data.data.job;
  }

  async cancelFactorValueBackfillJob(jobId: string, reason = 'manual_cancel'): Promise<FactorValueBackfillJob> {
    const params = new URLSearchParams();
    params.append('reason', reason);
    const resp = await this.client.post<FactorValueBackfillJobResponse>(
      `/research/factors/value-backfills/${jobId}/cancel?${params.toString()}`,
      {}
    );
    return resp.data.data.job;
  }

  async listFactorValueBackfillEvents(options?: {
    jobId?: string;
    workerId?: string;
    eventType?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    items: FactorValueBackfillEvent[];
    total: number;
    pagination: FactorValueBackfillEventsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    if (options?.jobId) params.append('job_id', options.jobId);
    if (options?.workerId) params.append('worker_id', options.workerId);
    if (options?.eventType) params.append('event_type', options.eventType);
    if (options?.status) params.append('status', options.status);
    params.append('limit', String(options?.limit ?? 10));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorValueBackfillEventsResponse>(`/research/factors/value-backfill-events?${params.toString()}`);
    return resp.data.data;
  }

  async promoteFactorCandidate(candidateId: string, payload?: {
    run_id?: string;
    feature_key?: string;
    feature_name?: string;
    force_shadow?: boolean;
    metadata?: Record<string, any>;
  }): Promise<FactorFeaturePromotion> {
    const resp = await this.client.post<FactorPromotionResponse>(
      `/research/factors/candidates/${candidateId}/promote`,
      payload || {}
    );
    return resp.data.data.promotion;
  }

  async listFactorPromotions(options?: { limit?: number; offset?: number }): Promise<{
    items: FactorFeaturePromotion[];
    total: number;
    pagination: FactorPromotionsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorPromotionsResponse>(`/research/factors/promotions?${params.toString()}`);
    return resp.data.data;
  }

  async materializeFactorPromotion(promotionId: string): Promise<FactorFeaturePromotion> {
    const resp = await this.client.post<FactorPromotionResponse>(
      `/research/factors/promotions/${promotionId}/materialize`,
      {}
    );
    return resp.data.data.promotion;
  }

  async rollbackFactorPromotion(promotionId: string, reason = 'manual_rollback'): Promise<FactorFeaturePromotion> {
    const resp = await this.client.post<FactorPromotionResponse>(
      `/research/factors/promotions/${promotionId}/rollback`,
      { reason }
    );
    return resp.data.data.promotion;
  }

  async publishFactorShadowSignal(candidateId: string, payload?: {
    run_id?: string;
    trade_date?: string;
    top_n?: number;
    bottom_n?: number;
    long_short?: boolean;
    quantity?: number;
    publish_stream?: boolean;
    allow_shadow_stream?: boolean;
    metadata?: Record<string, any>;
  }): Promise<FactorSignalRun> {
    const resp = await this.client.post<FactorSignalRunResponse>(
      `/research/factors/candidates/${candidateId}/publish-shadow-signal`,
      payload || {}
    );
    return resp.data.data.signalRun;
  }

  async listFactorSignalRuns(options?: { limit?: number; offset?: number }): Promise<{
    items: FactorSignalRun[];
    total: number;
    pagination: FactorSignalRunsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorSignalRunsResponse>(`/research/factors/signals?${params.toString()}`);
    return resp.data.data;
  }

  async createFactorCampaign(payload: {
    name?: string;
    strategy?: string;
    seed_expression?: string;
    seed_expressions?: string[];
    n_candidates?: number;
    max_generations?: number;
    run_async?: boolean;
    universe: string;
    start_date: string;
    end_date: string;
    n_groups: number;
    holding_period: number;
    neutralize_industry: boolean;
    neutralize_cap: boolean;
    validation_profile?: string;
    worker_policy?: Record<string, any>;
    retry_policy?: Record<string, any>;
    execution_lease?: Record<string, any>;
    metadata?: Record<string, any>;
  }): Promise<FactorCampaign> {
    const resp = await this.client.post<FactorCampaignResponse>('/research/factors/campaigns', payload);
    return resp.data.data.campaign;
  }

  async listFactorCampaigns(options?: { limit?: number; offset?: number }): Promise<{
    items: FactorCampaign[];
    total: number;
    pagination: FactorCampaignsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorCampaignsResponse>(`/research/factors/campaigns?${params.toString()}`);
    return resp.data.data;
  }

  async getFactorCampaign(campaignId: string): Promise<FactorCampaign> {
    const resp = await this.client.get<FactorCampaignResponse>(`/research/factors/campaigns/${campaignId}`);
    return resp.data.data.campaign;
  }

  async listFactorCampaignWorkerEvents(options?: {
    campaignId?: string;
    workerId?: string;
    eventType?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    items: FactorCampaignWorkerEvent[];
    total: number;
    pagination: FactorCampaignWorkerEventsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 10));
    params.append('offset', String(options?.offset ?? 0));
    if (options?.campaignId) params.append('campaign_id', options.campaignId);
    if (options?.workerId) params.append('worker_id', options.workerId);
    if (options?.eventType) params.append('event_type', options.eventType);
    if (options?.status) params.append('status', options.status);
    const resp = await this.client.get<FactorCampaignWorkerEventsResponse>(
      `/research/factors/campaign-worker-events?${params.toString()}`
    );
    return resp.data.data;
  }

  async cancelFactorCampaign(campaignId: string, reason = 'manual_cancel'): Promise<FactorCampaign> {
    const params = new URLSearchParams({ reason });
    const resp = await this.client.post<FactorCampaignResponse>(
      `/research/factors/campaigns/${campaignId}/cancel?${params.toString()}`,
      {}
    );
    return resp.data.data.campaign;
  }

  async launchFactorPromotionTraining(promotionId: string, payload?: {
    display_name?: string;
    baseline_display_name?: string;
    auto_baseline?: boolean;
    train_start?: string;
    train_end?: string;
    valid_start?: string;
    valid_end?: string;
    test_start?: string;
    test_end?: string;
    target_horizon_days?: number;
    target_mode?: string;
    label_formula?: string;
    num_boost_round?: number;
    early_stopping_rounds?: number;
    context?: Record<string, any>;
    lgb_params?: Record<string, any>;
    baseline_training_run_id?: string;
    baseline_metrics?: Record<string, any>;
    metadata?: Record<string, any>;
  }): Promise<FactorTrainingRun> {
    const resp = await this.client.post<FactorTrainingRunResponse>(
      `/research/factors/promotions/${promotionId}/train`,
      payload || {}
    );
    return resp.data.data.training;
  }

  async listFactorTrainingRuns(options?: { limit?: number; offset?: number }): Promise<{
    items: FactorTrainingRun[];
    total: number;
    pagination: FactorTrainingRunsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorTrainingRunsResponse>(`/research/factors/trainings?${params.toString()}`);
    return resp.data.data;
  }

  async listFactorApprovalAudits(options?: {
    trainingId?: string;
    modelId?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    items: FactorApprovalAudit[];
    total: number;
    pagination: FactorApprovalAuditsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    if (options?.trainingId) params.append('training_id', options.trainingId);
    if (options?.modelId) params.append('model_id', options.modelId);
    if (options?.status) params.append('status', options.status);
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorApprovalAuditsResponse>(`/research/factors/approvals?${params.toString()}`);
    return resp.data.data;
  }

  async getFactorApprovalPolicy(): Promise<FactorApprovalPolicy> {
    const resp = await this.client.get<FactorApprovalPolicyResponse>('/research/factors/approval-policy');
    return resp.data.data.policy;
  }

  async updateFactorApprovalPolicy(payload: {
    allow_direct_approval?: boolean;
    allow_self_approval?: boolean;
    min_approvals?: number;
    reviewer_permission?: string;
    metadata?: Record<string, any>;
  }): Promise<FactorApprovalPolicy> {
    const resp = await this.client.put<FactorApprovalPolicyResponse>(
      '/research/factors/approval-policy',
      payload
    );
    return resp.data.data.policy;
  }

  async requestFactorTrainingApproval(trainingId: string, payload?: {
    reason?: string;
    metadata?: Record<string, any>;
  }): Promise<FactorApprovalRequest> {
    const resp = await this.client.post<FactorApprovalRequestResponse>(
      `/research/factors/trainings/${trainingId}/approval-requests`,
      payload || {}
    );
    return resp.data.data.request;
  }

  async listFactorApprovalRequests(options?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{
    items: FactorApprovalRequest[];
    total: number;
    pagination: FactorApprovalRequestsResponse['data']['pagination'];
  }> {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    params.append('limit', String(options?.limit ?? 20));
    params.append('offset', String(options?.offset ?? 0));
    const resp = await this.client.get<FactorApprovalRequestsResponse>(`/research/factors/approval-requests?${params.toString()}`);
    return resp.data.data;
  }

  async reviewFactorApprovalRequest(requestId: string, payload?: {
    approve?: boolean;
    decision?: string;
    reason?: string;
    reviewer_note?: string;
    metadata?: Record<string, any>;
  }): Promise<FactorApprovalRequestResponse['data']> {
    const resp = await this.client.post<FactorApprovalRequestResponse>(
      `/research/factors/approval-requests/${requestId}/review`,
      payload || {}
    );
    return resp.data.data;
  }

  async approveFactorTraining(trainingId: string, payload?: {
    set_default_model?: boolean;
    approve_default_model?: boolean;
    reason?: string;
    metadata?: Record<string, any>;
  }): Promise<FactorTrainingRun> {
    const resp = await this.client.post<FactorTrainingRunResponse>(
      `/research/factors/trainings/${trainingId}/approve`,
      payload || {}
    );
    return resp.data.data.training;
  }
}

export interface KlineDataItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KlineResponse {
  code: number;
  message: string;
  data: {
    symbol: string;
    items: KlineDataItem[];
    count: number;
  };
}

export interface WatchlistItem {
  symbol: string;
  stockName: string | null;
  addedAt: string | null;
  sourceRunId: string | null;
  notes: string | null;
  tags: string[];
}

export interface ResearchPoolItem {
  symbol: string;
  stockName: string | null;
  addedAt: string | null;
  sourceRunId: string | null;
  modelId: string | null;
  fusionScore: number | null;
  thesisSummary: string | null;
  status: string;
  notes: string | null;
  tags: string[];
}

interface WatchlistResponse {
  code: number;
  message: string;
  data: { items: WatchlistItem[]; total: number };
}

interface ResearchPoolResponse {
  code: number;
  message: string;
  data: { items: ResearchPoolItem[]; total: number };
}

export const researchService = new ResearchService();
