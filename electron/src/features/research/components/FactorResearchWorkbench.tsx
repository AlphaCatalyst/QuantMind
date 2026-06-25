import React from 'react';
import { Button, DatePicker, Input, InputNumber, Modal, Select, Segmented, Switch, Table, Tag, Tooltip, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Beaker,
  CheckCircle2,
  Database,
  FlaskConical,
  GitBranch,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Radio,
  Sparkles,
  XCircle,
} from 'lucide-react';
import {
  researchService,
  type FactorApprovalAudit,
  type FactorApprovalPolicy,
  type FactorApprovalRequest,
  type FactorCampaign,
  type FactorCampaignWorkerEvent,
  type FactorCandidate,
  type FactorFeaturePromotion,
  type FactorRunValuesResult,
  type FactorResearchHealth,
  type FactorSignalRun,
  type FactorTrainingRun,
  type FactorValueBackfillEvent,
  type FactorValueBackfillJob,
} from '../../../services/researchService';
import { authService } from '../../auth/services/authService';

const { Text } = Typography;
const { RangePicker } = DatePicker;

type LabMode = 'campaign' | 'evaluate' | 'promote' | 'signal';
type CampaignStrategy =
  | 'mutation_crossover'
  | 'template_mutation'
  | 'quantgpt_meta_evolution'
  | 'quantgpt_crossover_only';
const FACTOR_APPROVAL_PERMISSION = 'factor.approve';

interface FactorTemplate {
  key: string;
  label: string;
  expression: string;
  family: string;
}

interface GateRow {
  key: string;
  metric: string;
  threshold: string;
  current: string;
  status: 'passed' | 'pending' | 'blocked';
}

const FACTOR_TEMPLATES: FactorTemplate[] = [
  {
    key: 'price_mean_reversion',
    label: '价格均值偏离',
    expression: 'rank(close / ts_mean(close, 20))',
    family: 'momentum',
  },
  {
    key: 'short_momentum',
    label: '短周期动量',
    expression: 'rank(ts_delta(close, 5) / ts_shift(close, 5))',
    family: 'momentum',
  },
  {
    key: 'price_volume_corr',
    label: '价量相关',
    expression: 'rank(ts_corr(rank(close), rank(volume), 10))',
    family: 'volume',
  },
];

const GATE_ROWS: GateRow[] = [
  { key: 'rank_ic', metric: 'Rank IC', threshold: '|mean| >= 0.015', current: '待评估', status: 'pending' },
  { key: 'ic_ir', metric: 'IC IR', threshold: '>= 0.15', current: '待评估', status: 'pending' },
  { key: 'turnover', metric: 'Turnover', threshold: '<= 0.35', current: '待评估', status: 'pending' },
  { key: 'monotonicity', metric: 'Monotonicity', threshold: '>= 0.60', current: '待评估', status: 'pending' },
  { key: 'anti_overfit', metric: 'Anti-overfit', threshold: '>= 60', current: '待评估', status: 'pending' },
  { key: 'coverage', metric: 'Coverage days', threshold: '>= 120', current: '待评估', status: 'pending' },
];

const formatMetric = (value: unknown, digits = 4): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '未计算';
  return value.toFixed(digits);
};

const statusTag = (status: GateRow['status']) => {
  if (status === 'passed') return <Tag color="success" className="m-0 rounded-full font-bold">通过</Tag>;
  if (status === 'blocked') return <Tag color="error" className="m-0 rounded-full font-bold">阻断</Tag>;
  return <Tag color="processing" className="m-0 rounded-full font-bold">待跑数</Tag>;
};

const candidateStatusTag = (status: FactorCandidate['status']) => {
  const config: Record<FactorCandidate['status'], { color: string; label: string }> = {
    draft: { color: 'default', label: '草稿' },
    evaluating: { color: 'processing', label: '评估中' },
    validated: { color: 'success', label: '已验证' },
    rejected: { color: 'error', label: '已阻断' },
    promoted: { color: 'success', label: '已晋升' },
    archived: { color: 'default', label: '已归档' },
  };
  const item = config[status] || { color: 'default', label: status };
  return <Tag color={item.color} className="m-0 rounded-full font-bold">{item.label}</Tag>;
};

const runStatusTag = (status?: string) => {
  if (!status) return <span className="text-xs font-bold text-slate-400">未创建</span>;
  const config: Record<string, { color: string; label: string }> = {
    pending: { color: 'warning', label: '待执行' },
    running: { color: 'processing', label: '运行中' },
    completed: { color: 'success', label: '已完成' },
    failed: { color: 'error', label: '失败' },
  };
  const item = config[status] || { color: 'default', label: status };
  return <Tag color={item.color} className="m-0 rounded-full font-bold">{item.label}</Tag>;
};

const healthStatusTag = (status?: string) => {
  const config: Record<string, { color: string; label: string }> = {
    healthy: { color: 'success', label: '健康' },
    warning: { color: 'warning', label: '需关注' },
    critical: { color: 'error', label: '异常' },
  };
  const item = config[status || ''] || { color: 'default', label: status || '未加载' };
  return <Tag color={item.color} className="m-0 rounded-full font-bold">{item.label}</Tag>;
};

const percentText = (value?: number | null): string => {
  if (typeof value !== 'number') return '-';
  return `${(value * 100).toFixed(1)}%`;
};

const promotionStatusTag = (status?: string) => {
  if (status === 'materialized') return <Tag color="success" className="m-0 rounded-full font-bold">可训练</Tag>;
  if (status === 'pending_materialization') return <Tag color="warning" className="m-0 rounded-full font-bold">待物化</Tag>;
  if (status === 'rolled_back') return <Tag color="default" className="m-0 rounded-full font-bold">已回滚</Tag>;
  if (status === 'unknown') return <Tag color="default" className="m-0 rounded-full font-bold">未知</Tag>;
  return <Tag className="m-0 rounded-full font-bold">{status || '未晋升'}</Tag>;
};

const trainingMetricSummary = (run?: FactorTrainingRun): string => {
  if (!run) return '-';
  const result = run.trainingResult || run.response?.trainingJob?.result || {};
  const summary = result.summary || {};
  const metrics = result.metrics || {};
  const test = metrics.test || {};
  if (typeof test.auc === 'number' || typeof test.rmse === 'number') {
    const auc = typeof test.auc === 'number' ? `AUC ${test.auc.toFixed(4)}` : 'AUC -';
    const rmse = typeof test.rmse === 'number' ? `RMSE ${test.rmse.toFixed(4)}` : 'RMSE -';
    return `${auc} / ${rmse}`;
  }
  return String(summary.message || summary.status || '-');
};

const trainingComparisonSummary = (run?: FactorTrainingRun): string => {
  if (!run) return '-';
  const comparison = run.trainingComparison || run.trainingResult?.comparison || run.response?.comparison || {};
  if (comparison.status === 'baseline_missing') return '待补 baseline';
  if (comparison.status === 'promoted_metrics_missing') return '待补 promoted metrics';
  if (comparison.summary) return String(comparison.summary);
  return '-';
};

const trainingComparisonTag = (run?: FactorTrainingRun) => {
  const comparison = run?.trainingComparison || run?.trainingResult?.comparison || run?.response?.comparison || {};
  const status = String(comparison.status || '');
  if (status === 'improved') return <Tag color="success" className="m-0 rounded-full font-bold">优于 Baseline</Tag>;
  if (status === 'regressed') return <Tag color="error" className="m-0 rounded-full font-bold">弱于 Baseline</Tag>;
  if (status === 'mixed') return <Tag color="warning" className="m-0 rounded-full font-bold">表现混合</Tag>;
  if (status === 'baseline_missing') return <Tag className="m-0 rounded-full font-bold">待补 Baseline</Tag>;
  return <Tag className="m-0 rounded-full font-bold">待对比</Tag>;
};

const trainingGate = (run?: FactorTrainingRun): Record<string, any> => {
  const comparison = run?.trainingComparison || run?.trainingResult?.comparison || run?.response?.comparison || {};
  return run?.trainingGate || comparison.gate || run?.response?.trainingGate || {};
};

const trainingGateSummary = (run?: FactorTrainingRun): string => {
  if (!run) return '-';
  const gate = trainingGate(run);
  return String(gate.summary || gate.decision || '-');
};

const trainingGateTag = (run?: FactorTrainingRun) => {
  const gate = trainingGate(run);
  const decision = String(gate.decision || '');
  if (decision === 'approve_model_candidate') return <Tag color="success" className="m-0 rounded-full font-bold">待审批晋升</Tag>;
  if (decision === 'rollback_recommended') return <Tag color="error" className="m-0 rounded-full font-bold">建议回滚</Tag>;
  if (decision === 'observe') return <Tag color="warning" className="m-0 rounded-full font-bold">继续观察</Tag>;
  if (decision === 'blocked') return <Tag className="m-0 rounded-full font-bold">证据不足</Tag>;
  return <Tag className="m-0 rounded-full font-bold">待门禁</Tag>;
};

const isActiveAsyncStatus = (status?: string | null): boolean => {
  return ['pending', 'provisioning', 'running', 'waiting_callback'].includes(String(status || ''));
};

const reasonLabel = (reason: string): string => {
  const labels: Record<string, string> = {
    data_table_missing: '本地行情表缺失',
    unsupported_expression: '表达式暂不支持',
    no_factor_values_generated: '未生成因子值',
    missing_rank_ic_mean: '缺少 Rank IC',
    rank_ic_mean_below_threshold: 'Rank IC 未达标',
    missing_ic_ir: '缺少 IC IR',
    missing_turnover: '缺少换手',
    missing_monotonicity_score: '缺少单调性',
    missing_anti_overfit_score: '缺少反过拟合评分',
    coverage_days_below_threshold: '覆盖天数不足',
  };
  return labels[reason] || reason;
};

const healthAlertLabel = (code: string): string => {
  const labels: Record<string, string> = {
    stale_factor_runs: '存在长时间未完成 run',
    shadow_signal_stream_published: 'Shadow Signal 已写入实时流',
    recent_failed_factor_runs: '近期存在失败 run',
    factor_campaign_worker_failures: 'Campaign Worker 近期失败',
    stale_factor_campaigns: '存在长时间运行 Campaign',
    campaign_active_quota_used: 'Campaign 并发配额已满',
    campaign_daily_candidate_quota_near_limit: 'Campaign 日预算接近上限',
    campaign_daily_candidate_quota_used: 'Campaign 日预算已用尽',
    pending_feature_materializations: '存在待物化特征',
  };
  return labels[code] || code;
};

const workerEventLabel = (eventType?: string): string => {
  const labels: Record<string, string> = {
    recovered: '已恢复',
    processed: '已处理',
    idle: '空转',
    failed: '失败',
    heartbeat: '心跳',
    started: '启动',
    stopped: '停止',
  };
  return labels[eventType || ''] || eventType || '未知';
};

const workerEventSummary = (event: FactorCampaignWorkerEvent): string => {
  const details = event.details || {};
  if (event.eventType === 'processed') {
    return `worker ${event.workerId || '-'} / attempt ${event.attemptNo ?? '-'} / ${event.durationMs ?? 0}ms / runs ${details.completedRuns ?? 0}`;
  }
  if (event.eventType === 'recovered') {
    return `worker ${event.workerId || '-'} / 恢复 ${details.count ?? 0} 个`;
  }
  if (event.eventType === 'heartbeat') {
    return `worker ${event.workerId || '-'} / processed ${details.processed ?? 0}`;
  }
  if (event.eventType === 'started') {
    return `worker ${event.workerId || '-'} / concurrency ${details.concurrency ?? '-'}`;
  }
  if (event.eventType === 'stopped') {
    return `worker ${event.workerId || '-'} / ${details.reason || '-'} / processed ${details.processed ?? 0}`;
  }
  if (event.eventType === 'failed') {
    return `worker ${event.workerId || '-'} / ${String(details.error || 'worker 执行失败')}`;
  }
  if (event.eventType === 'idle') {
    return `worker ${event.workerId || '-'} / processed ${details.processed ?? 0}`;
  }
  return event.campaignId ? `campaign ${event.campaignId.slice(0, 8)}` : '-';
};

const runReasonText = (candidate?: FactorCandidate): string => {
  const run = candidate?.latestRun;
  if (!run) return '暂无评估 run';
  const reasons = run.gateDecision?.reasons || [];
  if (run.errorMessage) return run.errorMessage;
  if (reasons.length > 0) return reasons.map(reasonLabel).join(' / ');
  return run.gateDecision?.eligible ? '满足晋升门禁' : '等待门禁判断';
};

const buildGateRows = (candidate?: FactorCandidate): GateRow[] => {
  const run = candidate?.latestRun;
  const metrics = run?.metrics || {};
  const reasons = run?.gateDecision?.reasons || [];
  const terminal = run?.status === 'completed' || run?.status === 'failed';
  const missingBlocked = (reason: string): GateRow['status'] => terminal && reasons.includes(reason) ? 'blocked' : 'pending';
  const rankIc = typeof metrics.rank_ic_mean === 'number' ? metrics.rank_ic_mean : undefined;
  const coverage = typeof metrics.coverage_days === 'number' ? metrics.coverage_days : undefined;

  if (run?.status === 'failed') {
    return GATE_ROWS.map((row) => ({
      ...row,
      current: row.key === 'rank_ic' ? run.errorMessage || '评估失败' : '未生成',
      status: 'blocked',
    }));
  }

  return [
    {
      key: 'rank_ic',
      metric: 'Rank IC',
      threshold: '|mean| >= 0.015',
      current: formatMetric(rankIc),
      status: rankIc === undefined ? missingBlocked('missing_rank_ic_mean') : Math.abs(rankIc) >= 0.015 ? 'passed' : 'blocked',
    },
    {
      key: 'ic_ir',
      metric: 'IC IR',
      threshold: '>= 0.15',
      current: formatMetric(metrics.ic_ir),
      status: typeof metrics.ic_ir === 'number' ? metrics.ic_ir >= 0.15 ? 'passed' : 'blocked' : missingBlocked('missing_ic_ir'),
    },
    {
      key: 'turnover',
      metric: 'Turnover',
      threshold: '<= 0.35',
      current: formatMetric(metrics.turnover),
      status: typeof metrics.turnover === 'number' ? metrics.turnover <= 0.35 ? 'passed' : 'blocked' : missingBlocked('missing_turnover'),
    },
    {
      key: 'monotonicity',
      metric: 'Monotonicity',
      threshold: '>= 0.60',
      current: formatMetric(metrics.monotonicity_score, 2),
      status: typeof metrics.monotonicity_score === 'number'
        ? metrics.monotonicity_score >= 0.6 ? 'passed' : 'blocked'
        : missingBlocked('missing_monotonicity_score'),
    },
    {
      key: 'anti_overfit',
      metric: 'Anti-overfit',
      threshold: '>= 60',
      current: formatMetric(metrics.anti_overfit_score, 1),
      status: typeof metrics.anti_overfit_score === 'number'
        ? metrics.anti_overfit_score >= 60 ? 'passed' : 'blocked'
        : missingBlocked('missing_anti_overfit_score'),
    },
    {
      key: 'coverage',
      metric: 'Coverage days',
      threshold: '>= 120',
      current: coverage === undefined ? '未计算' : String(coverage),
      status: coverage === undefined ? missingBlocked('missing_coverage_days') : coverage >= 120 ? 'passed' : 'blocked',
    },
  ];
};

const PIPELINE_STEPS = [
  {
    icon: Beaker,
    title: '因子构思',
    value: 'Seed',
    description: '手动表达式、模板、自动挖掘 campaign',
    output: '候选表达式',
    tone: 'blue',
  },
  {
    icon: Database,
    title: '数据准备',
    value: 'Data',
    description: '股票池、窗口、OHLCV、特征快照',
    output: '标准输入集',
    tone: 'emerald',
  },
  {
    icon: FlaskConical,
    title: '计算评估',
    value: 'Eval',
    description: '因子值、分组收益、IC、换手',
    output: '评估 run',
    tone: 'violet',
  },
  {
    icon: ShieldCheck,
    title: '研究门禁',
    value: 'Gate',
    description: '反过拟合、滚动验证、覆盖率、成本',
    output: '通过/阻断',
    tone: 'amber',
  },
  {
    icon: GitBranch,
    title: '入库版本',
    value: 'Catalog',
    description: '候选、run、factor values 可追溯',
    output: 'Factor Catalog',
    tone: 'blue',
  },
  {
    icon: Sparkles,
    title: '晋升训练',
    value: 'Train',
    description: '生成 shadow feature set，再交给模型训练',
    output: '训练特征',
    tone: 'emerald',
  },
  {
    icon: Activity,
    title: '信号灰度',
    value: 'Signal',
    description: '转为 shadow signal，供回测和模拟盘验证',
    output: '信号流',
    tone: 'violet',
  },
  {
    icon: CheckCircle2,
    title: '监控回滚',
    value: 'Ops',
    description: '表现监控、版本回退、审计记录',
    output: '生产门禁',
    tone: 'amber',
  },
];

export const FactorResearchWorkbench: React.FC = () => {
  const navigate = useNavigate();
  const currentUser = authService.getStoredUser() as any;
  const currentUserIsAdmin = Boolean(currentUser?.is_admin);
  const [mode, setMode] = React.useState<LabMode>('campaign');
  const [expression, setExpression] = React.useState(FACTOR_TEMPLATES[0].expression);
  const [universe, setUniverse] = React.useState('hs300');
  const [dateRange, setDateRange] = React.useState<[Dayjs, Dayjs]>([
    dayjs().subtract(180, 'day'),
    dayjs(),
  ]);
  const [groups, setGroups] = React.useState(5);
  const [holdingPeriod, setHoldingPeriod] = React.useState(5);
  const [campaignGenerations, setCampaignGenerations] = React.useState(1);
  const [campaignStrategy, setCampaignStrategy] = React.useState<CampaignStrategy>('mutation_crossover');
  const [requestContractOpen, setRequestContractOpen] = React.useState(false);
  const [candidates, setCandidates] = React.useState<FactorCandidate[]>([]);
  const [candidateTotal, setCandidateTotal] = React.useState(0);
  const [campaigns, setCampaigns] = React.useState<FactorCampaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = React.useState<string | null>(null);
  const [promotions, setPromotions] = React.useState<FactorFeaturePromotion[]>([]);
  const [signalRuns, setSignalRuns] = React.useState<FactorSignalRun[]>([]);
  const [trainingRuns, setTrainingRuns] = React.useState<FactorTrainingRun[]>([]);
  const [backfillJobs, setBackfillJobs] = React.useState<FactorValueBackfillJob[]>([]);
  const [backfillEvents, setBackfillEvents] = React.useState<FactorValueBackfillEvent[]>([]);
  const [approvalAudits, setApprovalAudits] = React.useState<FactorApprovalAudit[]>([]);
  const [approvalRequests, setApprovalRequests] = React.useState<FactorApprovalRequest[]>([]);
  const [approvalPolicy, setApprovalPolicy] = React.useState<FactorApprovalPolicy | null>(null);
  const [factorHealth, setFactorHealth] = React.useState<FactorResearchHealth | null>(null);
  const [workerEvents, setWorkerEvents] = React.useState<FactorCampaignWorkerEvent[]>([]);
  const [factorRunValues, setFactorRunValues] = React.useState<FactorRunValuesResult | null>(null);
  const [loadingCandidates, setLoadingCandidates] = React.useState(false);
  const [loadingApprovalPolicy, setLoadingApprovalPolicy] = React.useState(false);
  const [savingApprovalPolicy, setSavingApprovalPolicy] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [miningCampaign, setMiningCampaign] = React.useState(false);
  const [cancellingCampaign, setCancellingCampaign] = React.useState(false);
  const [promoting, setPromoting] = React.useState(false);
  const [materializing, setMaterializing] = React.useState(false);
  const [rollingBackPromotion, setRollingBackPromotion] = React.useState(false);
  const [launchingTraining, setLaunchingTraining] = React.useState(false);
  const [approvingTraining, setApprovingTraining] = React.useState(false);
  const [requestingApproval, setRequestingApproval] = React.useState(false);
  const [reviewingApprovalRequest, setReviewingApprovalRequest] = React.useState<'approve' | 'reject' | null>(null);
  const [runningBackfill, setRunningBackfill] = React.useState(false);
  const [cancellingBackfill, setCancellingBackfill] = React.useState(false);
  const [publishingSignal, setPublishingSignal] = React.useState(false);
  const [canReviewApprovals, setCanReviewApprovals] = React.useState(currentUserIsAdmin);
  const latestCandidate = candidates[0];
  const latestRun = latestCandidate?.latestRun;
  const latestCampaign = campaigns[0];
  const selectedCampaign = React.useMemo(
    () => campaigns.find((campaign) => campaign.id === selectedCampaignId) || latestCampaign,
    [campaigns, latestCampaign, selectedCampaignId],
  );
  const latestPromotion = promotions[0];
  const latestSignalRun = signalRuns[0];
  const latestTrainingRun = trainingRuns[0];
  const latestBackfillJob = backfillJobs[0];
  const latestApprovalAudit = approvalAudits[0];
  const latestApprovalRequest = approvalRequests[0];
  const latestCampaignBestCandidateId = selectedCampaign?.summary?.bestCandidateId as string | undefined;
  const latestCampaignBestRunId = selectedCampaign?.summary?.bestRunId as string | undefined;
  const latestCampaignBestExpression = selectedCampaign?.summary?.bestExpression as string | undefined;
  const shouldAutoRefresh = isActiveAsyncStatus(latestRun?.status)
    || campaigns.some((campaign) => isActiveAsyncStatus(campaign.status))
    || isActiveAsyncStatus(latestTrainingRun?.trainingStatus || latestTrainingRun?.status)
    || backfillJobs.some((job) => isActiveAsyncStatus(job.status));
  const latestTrainingGate = trainingGate(latestTrainingRun);
  const latestCampaignIsActive = isActiveAsyncStatus(selectedCampaign?.status);
  const canApproveLatestTraining = Boolean(
    latestTrainingRun?.id
      && (latestTrainingRun.trainingStatus || latestTrainingRun.status) === 'completed'
      && latestTrainingGate.decision === 'approve_model_candidate'
      && latestTrainingGate.allowDefaultModelPromotion === true
      && !latestTrainingRun.metadata?.approval?.default_model_set,
  );
  const directApprovalDisabledByPolicy = approvalPolicy?.allowDirectApproval === false;
  const dynamicGateRows = React.useMemo(() => buildGateRows(latestCandidate), [latestCandidate]);

  const selectedTemplate = React.useMemo(
    () => FACTOR_TEMPLATES.find((item) => item.expression === expression),
    [expression],
  );

  const requestPreview = React.useMemo(() => ({
    expression,
    universe,
    start_date: dateRange[0]?.format('YYYY-MM-DD'),
    end_date: dateRange[1]?.format('YYYY-MM-DD'),
    n_groups: groups,
    holding_period: holdingPeriod,
    ...(mode === 'campaign' ? {
      strategy: campaignStrategy,
      max_generations: campaignGenerations,
      worker_policy: { concurrency: 1, max_claims: 1, heartbeat_interval_seconds: 30 },
      retry_policy: { max_attempts: 1, retry_failed_after_minutes: 30 },
      execution_lease: { lease_seconds: 1800 },
    } : {}),
    neutralize_industry: true,
    neutralize_cap: true,
  }), [campaignGenerations, campaignStrategy, dateRange, expression, groups, holdingPeriod, mode, universe]);

  const gateColumns = React.useMemo<ColumnsType<GateRow>>(() => [
    {
      title: '门禁',
      dataIndex: 'metric',
      render: (value: string) => <span className="font-black text-slate-800">{value}</span>,
    },
    {
      title: '阈值',
      dataIndex: 'threshold',
      render: (value: string) => <span className="font-mono text-[11px] text-slate-500">{value}</span>,
    },
    {
      title: '当前值',
      dataIndex: 'current',
      render: (value: string) => <span className="text-slate-500">{value}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      align: 'center',
      width: 92,
      render: (status: GateRow['status']) => statusTag(status),
    },
  ], []);

  const loadCandidates = React.useCallback(async () => {
    setLoadingCandidates(true);
    try {
      const result = await researchService.listFactorCandidates({ limit: 20, offset: 0 });
      const nextCandidates = result.items || [];
      setCandidates(nextCandidates);
      setCandidateTotal(result.total || 0);
      const nextLatestRun = nextCandidates[0]?.latestRun;
      if (nextLatestRun?.status === 'completed') {
        try {
          const valuesResult = await researchService.listFactorRunValues(nextLatestRun.id, { limit: 5, offset: 0 });
          if (valuesResult?.summary && Array.isArray(valuesResult.items)) {
            setFactorRunValues(valuesResult);
          } else {
            setFactorRunValues(null);
          }
        } catch (valuesError) {
          console.warn('factor run values preview failed', valuesError);
          setFactorRunValues(null);
        }
      } else {
        setFactorRunValues(null);
      }
      const campaignResult = await researchService.listFactorCampaigns({ limit: 10, offset: 0 });
      const nextCampaigns = campaignResult.items || [];
      const latestCampaignId = nextCampaigns[0]?.id;
      if (latestCampaignId) {
        try {
          const campaignDetail = await researchService.getFactorCampaign(latestCampaignId);
          if (campaignDetail?.id === latestCampaignId && Array.isArray(campaignDetail.items)) {
            setCampaigns([campaignDetail, ...nextCampaigns.slice(1)]);
          } else {
            setCampaigns(nextCampaigns);
          }
        } catch (campaignError) {
          console.warn('factor campaign detail failed', campaignError);
          setCampaigns(nextCampaigns);
        }
      } else {
        setCampaigns(nextCampaigns);
      }
      const promotionResult = await researchService.listFactorPromotions({ limit: 20, offset: 0 });
      setPromotions(promotionResult.items || []);
      const signalResult = await researchService.listFactorSignalRuns({ limit: 20, offset: 0 });
      setSignalRuns(signalResult.items || []);
      const trainingResult = await researchService.listFactorTrainingRuns({ limit: 20, offset: 0 });
      setTrainingRuns(trainingResult.items || []);
      const backfillResult = await researchService.listFactorValueBackfillJobs({ limit: 5, offset: 0 });
      setBackfillJobs(backfillResult.items || []);
      const backfillEventResult = await researchService.listFactorValueBackfillEvents({ limit: 5, offset: 0 });
      setBackfillEvents(backfillEventResult.items || []);
      const approvalAuditResult = await researchService.listFactorApprovalAudits({ limit: 5, offset: 0 });
      setApprovalAudits(approvalAuditResult.items || []);
      const approvalRequestResult = await researchService.listFactorApprovalRequests({ limit: 5, offset: 0 });
      setApprovalRequests(approvalRequestResult.items || []);
      const health = await researchService.getFactorResearchHealth(24);
      setFactorHealth(health || null);
      const workerEventResult = await researchService.listFactorCampaignWorkerEvents({ limit: 5, offset: 0 });
      setWorkerEvents(workerEventResult.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '候选因子加载失败');
    } finally {
      setLoadingCandidates(false);
    }
  }, []);

  const loadApprovalPolicy = React.useCallback(async () => {
    setLoadingApprovalPolicy(true);
    try {
      const policy = await researchService.getFactorApprovalPolicy();
      setApprovalPolicy(policy);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '审批策略加载失败');
    } finally {
      setLoadingApprovalPolicy(false);
    }
  }, []);

  React.useEffect(() => {
    void loadCandidates();
  }, [loadCandidates]);

  React.useEffect(() => {
    void loadApprovalPolicy();
  }, [loadApprovalPolicy]);

  React.useEffect(() => {
    let active = true;
    if (currentUserIsAdmin) {
      setCanReviewApprovals(true);
      return undefined;
    }

    void researchService.checkPermission(FACTOR_APPROVAL_PERMISSION)
      .then((allowed) => {
        if (active) setCanReviewApprovals(allowed);
      })
      .catch(() => {
        if (active) setCanReviewApprovals(false);
      });

    return () => {
      active = false;
    };
  }, [currentUserIsAdmin]);

  React.useEffect(() => {
    if (!shouldAutoRefresh) return undefined;
    const timer = window.setInterval(() => {
      void loadCandidates();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [loadCandidates, shouldAutoRefresh]);

  const handleSubmitEvaluation = async () => {
    const trimmed = expression.trim();
    if (!trimmed) {
      message.warning('请输入因子表达式');
      return;
    }
    if (!dateRange[0] || !dateRange[1]) {
      message.warning('请选择评估时间窗口');
      return;
    }

    setSubmitting(true);
    try {
      const candidate = await researchService.createFactorCandidate({
        name: selectedTemplate?.label || trimmed.slice(0, 32),
        expression: trimmed,
        source: selectedTemplate ? 'template' : 'manual',
        family: selectedTemplate?.family,
        tags: selectedTemplate ? [selectedTemplate.family] : [],
        metadata: {
          pipeline_stage: 'pre_training_factor_research',
          submitted_from: 'factor_research_workbench',
        },
      });
      const run = await researchService.evaluateFactorCandidate(candidate.id, {
        universe,
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        n_groups: groups,
        holding_period: holdingPeriod,
        neutralize_industry: true,
        neutralize_cap: true,
        validation_profile: 'default',
      });
      if (run.status === 'failed') {
        message.warning(`候选因子已入库，但评估失败：${run.errorMessage || runReasonText({ ...candidate, latestRun: run })}`);
      } else if (run.status === 'completed') {
        message.success('候选因子已完成本地评估，结果已写入因子研究产物库');
      } else {
        message.success('候选因子已入库，评估任务已创建');
      }
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '提交评估失败');
    } finally {
      setSubmitting(false);
    }
  };

  const promoteFactorCandidate = async (
    candidateId: string,
    runId: string,
    featureName: string,
    metadata: Record<string, any>,
  ) => {
    setPromoting(true);
    try {
      const promotion = await researchService.promoteFactorCandidate(candidateId, {
        run_id: runId,
        feature_name: featureName,
        force_shadow: true,
        metadata,
      });
      if (promotion.materializationStatus === 'materialized') {
        message.success(`已登记可训练特征：${promotion.featureKey}`);
      } else {
        message.warning(`已登记 Shadow 特征，但训练快照尚未物化列：${promotion.featureKey}`);
      }
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Feature 晋升失败');
    } finally {
      setPromoting(false);
    }
  };

  const handlePromoteLatest = async () => {
    if (!latestCandidate?.id || latestRun?.status !== 'completed') {
      message.warning('只有已完成评估且生成因子值的候选才能登记为 Shadow 特征');
      return;
    }
    await promoteFactorCandidate(latestCandidate.id, latestRun.id, latestCandidate.name, {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'shadow_feature_promotion',
      source: 'latest_candidate',
    });
  };

  const handleBackfillLatestRun = async () => {
    if (!latestRun?.id) {
      message.warning('暂无可回填的因子 run');
      return;
    }
    setRunningBackfill(true);
    try {
      const job = await researchService.createFactorValueBackfillJob({
        run_ids: [latestRun.id],
        dry_run: true,
        max_runs: 1,
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_value_backfill',
          source: 'latest_completed_run',
        },
      });
      const completed = await researchService.runFactorValueBackfillJob(job.id);
      if (completed.status === 'completed') {
        message.success('因子值回填任务已完成');
      } else {
        message.warning(`因子值回填任务状态：${completed.status}`);
      }
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '因子值回填失败');
    } finally {
      setRunningBackfill(false);
    }
  };

  const handleCancelLatestBackfill = async () => {
    if (!latestBackfillJob?.id || !isActiveAsyncStatus(latestBackfillJob.status)) {
      message.warning('暂无可取消的回填任务');
      return;
    }
    setCancellingBackfill(true);
    try {
      const job = await researchService.cancelFactorValueBackfillJob(
        latestBackfillJob.id,
        'factor_research_workbench_cancel',
      );
      message.success(`回填任务已${job.status === 'cancelled' ? '取消' : '更新'}`);
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '回填任务取消失败');
    } finally {
      setCancellingBackfill(false);
    }
  };

  const handlePromoteCampaignBest = async () => {
    if (!latestCampaignBestCandidateId || !latestCampaignBestRunId) {
      message.warning('暂无可晋升的 Campaign 最佳候选');
      return;
    }
    await promoteFactorCandidate(
      latestCampaignBestCandidateId,
      latestCampaignBestRunId,
      latestCampaignBestExpression || `${selectedCampaign?.name || 'campaign'} best factor`,
      {
        submitted_from: 'factor_research_workbench',
        pipeline_stage: 'campaign_best_shadow_feature_promotion',
        source: 'campaign_best_candidate',
        campaign_id: selectedCampaign?.id,
      },
    );
  };

  const handleSelectCampaign = async (campaignId: string) => {
    setSelectedCampaignId(campaignId);
    const existing = campaigns.find((campaign) => campaign.id === campaignId);
    if (existing && Array.isArray(existing.items) && existing.items.length > 0) {
      return;
    }
    try {
      const detail = await researchService.getFactorCampaign(campaignId);
      const found = campaigns.some((campaign) => campaign.id === campaignId);
      setCampaigns(
        found
          ? campaigns.map((campaign) => (campaign.id === campaignId ? detail : campaign))
          : [detail, ...campaigns],
      );
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Campaign 详情加载失败');
    }
  };

  const handleStartCampaign = async () => {
    if (!dateRange[0] || !dateRange[1]) {
      message.warning('请选择挖掘时间窗口');
      return;
    }
    setMiningCampaign(true);
    try {
      const campaign = await researchService.createFactorCampaign({
        name: selectedTemplate ? `${selectedTemplate.label} 自动挖掘` : '自动因子挖掘',
        strategy: campaignStrategy,
        seed_expression: expression.trim(),
        n_candidates: 5,
        max_generations: campaignGenerations,
        run_async: true,
        worker_policy: {
          concurrency: 1,
          max_claims: 1,
          heartbeat_interval_seconds: 30,
        },
        retry_policy: {
          max_attempts: 1,
          retry_failed_after_minutes: 30,
        },
        execution_lease: {
          lease_seconds: 1800,
        },
        universe,
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        n_groups: groups,
        holding_period: holdingPeriod,
        neutralize_industry: true,
        neutralize_cap: true,
        validation_profile: 'campaign',
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_campaign',
          strategy: campaignStrategy,
          max_generations: campaignGenerations,
        },
      });
      const completed = campaign.summary?.completedRuns ?? 0;
      setSelectedCampaignId(campaign.id);
      if (isActiveAsyncStatus(campaign.status)) {
        message.success('Campaign 已进入异步执行队列，结果会自动刷新');
      } else {
        message.success(`Campaign 已完成：${completed}/${campaign.summary?.totalCandidates ?? 0} 个候选完成评估`);
      }
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Campaign 启动失败');
    } finally {
      setMiningCampaign(false);
    }
  };

  const handleCancelCampaign = async () => {
    if (!selectedCampaign?.id || !latestCampaignIsActive) {
      message.warning('暂无运行中的 Campaign 可取消');
      return;
    }
    setCancellingCampaign(true);
    try {
      const campaign = await researchService.cancelFactorCampaign(
        selectedCampaign.id,
        'factor_research_workbench_cancel',
      );
      message.success(`Campaign 已取消：${campaign.name}`);
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Campaign 取消失败');
    } finally {
      setCancellingCampaign(false);
    }
  };

  const handleMaterializeLatest = async () => {
    if (!latestPromotion?.id) {
      message.warning('暂无可物化的 Shadow 特征');
      return;
    }
    setMaterializing(true);
    try {
      const promotion = await researchService.materializeFactorPromotion(latestPromotion.id);
      if (promotion.materializationStatus === 'materialized') {
        message.success(`特征已物化并进入训练目录：${promotion.featureKey}`);
      } else {
        message.warning(promotion.metadata?.materialization?.reason || '训练快照尚未就绪，仍保持待物化');
      }
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '特征物化失败');
    } finally {
      setMaterializing(false);
    }
  };

  const handleLaunchTraining = async () => {
    if (!latestPromotion?.id || latestPromotion.materializationStatus !== 'materialized') {
      message.warning('只有已物化并进入 active feature catalog 的因子才能发起训练');
      return;
    }
    setLaunchingTraining(true);
    try {
      const training = await researchService.launchFactorPromotionTraining(latestPromotion.id, {
        display_name: `因子研究 Shadow 训练 - ${latestPromotion.featureKey}`,
        baseline_display_name: `因子研究 Baseline 训练 - ${latestPromotion.featureKey}`,
        auto_baseline: true,
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_shadow_training',
        },
      });
      message.success(`Shadow 训练已提交：${training.trainingRunId}`);
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Shadow 训练提交失败');
    } finally {
      setLaunchingTraining(false);
    }
  };

  const handleApproveTraining = async () => {
    if (!latestTrainingRun?.id || !canApproveLatestTraining) {
      message.warning('最新训练尚未满足默认模型审批条件');
      return;
    }
    setApprovingTraining(true);
    try {
      await researchService.approveFactorTraining(latestTrainingRun.id, {
        set_default_model: true,
        reason: 'factor_research_gate_approved',
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_model_approval',
        },
      });
      message.success('因子训练候选已审批为默认模型');
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '因子训练审批失败');
    } finally {
      setApprovingTraining(false);
    }
  };

  const handleRequestTrainingApproval = async () => {
    if (!latestTrainingRun?.id || !canApproveLatestTraining) {
      message.warning('最新训练尚未满足默认模型审批申请条件');
      return;
    }
    setRequestingApproval(true);
    try {
      const request = await researchService.requestFactorTrainingApproval(latestTrainingRun.id, {
        reason: 'factor_research_gate_approved',
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_model_approval_request',
        },
      });
      message.success(request.idempotent ? '审批请求已存在，已保留待审批状态' : '默认模型审批请求已提交');
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '默认模型审批请求提交失败');
    } finally {
      setRequestingApproval(false);
    }
  };

  const handleReviewApprovalRequest = async (approve: boolean) => {
    if (!latestApprovalRequest?.id || latestApprovalRequest.status !== 'pending') {
      message.warning('暂无待审核的默认模型审批请求');
      return;
    }
    const action = approve ? 'approve' : 'reject';
    setReviewingApprovalRequest(action);
    try {
      await researchService.reviewFactorApprovalRequest(latestApprovalRequest.id, {
        approve,
        decision: action,
        reason: 'factor_research_admin_review',
        reviewer_note: approve ? 'approved_from_factor_research_workbench' : 'rejected_from_factor_research_workbench',
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_model_approval_review',
        },
      });
      message.success(approve ? '审批请求已通过' : '审批请求已拒绝');
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '审批请求处理失败');
    } finally {
      setReviewingApprovalRequest(null);
    }
  };

  const handleSaveApprovalPolicy = async () => {
    if (!approvalPolicy) {
      message.warning('审批策略尚未加载');
      return;
    }
    setSavingApprovalPolicy(true);
    try {
      const policy = await researchService.updateFactorApprovalPolicy({
        allow_direct_approval: approvalPolicy.allowDirectApproval,
        allow_self_approval: approvalPolicy.allowSelfApproval,
        min_approvals: Math.max(1, approvalPolicy.minApprovals || 1),
        reviewer_permission: approvalPolicy.reviewerPermission || FACTOR_APPROVAL_PERMISSION,
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'factor_approval_policy',
        },
      });
      setApprovalPolicy(policy);
      message.success('审批策略已更新');
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '审批策略保存失败');
    } finally {
      setSavingApprovalPolicy(false);
    }
  };

  const handleRollbackPromotion = async () => {
    if (!latestPromotion?.id) {
      message.warning('暂无可回滚的因子特征');
      return;
    }
    setRollingBackPromotion(true);
    try {
      const promotion = await researchService.rollbackFactorPromotion(latestPromotion.id, 'factor_research_manual_rollback');
      message.success(`已从训练特征集中回滚：${promotion.featureKey}`);
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '因子特征回滚失败');
    } finally {
      setRollingBackPromotion(false);
    }
  };

  const handlePublishShadowSignal = async () => {
    if (!latestCandidate?.id || latestRun?.status !== 'completed') {
      message.warning('只有已完成评估且生成因子值的候选才能发布 Shadow Signal');
      return;
    }
    setPublishingSignal(true);
    try {
      const signalRun = await researchService.publishFactorShadowSignal(latestCandidate.id, {
        run_id: latestRun.id,
        top_n: 20,
        bottom_n: 0,
        long_short: false,
        quantity: 100,
        publish_stream: false,
        metadata: {
          submitted_from: 'factor_research_workbench',
          pipeline_stage: 'shadow_signal_publish',
        },
      });
      message.success(`Shadow Signal 已写入：${signalRun.signalCount} 条`);
      await loadCandidates();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || 'Shadow Signal 发布失败');
    } finally {
      setPublishingSignal(false);
    }
  };

  const candidateColumns = React.useMemo<ColumnsType<FactorCandidate>>(() => [
    {
      title: '候选因子',
      dataIndex: 'name',
      render: (value: string, row) => (
        <div className="min-w-0">
          <div className="font-black text-slate-900">{value}</div>
          <div className="mt-1 max-w-[520px] truncate font-mono text-[11px] text-slate-500" title={row.expression}>
            {row.expression}
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (value: FactorCandidate['status']) => candidateStatusTag(value),
    },
    {
      title: '最新 Run',
      dataIndex: 'latestRun',
      width: 130,
      render: (_, row) => row.latestRun ? (
        <Tooltip title={runReasonText(row)}>
          {runStatusTag(row.latestRun.status)}
        </Tooltip>
      ) : <span className="text-xs font-bold text-slate-400">未创建</span>,
    },
    {
      title: '评估摘要',
      dataIndex: 'latestRun',
      render: (_, row) => {
        const run = row.latestRun;
        const inserted = run?.metrics?.inserted_values;
        const rankIc = run?.metrics?.rank_ic_mean;
        const coverage = run?.metrics?.coverage_days;
        return (
          <div className="max-w-[260px] truncate text-[11px] font-bold leading-5 text-slate-500" title={runReasonText(row)}>
            {run?.status === 'completed' ? (
              <>
                <span className="font-mono text-slate-700">IC {formatMetric(rankIc)}</span>
                <span className="mx-1 text-slate-300">/</span>
                <span>{coverage ?? 0} 天</span>
                <span className="mx-1 text-slate-300">/</span>
                <span>{inserted ?? 0} 条值</span>
              </>
            ) : (
              <span>{runReasonText(row)}</span>
            )}
          </div>
        );
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      width: 160,
      render: (value: string | null) => (
        <span className="text-xs font-bold text-slate-500">{value ? dayjs(value).format('MM-DD HH:mm') : '-'}</span>
      ),
    },
  ], []);

  return (
    <div className="space-y-4 pb-28">
      <div className="rounded-3xl border border-slate-100 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-1 text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">Pre-training Pipeline</div>
            <h2 className="m-0 text-base font-black text-slate-900">因子研究是模型训练的前置流水线</h2>
            <p className="m-0 mt-1 text-xs font-medium leading-5 text-slate-500">
              只有通过研究门禁并晋升为 shadow feature set 的因子，才进入模型训练的特征选择；未通过的表达式保留为候选或归档。
            </p>
          </div>
          <div className="grid min-w-[460px] max-w-full grid-cols-3 gap-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-center text-[11px] font-black text-slate-500">
            <span className="rounded-xl bg-white px-3 py-2 text-emerald-700 shadow-sm">因子研究</span>
            <span className="rounded-xl px-3 py-2 text-blue-600">模型训练</span>
            <span className="rounded-xl px-3 py-2">模型管理</span>
          </div>
        </div>
        <details className="mt-3 group">
          <summary className="flex cursor-pointer list-none items-center justify-between rounded-2xl border border-slate-100 bg-slate-50 px-4 py-2.5 text-xs font-black text-slate-600">
            <span>查看完整 8 步流水线</span>
            <span className="text-slate-400 group-open:hidden">展开</span>
            <span className="hidden text-slate-400 group-open:inline">收起</span>
          </summary>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {PIPELINE_STEPS.map((step, index) => {
              const Icon = step.icon;
              const toneClass = step.tone === 'emerald'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                : step.tone === 'violet'
                  ? 'bg-violet-50 text-violet-700 border-violet-100'
                  : step.tone === 'amber'
                    ? 'bg-amber-50 text-amber-700 border-amber-100'
                    : 'bg-blue-50 text-blue-700 border-blue-100';
              return (
                <div key={step.title} className="rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className={`flex h-9 w-9 items-center justify-center rounded-xl border ${toneClass}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-slate-500">
                      {String(index + 1).padStart(2, '0')} · {step.value}
                    </span>
                  </div>
                  <div className="text-sm font-black text-slate-900">{step.title}</div>
                  <div className="mt-1 min-h-[36px] text-xs font-medium leading-5 text-slate-500">{step.description}</div>
                  <div className="mt-3 rounded-xl bg-white px-3 py-2 text-[11px] font-black text-slate-600">
                    产物：{step.output}
                  </div>
                </div>
              );
            })}
          </div>
        </details>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <div className="rounded-3xl border border-slate-100 bg-white p-4 shadow-sm">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg shadow-slate-300/50">
                  <FlaskConical className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="m-0 text-base font-black text-slate-900">因子研究工作台</h2>
                  <p className="m-0 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Cross-module Factor Pipeline</p>
                </div>
              </div>
              <Segmented
                value={mode}
                onChange={(value) => setMode(value as LabMode)}
                options={[
                  { label: '挖掘', value: 'campaign' },
                  { label: '评估', value: 'evaluate' },
                  { label: '晋升', value: 'promote' },
                  { label: '信号', value: 'signal' },
                ]}
                className="research-next-segmented p-1"
              />
            </div>

            <div className="mb-3 grid gap-3 lg:grid-cols-3">
              {FACTOR_TEMPLATES.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setExpression(item.expression)}
                  className={`rounded-2xl border p-4 text-left transition-all ${expression === item.expression
                    ? 'border-blue-200 bg-blue-50 shadow-md shadow-blue-100/70'
                    : 'border-slate-100 bg-slate-50/60 hover:border-slate-200 hover:bg-white'
                    }`}
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-black text-slate-800">{item.label}</span>
                    <Tag className="m-0 rounded-full border-none bg-white text-[10px] font-bold text-slate-500">{item.family}</Tag>
                  </div>
                  <div className="font-mono text-[11px] leading-5 text-slate-500">{item.expression}</div>
                </button>
              ))}
            </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px]">
            <div className="space-y-3">
              <Input.TextArea
                value={expression}
                onChange={(event) => setExpression(event.target.value)}
                autoSize={{ minRows: 3, maxRows: 5 }}
                className="rounded-2xl border-slate-200 font-mono text-sm"
              />
              <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
                <Select
                  value={universe}
                  onChange={setUniverse}
                  options={[
                    { value: 'hs300', label: '沪深 300' },
                    { value: 'csi500', label: '中证 500' },
                    { value: 'small_scale', label: '小样本' },
                  ]}
                  className="w-full"
                />
                <RangePicker
                  value={dateRange}
                  onChange={(value) => {
                    if (value?.[0] && value?.[1]) setDateRange([value[0], value[1]]);
                  }}
                  className="w-full rounded-xl"
                />
                <div className="flex h-8 items-center rounded-md border border-slate-200 bg-white">
                  <span className="shrink-0 border-r border-slate-200 px-3 text-xs font-bold text-slate-500">分组</span>
                  <InputNumber
                    aria-label="分组数量"
                    value={groups}
                    min={2}
                    max={20}
                    variant="borderless"
                    onChange={(value) => setGroups(value || 5)}
                    className="min-w-0 flex-1"
                  />
                </div>
                <div className="flex h-8 items-center rounded-md border border-slate-200 bg-white">
                  <span className="shrink-0 border-r border-slate-200 px-3 text-xs font-bold text-slate-500">持有</span>
                  <InputNumber
                    aria-label="持有周期"
                    value={holdingPeriod}
                    min={1}
                    max={60}
                    variant="borderless"
                    onChange={(value) => setHoldingPeriod(value || 5)}
                    className="min-w-0 flex-1"
                  />
                  <span className="shrink-0 border-l border-slate-200 px-3 text-xs font-bold text-slate-500">日</span>
                </div>
                {mode === 'campaign' && (
                  <>
                    <div className="min-w-0 md:col-span-2 2xl:col-span-3">
                      <Segmented
                        aria-label="Campaign 策略"
                        value={campaignStrategy}
                        onChange={(value) => setCampaignStrategy(value as CampaignStrategy)}
                        options={[
                          { label: '突变+交叉', value: 'mutation_crossover' },
                          { label: '因子进化', value: 'quantgpt_meta_evolution' },
                          { label: '因子交叉', value: 'quantgpt_crossover_only' },
                          { label: '仅突变', value: 'template_mutation' },
                        ]}
                        block
                        className="w-full bg-white"
                      />
                    </div>
                    <div className="flex h-8 items-center rounded-md border border-slate-200 bg-white md:col-span-2 2xl:col-span-1">
                      <span className="shrink-0 border-r border-slate-200 px-3 text-xs font-bold text-slate-500">代数</span>
                      <InputNumber
                        aria-label="Campaign 代数"
                        value={campaignGenerations}
                        min={1}
                        max={5}
                        variant="borderless"
                        onChange={(value) => setCampaignGenerations(value || 1)}
                        className="min-w-0 flex-1"
                      />
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">
                <Activity className="h-3.5 w-3.5" />
                任务摘要
              </div>
              <div className="space-y-2 text-xs font-bold leading-6 text-slate-600">
                <div className="flex justify-between gap-3"><span>股票池</span><span className="font-mono text-slate-800">{universe}</span></div>
                <div className="flex justify-between gap-3"><span>区间</span><span className="font-mono text-slate-800">{requestPreview.start_date} ~ {requestPreview.end_date}</span></div>
                <div className="flex justify-between gap-3"><span>分组 / 持有</span><span className="font-mono text-slate-800">{groups} / T+{holdingPeriod}</span></div>
                {mode === 'campaign' && (
                  <div className="flex justify-between gap-3"><span>Campaign</span><span className="font-mono text-slate-800">{campaignStrategy} · G{campaignGenerations}</span></div>
                )}
              </div>
              <Button
                size="small"
                type="link"
                onClick={() => setRequestContractOpen(true)}
                className="mt-3 h-auto p-0 text-[11px] font-black text-slate-400"
              >
                高级：查看请求契约
              </Button>
            </div>
          </div>

          <div className="mt-4 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Tag color="success" className="m-0 rounded-full font-bold">本地 Evaluator 已接入</Tag>
              <Tag color="success" className="m-0 rounded-full font-bold">因子值落库已接入</Tag>
              <Tag color="success" className="m-0 rounded-full font-bold">任务 API 已接入</Tag>
              {selectedTemplate && <Tag className="m-0 rounded-full bg-white font-bold">{selectedTemplate.label}</Tag>}
            </div>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <Tooltip title="创建候选因子并生成可追踪评估 run">
                <Button
                  type="primary"
                  icon={<Play className="h-4 w-4" />}
                  loading={submitting}
                  onClick={handleSubmitEvaluation}
                  className="w-full rounded-xl font-black"
                >
                  提交评估
                </Button>
              </Tooltip>
              <Tooltip title="基于当前表达式启动本地 mutation/crossover campaign，批量生成候选并逐个评估">
                <Button
                  icon={<Sparkles className="h-4 w-4" />}
                  loading={miningCampaign}
                  onClick={handleStartCampaign}
                  className="w-full rounded-xl font-black"
                >
                  启动 Campaign
                </Button>
              </Tooltip>
              <Tooltip title="把最新 completed run 登记为 shadow feature；未物化前不会进入模型训练 active catalog">
                <Button
                  icon={<GitBranch className="h-4 w-4" />}
                  loading={promoting}
                  disabled={latestRun?.status !== 'completed'}
                  onClick={handlePromoteLatest}
                  className="w-full rounded-xl font-black"
                >
                  登记 Shadow 特征
                </Button>
              </Tooltip>
              <Tooltip title="将最新 completed run 的截面因子值写入 shadow signal 表；默认不写 Redis latest key">
                <Button
                  icon={<Radio className="h-4 w-4" />}
                  loading={publishingSignal}
                  disabled={latestRun?.status !== 'completed'}
                  onClick={handlePublishShadowSignal}
                  className="w-full rounded-xl font-black"
                >
                  发布 Shadow Signal
                </Button>
              </Tooltip>
            </div>
          </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <Text className="block text-sm font-black text-slate-900">候选因子队列</Text>
                <Text className="text-xs text-slate-400">
                  已入库 {candidateTotal} 个候选；评估产物统一写入候选、run、factor values，后续供模型训练和信号灰度消费。
                </Text>
              </div>
              <Button size="small" onClick={() => void loadCandidates()} loading={loadingCandidates} className="rounded-xl font-bold">
                刷新
              </Button>
            </div>
            <Table<FactorCandidate>
              rowKey="id"
              columns={candidateColumns}
              dataSource={candidates}
              loading={loadingCandidates}
              pagination={false}
              size="small"
              className="research-table"
            />
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <Text className="block text-sm font-black text-slate-900">
                  {mode === 'campaign'
                    ? 'Campaign 评估门禁'
                    : mode === 'evaluate'
                      ? '候选因子门禁'
                      : mode === 'promote'
                        ? 'Feature 晋升门禁'
                        : '灰度信号门禁'}
                </Text>
                <Text className="text-xs text-slate-400">
                  {mode === 'campaign'
                    ? '每个候选都会复用同一套候选评估和晋升门禁'
                    : mode === 'evaluate'
                    ? '与后端 factor_promotion.py 阈值保持一致'
                    : mode === 'promote'
                      ? '只允许进入 shadow feature set'
                      : '只允许模拟盘或 shadow runner 消费'}
                </Text>
              </div>
              <Tag color="blue" className="m-0 rounded-full px-3 py-1 font-black">
                {mode === 'campaign'
                  ? 'Batch eval'
                  : mode === 'evaluate'
                    ? 'Contract-first'
                    : mode === 'promote'
                      ? 'Shadow only'
                      : 'Sim only'}
              </Tag>
            </div>
            <Table<GateRow>
              rowKey="key"
              columns={gateColumns}
              dataSource={dynamicGateRows}
              pagination={false}
              size="small"
              className="research-table"
            />
          </div>
        </div>

        <div className="space-y-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-430px)] xl:overflow-y-auto xl:pr-1 custom-scrollbar">
          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-sky-500" />
                <Text className="text-sm font-black text-slate-800">运行健康</Text>
              </div>
              {healthStatusTag(factorHealth?.status)}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                ['失败 Run', factorHealth?.indicators?.recent_failed_runs ?? 0],
                ['待物化', factorHealth?.indicators?.pending_materializations ?? 0],
                ['活跃 Campaign', factorHealth?.indicators?.active_campaigns ?? 0],
                ['Worker 事件', factorHealth?.indicators?.worker_recent_events ?? 0],
                ['Worker 失败', factorHealth?.indicators?.worker_recent_failures ?? 0],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-slate-100 bg-slate-50 px-2 py-2 text-center">
                  <div className="text-[10px] font-bold text-slate-400">{label}</div>
                  <div className="mt-1 text-sm font-black text-slate-800">{value}</div>
                </div>
              ))}
            </div>
            {factorHealth?.slo && (
              <div
                data-testid="factor-research-slo-panel"
                className="mt-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-[11px] font-black text-slate-700">SLO</span>
                  <Tag
                    color={factorHealth.slo.status === 'met' ? 'success' : 'warning'}
                    className="m-0 rounded-full font-bold"
                  >
                    {factorHealth.slo.status === 'met' ? '达标' : '需关注'}
                  </Tag>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-slate-500">
                  <span>Run 成功率 {percentText(factorHealth.slo.metrics?.runSuccessRate)}</span>
                  <span>Campaign 成功率 {percentText(factorHealth.slo.metrics?.campaignSuccessRate)}</span>
                  <span>P95 {factorHealth.slo.metrics?.campaignP95DurationSeconds ?? 0}s</span>
                  <span>Pending {factorHealth.slo.metrics?.pendingCampaigns ?? 0}</span>
                  <span>Stale {factorHealth.slo.metrics?.staleRunningCampaigns ?? 0}</span>
                  <span>Backfill 失败 {factorHealth.slo.metrics?.backfillFailedJobs ?? 0}</span>
                </div>
              </div>
            )}
            <div className="mt-3 space-y-2">
              {(factorHealth?.alerts || []).slice(0, 3).map((alert) => (
                <div
                  key={`${alert.level}-${alert.code}`}
                  className={`rounded-xl border px-3 py-2 text-[11px] font-bold ${
                    alert.level === 'critical'
                      ? 'border-red-100 bg-red-50 text-red-700'
                      : 'border-amber-100 bg-amber-50 text-amber-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span>{healthAlertLabel(alert.code)}</span>
                    <span>{alert.value ?? alert.count ?? 0}</span>
                  </div>
                </div>
              ))}
              {factorHealth && factorHealth.alerts.length === 0 && (
                <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-[11px] font-bold text-emerald-700">
                  最近 {factorHealth.windowHours} 小时无运行告警
                </div>
              )}
              {!factorHealth && (
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-500">
                  等待健康摘要加载
                </div>
              )}
            </div>
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="mb-2 flex items-center justify-between">
                <Text className="text-[11px] font-black text-slate-500">Worker 最近事件</Text>
                <Text className="text-[10px] font-bold text-slate-400">{workerEvents.length} 条</Text>
              </div>
              <div className="space-y-2">
                {workerEvents.slice(0, 5).map((event) => (
                  <div key={event.id} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-black text-slate-700">{workerEventLabel(event.eventType)}</span>
                      <span className={`text-[10px] font-black ${event.status === 'failed' || event.status === 'error' ? 'text-red-600' : 'text-emerald-600'}`}>
                        {event.status}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-[10px] font-bold text-slate-400">
                      <span className="truncate">{workerEventSummary(event)}</span>
                      <span>{event.heartbeatAt ? dayjs(event.heartbeatAt).format('MM-DD HH:mm') : event.createdAt ? dayjs(event.createdAt).format('MM-DD HH:mm') : '-'}</span>
                    </div>
                  </div>
                ))}
                {workerEvents.length === 0 && (
                  <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-500">
                    暂无 Worker 事件
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-blue-500" />
                <Text className="text-sm font-black text-slate-800">因子值回填</Text>
              </div>
              {runStatusTag(latestBackfillJob?.status)}
            </div>
            <div className="space-y-2 text-xs font-bold leading-6 text-slate-500">
              <div>最近任务：<span className="font-mono text-slate-700">{latestBackfillJob?.id?.slice(0, 8) || '-'}</span></div>
              <div>
                目标：run {(latestBackfillJob?.target?.runIds || []).length} / candidate {(latestBackfillJob?.target?.candidateIds || []).length} / promotion {(latestBackfillJob?.target?.promotionIds || []).length}
              </div>
              <div>
                结果：resolved {latestBackfillJob?.result?.resolvedRuns ?? '-'} / processed {latestBackfillJob?.result?.processedRuns ?? '-'}
              </div>
              <div>
                Worker：<span className="font-mono text-slate-700">{latestBackfillJob?.workerId || backfillEvents[0]?.workerId || '-'}</span>
              </div>
              <div>
                最近事件：{backfillEvents[0]?.eventType || '-'} / {backfillEvents[0]?.status || '-'}
              </div>
              {latestBackfillJob?.errorMessage && (
                <div className="break-all text-rose-500">失败原因：{latestBackfillJob.errorMessage}</div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="small"
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  loading={runningBackfill}
                  disabled={!latestRun?.id || latestRun.status !== 'completed'}
                  onClick={handleBackfillLatestRun}
                  className="rounded-xl font-black"
                >
                  回填最新 Run
                </Button>
                <Button
                  size="small"
                  danger
                  icon={<XCircle className="h-3.5 w-3.5" />}
                  loading={cancellingBackfill}
                  disabled={!latestBackfillJob?.id || !isActiveAsyncStatus(latestBackfillJob.status)}
                  onClick={handleCancelLatestBackfill}
                  className="rounded-xl font-black"
                >
                  取消回填
                </Button>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-500" />
              <Text className="text-sm font-black text-slate-800">能力状态</Text>
            </div>
            <div className="space-y-3">
              {[
                ['因子研究入口', '已独立'],
                ['本地评估器', '已接入'],
                ['表达式契约映射', '已完成'],
                ['自动挖掘 Campaign', '已接入'],
                ['因子值落库', '已接入'],
                ['门禁状态回写', '已接入'],
                ['训练前置关系', '已接入'],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-xs font-bold text-slate-500">{label}</span>
                  <span className={`text-xs font-black ${value === '已完成' || value === '已接入' || value === '已独立' ? 'text-emerald-600' : 'text-amber-600'}`}>{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-teal-500" />
              <Text className="text-sm font-black text-slate-800">产物去向</Text>
            </div>
            <div className="space-y-2">
              {[
                ['模型训练', '晋升为训练特征'],
                ['模型管理', '进入因子贡献与版本追踪'],
                ['智能策略', '转成可引用信号模板'],
                ['回测中心', '验证分组收益与换手成本'],
              ].map(([target, usage]) => (
                <div key={target} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="text-xs font-black text-slate-800">{target}</div>
                  <div className="mt-0.5 text-[11px] font-bold text-slate-500">{usage}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-violet-500" />
                <Text className="text-sm font-black text-slate-800">Campaign 状态</Text>
              </div>
              <Tag color={selectedCampaign ? 'processing' : 'default'} className="m-0 rounded-full font-bold">
                {shouldAutoRefresh ? '自动刷新中' : selectedCampaign?.status || '未启动'}
              </Tag>
            </div>
            <div className="space-y-2 text-xs font-bold leading-6 text-slate-500">
              <div>当前 Campaign：{selectedCampaign?.name || '暂无'}</div>
              <div>完成候选：{selectedCampaign?.summary?.completedRuns ?? 0}/{selectedCampaign?.summary?.totalCandidates ?? 0}</div>
              <div>
                代际进度：{selectedCampaign?.summary?.completedGenerations ?? 0}/{selectedCampaign?.summary?.maxGenerations ?? 0}
              </div>
              <div className="break-all">最佳表达式：<span className="font-mono text-slate-700">{selectedCampaign?.summary?.bestExpression || '-'}</span></div>
              {(selectedCampaign?.summary?.generationStats || []).length > 0 && (
                <div className="space-y-1 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                  {(selectedCampaign?.summary?.generationStats || []).slice(0, 5).map((generation: any) => (
                    <div
                      key={generation.generation}
                      className="grid grid-cols-[34px_52px_1fr_58px] items-center gap-2 text-[11px] text-slate-500"
                    >
                      <span className="font-mono font-black">G{generation.generation}</span>
                      <span className="font-mono">{generation.completedRuns}/{generation.totalCandidates}</span>
                      <span className="truncate font-mono text-slate-700">{generation.bestExpression || '-'}</span>
                      <span className="truncate text-right font-mono">
                        {typeof generation.bestScore === 'number' ? generation.bestScore.toFixed(4) : '-'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {((selectedCampaign?.summary?.operatorStats || []).length > 0 ||
                (selectedCampaign?.summary?.reasonStats || []).length > 0 ||
                (selectedCampaign?.summary?.lineageEdges || []).length > 0) && (
                <div className="space-y-1 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                  <div className="text-[11px] font-black text-slate-700">进化摘要</div>
                  {(selectedCampaign?.summary?.operatorStats || []).slice(0, 4).map((item: any) => (
                    <div key={item.operator} className="grid grid-cols-[1fr_52px_58px] gap-2 text-[10px] text-slate-500">
                      <span className="truncate font-mono">{item.operator || '-'}</span>
                      <span className="font-mono">{item.completedRuns ?? 0}/{item.totalCandidates ?? 0}</span>
                      <span className="truncate text-right font-mono">
                        {typeof item.bestScore === 'number' ? item.bestScore.toFixed(4) : '-'}
                      </span>
                    </div>
                  ))}
                  {(selectedCampaign?.summary?.reasonStats || []).slice(0, 2).map((item: any) => (
                    <div key={item.reason} className="truncate text-[10px] text-slate-400">
                      原因 {item.count ?? 0}：{item.reason || '-'}
                    </div>
                  ))}
                  <div className="text-[10px] font-mono text-slate-400">
                    lineage edges: {(selectedCampaign?.summary?.lineageEdges || []).length}
                  </div>
                </div>
              )}
              <div className="border-t border-slate-100 pt-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="font-black text-slate-700">Campaign 历史</span>
                  <span className="font-mono text-[11px] text-slate-400">{campaigns.length} 条</span>
                </div>
                {campaigns.length > 0 ? (
                  <div className="space-y-1">
                    {campaigns.slice(0, 6).map((campaign) => {
                      const active = campaign.id === selectedCampaign?.id;
                      return (
                        <button
                          key={campaign.id}
                          type="button"
                          onClick={() => handleSelectCampaign(campaign.id)}
                          className={`grid w-full grid-cols-[1fr_62px_54px] items-center gap-2 rounded-xl border px-3 py-2 text-left text-[11px] transition ${
                            active
                              ? 'border-blue-200 bg-blue-50 text-blue-700'
                              : 'border-slate-100 bg-slate-50 text-slate-500 hover:border-slate-200 hover:bg-white'
                          }`}
                        >
                          <span className="truncate font-black">{campaign.name}</span>
                          <span className="font-mono">
                            G{campaign.summary?.completedGenerations ?? 0}/{campaign.summary?.maxGenerations ?? 0}
                          </span>
                          <span className="truncate text-right font-mono">
                            {typeof campaign.summary?.bestScore === 'number'
                              ? campaign.summary.bestScore.toFixed(4)
                              : campaign.status}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-[11px] font-bold text-slate-400">
                    启动 Campaign 后保留跨代历史
                  </div>
                )}
              </div>
              <div className="border-t border-slate-100 pt-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="font-black text-slate-700">候选历史</span>
                  <span className="font-mono text-[11px] text-slate-400">
                    {(selectedCampaign?.items || []).length} 条
                  </span>
                </div>
                {(selectedCampaign?.items || []).length > 0 ? (
                  <div className="space-y-1">
                    {(selectedCampaign?.items || []).slice(0, 8).map((item) => {
                      const rankIc = typeof item.metrics?.rank_ic_mean === 'number'
                        ? item.metrics.rank_ic_mean.toFixed(4)
                        : '-';
                      const icIr = typeof item.metrics?.ic_ir === 'number'
                        ? item.metrics.ic_ir.toFixed(2)
                        : '-';
                      const turnover = typeof item.metrics?.turnover_mean === 'number'
                        ? item.metrics.turnover_mean.toFixed(2)
                        : '-';
                      const operator = String(item.metadata?.operator || item.metadata?.sourceStrategy || '-');
                      const quantgptStrategy = item.metadata?.quantgptStrategy
                        ? String(item.metadata.quantgptStrategy)
                        : '';
                      const parentExpressions = Array.isArray(item.metadata?.parentExpressions)
                        ? item.metadata?.parentExpressions
                        : [];
                      const evolutionReason = item.metadata?.evolutionReason
                        ? String(item.metadata.evolutionReason)
                        : '';
                      return (
                        <div
                          key={`${item.generation}-${item.rankNo}-${item.expression}`}
                          className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                        >
                          <div className="grid grid-cols-[46px_66px_1fr_60px] items-center gap-2 text-[11px]">
                            <span className="font-mono text-slate-400">G{item.generation}.{item.rankNo}</span>
                            <span>{runStatusTag(item.status)}</span>
                            <span className="truncate font-mono text-slate-700">{item.expression}</span>
                            <span className="truncate text-right font-mono text-slate-500">
                              {typeof item.score === 'number' ? item.score.toFixed(4) : '-'}
                            </span>
                          </div>
                          <div className="mt-1 grid grid-cols-[1fr_1fr] gap-x-2 gap-y-1 text-[10px] leading-4 text-slate-400">
                            <span className="truncate font-mono">run: {item.runId || '-'}</span>
                            <span className="truncate font-mono">candidate: {item.candidateId || '-'}</span>
                            <span className="font-mono">RankIC {rankIc} · ICIR {icIr} · Turnover {turnover}</span>
                            <span className="truncate text-right">原因：{item.reason || '-'}</span>
                            <span className="truncate font-mono">
                              算子 {operator}{quantgptStrategy ? ` · ${quantgptStrategy}` : ''}
                            </span>
                            <span className="truncate text-right font-mono">
                              parents: {parentExpressions.length > 0 ? parentExpressions.slice(0, 2).join(' | ') : '-'}
                            </span>
                            {evolutionReason && (
                              <span className="col-span-2 truncate">进化理由：{evolutionReason}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-[11px] font-bold text-slate-400">
                    Campaign 完成后展示每代候选和评估分数
                  </div>
                )}
              </div>
              {selectedCampaign?.summary?.cancelled && (
                <div className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                  取消原因：{selectedCampaign.summary.cancelReason || '-'}
                </div>
              )}
              <Button
                size="small"
                type="primary"
                icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                loading={promoting}
                disabled={!latestCampaignBestCandidateId || !latestCampaignBestRunId}
                onClick={handlePromoteCampaignBest}
                className="rounded-xl font-black"
              >
                晋升最佳候选
              </Button>
              <Button
                size="small"
                danger
                icon={<XCircle className="h-3.5 w-3.5" />}
                loading={cancellingCampaign}
                disabled={!latestCampaignIsActive}
                onClick={handleCancelCampaign}
                className="rounded-xl font-black"
              >
                取消 Campaign
              </Button>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-2 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <Text className="text-sm font-black text-slate-800">最新评估状态</Text>
            </div>
            <div className="space-y-2 text-xs font-bold leading-6 text-slate-500">
              <div>最新候选：{latestCandidate?.name || '暂无'}</div>
              <div className="flex items-center gap-2">最新状态：{latestRun ? runStatusTag(latestRun.status) : runStatusTag()}</div>
              <div className="break-all">原因：{runReasonText(latestCandidate)}</div>
            </div>
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                <Text className="font-black text-slate-700">Factor Values 预览</Text>
                <span className="font-mono font-black text-slate-500">
                  {factorRunValues?.summary?.total ?? 0} 条
                </span>
              </div>
              {factorRunValues?.summary && Array.isArray(factorRunValues.items) ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-3 gap-2 text-[11px] font-black text-slate-400">
                    <span>日期 {factorRunValues.summary.tradeDateCount}</span>
                    <span>股票 {factorRunValues.summary.symbolCount}</span>
                    <span>样本 {factorRunValues.items.length}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[11px] font-black text-slate-400">
                    <span>空值 {factorRunValues.summary.nullValueCount ?? 0}</span>
                    <span>异常代码 {factorRunValues.summary.invalidSymbolCount ?? 0}</span>
                    <span>Source {factorRunValues.summary.sourceCount ?? 0}</span>
                  </div>
                  {(factorRunValues.summary.sourceDistribution || []).length > 0 && (
                    <div className="truncate text-[11px] font-bold text-slate-400">
                      来源：{(factorRunValues.summary.sourceDistribution || [])
                        .slice(0, 2)
                        .map((source) => `${source.source}:${source.count}`)
                        .join(' / ')}
                    </div>
                  )}
                  {(factorRunValues.summary.invalidSymbolSamples || []).length > 0 && (
                    <div className="truncate text-[11px] font-bold text-amber-600">
                      异常代码样本：{(factorRunValues.summary.invalidSymbolSamples || []).slice(0, 3).join(', ')}
                    </div>
                  )}
                  <div className="space-y-1">
                    {factorRunValues.items.map((item) => (
                      <div
                        key={`${item.tradeDate || 'date'}-${item.symbol}`}
                        className="grid grid-cols-[82px_78px_1fr] items-center gap-2 text-[11px] font-bold text-slate-500"
                      >
                        <span className="truncate font-mono">{item.tradeDate || '-'}</span>
                        <span className="truncate font-mono text-slate-700">{item.symbol || '-'}</span>
                        <span className="truncate font-mono text-right text-slate-700">
                          {formatMetric(item.factorValue)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs font-bold text-slate-400">
                  {latestRun?.status === 'completed' ? '暂无 factor values 预览' : 'run 完成后展示因子值样本'}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-amber-500" />
                <Text className="text-sm font-black text-slate-800">Feature 晋升状态</Text>
              </div>
              {promotionStatusTag(latestPromotion?.materializationStatus)}
            </div>
            <div className="space-y-2 text-xs font-bold leading-6 text-slate-500">
              <div>Feature Key：<span className="font-mono text-slate-700">{latestPromotion?.featureKey || '-'}</span></div>
              <div>Feature Set：<span className="font-mono text-slate-700">{latestPromotion?.versionId || '-'}</span></div>
              <div className="break-all">
                状态说明：{latestPromotion?.metadata?.materialization?.reason || 'completed run 可登记；训练快照包含该列后才会进入可训练目录'}
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <Button
                  size="small"
                  icon={<Database className="h-3.5 w-3.5" />}
                  loading={materializing}
                  disabled={!latestPromotion?.id || latestPromotion.materializationStatus === 'materialized'}
                  onClick={handleMaterializeLatest}
                  className="rounded-xl font-black"
                >
                  物化到训练快照
                </Button>
                <Button
                  size="small"
                  type="primary"
                  icon={<Play className="h-3.5 w-3.5" />}
                  loading={launchingTraining}
                  disabled={!latestPromotion?.id || latestPromotion.materializationStatus !== 'materialized'}
                  onClick={handleLaunchTraining}
                  className="rounded-xl font-black"
                >
                  发起 Shadow 训练
                </Button>
                <Button
                  size="small"
                  icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                  loading={approvingTraining}
                  disabled={!canReviewApprovals || !canApproveLatestTraining || directApprovalDisabledByPolicy}
                  onClick={handleApproveTraining}
                  className="rounded-xl font-black"
                >
                  审批为默认模型
                </Button>
                <Button
                  size="small"
                  icon={<ShieldCheck className="h-3.5 w-3.5" />}
                  loading={requestingApproval}
                  disabled={!canApproveLatestTraining || (canReviewApprovals && !directApprovalDisabledByPolicy)}
                  onClick={handleRequestTrainingApproval}
                  className="rounded-xl font-black"
                >
                  提交审批请求
                </Button>
                <Button
                  size="small"
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  loading={loadingCandidates}
                  onClick={loadCandidates}
                  className="rounded-xl font-black"
                >
                  刷新训练
                </Button>
                <Button
                  size="small"
                  danger
                  icon={<RotateCcw className="h-3.5 w-3.5" />}
                  loading={rollingBackPromotion}
                  disabled={!latestPromotion?.id || latestPromotion.materializationStatus === 'rolled_back'}
                  onClick={handleRollbackPromotion}
                  className="rounded-xl font-black"
                >
                  回滚特征
                </Button>
              </div>
              <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-[11px] text-slate-700">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-black text-slate-800">默认模型审批策略</div>
                    <div className="mt-0.5 text-slate-500">
                      直接审批、自审与多人审批会影响训练候选晋升默认模型。
                    </div>
                  </div>
                  <Tag color={directApprovalDisabledByPolicy ? 'warning' : 'processing'} className="m-0 rounded-full text-[10px] font-bold">
                    {directApprovalDisabledByPolicy ? '需走审批请求' : '允许直接审批'}
                  </Tag>
                </div>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
                  <label className="flex items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white px-2 py-1.5">
                    <span className="font-bold">允许直接审批</span>
                    <Switch
                      size="small"
                      checked={approvalPolicy?.allowDirectApproval !== false}
                      disabled={!canReviewApprovals || loadingApprovalPolicy || !approvalPolicy}
                      onChange={(checked) => {
                        if (approvalPolicy) setApprovalPolicy({ ...approvalPolicy, allowDirectApproval: checked });
                      }}
                    />
                  </label>
                  <label className="flex items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white px-2 py-1.5">
                    <span className="font-bold">允许自审</span>
                    <Switch
                      size="small"
                      checked={approvalPolicy?.allowSelfApproval !== false}
                      disabled={!canReviewApprovals || loadingApprovalPolicy || !approvalPolicy}
                      onChange={(checked) => {
                        if (approvalPolicy) setApprovalPolicy({ ...approvalPolicy, allowSelfApproval: checked });
                      }}
                    />
                  </label>
                  <label className="flex items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white px-2 py-1.5">
                    <span className="font-bold">最少审批人数</span>
                    <InputNumber
                      size="small"
                      min={1}
                      max={5}
                      value={approvalPolicy?.minApprovals || 1}
                      disabled={!canReviewApprovals || loadingApprovalPolicy || !approvalPolicy}
                      onChange={(value) => {
                        if (approvalPolicy) setApprovalPolicy({ ...approvalPolicy, minApprovals: Number(value || 1) });
                      }}
                      className="w-16"
                    />
                  </label>
                </div>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-[10px] text-slate-500">
                    reviewer={approvalPolicy?.reviewerPermission || FACTOR_APPROVAL_PERMISSION}
                  </span>
                  <Button
                    size="small"
                    type="primary"
                    icon={<ShieldCheck className="h-3.5 w-3.5" />}
                    loading={savingApprovalPolicy}
                    disabled={!canReviewApprovals || loadingApprovalPolicy || !approvalPolicy}
                    onClick={handleSaveApprovalPolicy}
                    className="h-7 rounded-lg text-[11px] font-black"
                  >
                    保存策略
                  </Button>
                </div>
              </div>
              <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span>最新训练</span>
                  {runStatusTag(latestTrainingRun?.trainingStatus || latestTrainingRun?.status)}
                </div>
                <div className="mt-1 break-all font-mono text-[11px] text-slate-700">{latestTrainingRun?.trainingRunId || '-'}</div>
                <div className="mt-1 grid grid-cols-2 gap-2 text-[11px]">
                  <span>进度：{typeof latestTrainingRun?.trainingProgress === 'number' ? `${latestTrainingRun.trainingProgress}%` : '-'}</span>
                  <span>结果：{trainingMetricSummary(latestTrainingRun)}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-2 text-[11px]">
                  <span className="min-w-0 truncate">对比：{trainingComparisonSummary(latestTrainingRun)}</span>
                  {trainingComparisonTag(latestTrainingRun)}
                </div>
                <div className="mt-2 flex items-center justify-between gap-2 text-[11px]">
                  <span className="min-w-0 truncate">门禁：{trainingGateSummary(latestTrainingRun)}</span>
                  {trainingGateTag(latestTrainingRun)}
                </div>
                {latestTrainingRun?.metadata?.approval?.default_model_set && (
                  <div className="mt-2 rounded-lg border border-emerald-100 bg-emerald-50 px-2 py-2 text-[11px] text-emerald-700">
                    <div className="break-all font-bold">
                      已设为默认模型：{latestTrainingRun.metadata.approval.model_id || '-'}
                    </div>
                    <div className="mt-1 text-emerald-600">
                      自动托管只消费默认模型生产批次，审批后还需要在模型管理生成生产批次。
                    </div>
                    <Button
                      size="small"
                      type="link"
                      icon={<ArrowRight className="h-3.5 w-3.5" />}
                      onClick={() => navigate('/model-registry')}
                      className="mt-1 h-auto p-0 text-[11px] font-black text-emerald-700"
                    >
                      前往模型管理生成生产批次
                    </Button>
                  </div>
                )}
                <div className="mt-2 rounded-lg border border-slate-100 bg-white px-2 py-2 text-[11px] text-slate-600">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-black text-slate-700">审批请求</span>
                    <Tag color={latestApprovalRequest ? 'warning' : 'default'} className="m-0 rounded-full text-[10px] font-bold">
                      {latestApprovalRequest?.status || '暂无'}
                    </Tag>
                  </div>
                  <div className="mt-1 break-all font-mono text-slate-500">
                    {latestApprovalRequest?.modelId || '-'}
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate">原因：{latestApprovalRequest?.requestReason || '-'}</span>
                    <span>{latestApprovalRequest?.idempotent ? '已存在' : latestApprovalRequest ? '待处理' : '-'}</span>
                  </div>
                  {canReviewApprovals && latestApprovalRequest?.status === 'pending' && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button
                        size="small"
                        type="primary"
                        icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                        loading={reviewingApprovalRequest === 'approve'}
                        disabled={Boolean(reviewingApprovalRequest)}
                        onClick={() => handleReviewApprovalRequest(true)}
                        className="h-7 rounded-lg text-[11px] font-black"
                      >
                        通过请求
                      </Button>
                      <Button
                        size="small"
                        danger
                        icon={<XCircle className="h-3.5 w-3.5" />}
                        loading={reviewingApprovalRequest === 'reject'}
                        disabled={Boolean(reviewingApprovalRequest)}
                        onClick={() => handleReviewApprovalRequest(false)}
                        className="h-7 rounded-lg text-[11px] font-black"
                      >
                        拒绝请求
                      </Button>
                    </div>
                  )}
                </div>
                <div className="mt-2 rounded-lg border border-slate-100 bg-white px-2 py-2 text-[11px] text-slate-600">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-black text-slate-700">审批审计</span>
                    <Tag color={latestApprovalAudit ? 'processing' : 'default'} className="m-0 rounded-full text-[10px] font-bold">
                      {latestApprovalAudit?.status || '暂无'}
                    </Tag>
                  </div>
                  <div className="mt-1 break-all font-mono text-slate-500">
                    {latestApprovalAudit?.modelId || '-'}
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate">原因：{latestApprovalAudit?.reason || '-'}</span>
                    <span>{latestApprovalAudit?.idempotent ? '幂等重放' : latestApprovalAudit ? '新审批' : '-'}</span>
                  </div>
                </div>
                {shouldAutoRefresh && (
                  <div className="mt-1 text-[11px] text-blue-500">活动任务每 5 秒自动刷新</div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Radio className="h-4 w-4 text-blue-500" />
                <Text className="text-sm font-black text-slate-800">Shadow Signal 状态</Text>
              </div>
              <Tag color={latestSignalRun ? 'processing' : 'default'} className="m-0 rounded-full font-bold">
                {latestSignalRun ? latestSignalRun.status : '未发布'}
              </Tag>
            </div>
            <div className="space-y-2 text-xs font-bold leading-6 text-slate-500">
              <div>Signal Run：<span className="font-mono text-slate-700">{latestSignalRun?.id || '-'}</span></div>
              <div>信号数量：{latestSignalRun?.signalCount ?? 0}</div>
              <div>Redis Stream：{latestSignalRun?.publishStream ? `${latestSignalRun.streamPublishedCount} 条` : '未写入'}</div>
            </div>
          </div>
        </div>
      </div>

      <Modal
        title="因子研究请求契约"
        open={requestContractOpen}
        onCancel={() => setRequestContractOpen(false)}
        footer={null}
        width={720}
        zIndex={10000}
      >
        <pre className="max-h-[60vh] overflow-auto rounded-xl bg-slate-950 p-4 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(requestPreview, null, 2)}
        </pre>
      </Modal>

    </div>
  );
};

export default FactorResearchWorkbench;
