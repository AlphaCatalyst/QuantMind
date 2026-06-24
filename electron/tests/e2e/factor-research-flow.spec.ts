import { expect, test } from '@playwright/test';

const now = '2026-06-24T09:00:00.000Z';

const user = {
  id: 59427183,
  username: 'factor-e2e',
  email: 'factor-e2e@example.com',
  full_name: 'Factor E2E',
  tenant_id: 'default',
  is_active: true,
  is_admin: true,
  created_at: now,
  updated_at: now,
};

const accessToken = [
  Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64'),
  Buffer.from(JSON.stringify({ sub: String(user.id), exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64'),
  'signature',
].join('.');

function emptyListData(limit = 20) {
  return {
    items: [],
    total: 0,
    pagination: {
      limit,
      offset: 0,
      returned: 0,
      hasMore: false,
    },
  };
}

function factorRun(status: 'running' | 'completed') {
  return {
    id: 'run-e2e',
    candidateId: 'candidate-e2e',
    status,
    params: {
      universe: 'hs300',
      holding_period: 5,
    },
    metrics: status === 'completed'
      ? {
          rank_ic_mean: 0.023,
          ic_ir: 0.28,
          turnover_mean: 0.18,
          monotonicity_score: 0.72,
          anti_overfit_score: 78,
          coverage_days: 160,
        }
      : {},
    gateDecision: status === 'completed'
      ? { eligible: true, reasons: [] }
      : { eligible: false, reasons: [] },
    reportUrl: null,
    errorMessage: null,
    startedAt: now,
    completedAt: status === 'completed' ? now : null,
    createdAt: now,
    updatedAt: now,
  };
}

function factorRunValues() {
  return {
    run: factorRun('completed'),
    summary: {
      total: 100,
      tradeDateCount: 40,
      symbolCount: 25,
      minTradeDate: '2026-03-01',
      maxTradeDate: '2026-04-30',
      minFactorValue: -0.42,
      maxFactorValue: 0.73,
      nullValueCount: 0,
      invalidSymbolCount: 0,
      sourceCount: 1,
      invalidSymbolSamples: [],
      sourceDistribution: [{ source: 'local_stock_daily_latest', count: 100 }],
      recentDateDistribution: [{ tradeDate: '2026-04-30', count: 25 }],
    },
    items: [
      {
        candidateId: 'candidate-e2e',
        runId: 'run-e2e',
        tradeDate: '2026-04-30',
        symbol: 'SH600001',
        factorValue: 0.5123,
        source: 'local_stock_daily_latest',
        createdAt: now,
      },
      {
        candidateId: 'candidate-e2e',
        runId: 'run-e2e',
        tradeDate: '2026-04-30',
        symbol: 'SZ000001',
        factorValue: -0.1289,
        source: 'local_stock_daily_latest',
        createdAt: now,
      },
    ],
    pagination: {
      limit: 5,
      offset: 0,
      returned: 2,
      hasMore: true,
    },
  };
}

function factorBackfillJob(status: 'pending' | 'completed' = 'completed') {
  return {
    id: 'backfill-job-e2e',
    tenantId: 'default',
    userId: String(user.id),
    status,
    target: {
      runIds: ['run-e2e'],
      candidateIds: [],
      promotionIds: [],
    },
    params: {
      dryRun: true,
      maxRuns: 1,
    },
    result: status === 'completed'
      ? {
          status: 'planned',
          resolvedRuns: 1,
          processedRuns: 0,
        }
      : null,
    errorMessage: null,
    workerId: status === 'completed' ? `api:${user.id}` : null,
    startedAt: status === 'completed' ? now : null,
    completedAt: status === 'completed' ? now : null,
    createdAt: now,
    updatedAt: now,
  };
}

function factorCandidate(runStatus: 'running' | 'completed') {
  return {
    id: 'candidate-e2e',
    name: '价格均值偏离',
    expression: 'rank(close / ts_mean(close, 20))',
    expressionHash: 'hash-e2e',
    description: null,
    source: 'template',
    family: 'momentum',
    status: runStatus === 'completed' ? 'validated' : 'evaluating',
    tags: ['momentum'],
    metadata: {
      pipeline_stage: 'pre_training_factor_research',
      submitted_from: 'factor_research_workbench',
    },
    latestRun: factorRun(runStatus),
    createdAt: now,
    updatedAt: now,
  };
}

function factorPromotion(status: 'materialized' | 'pending_materialization' = 'materialized') {
  return {
    id: 'promotion-e2e',
    candidateId: 'candidate-e2e',
    runId: 'run-e2e',
    featureKey: 'factor_alpha',
    featureId: 'factor_alpha',
    versionId: 'feature-set-e2e',
    status,
    materializationStatus: status,
    metadata: {
      materialization: {
        reason: status === 'materialized'
          ? 'feature_values_materialized_to_snapshots'
          : 'feature_snapshot_column_missing',
      },
    },
    createdAt: now,
    updatedAt: now,
  };
}

function factorTrainingRun(approved = false) {
  return {
    id: 'factor-training-e2e',
    promotionId: 'promotion-e2e',
    candidateId: 'candidate-e2e',
    factorRunId: 'run-e2e',
    trainingRunId: 'train-e2e',
    status: 'completed',
    trainingStatus: 'completed',
    trainingProgress: 100,
    trainingResult: {
      metrics: {
        test: { auc: 0.58, rmse: 0.18 },
      },
      model_registration: {
        model_id: 'model_train_e2e',
        status: 'ready',
      },
    },
    trainingComparison: {
      status: 'improved',
      summary: 'Promoted 模型优于 baseline',
      baselineRunId: 'baseline-train-e2e',
      gate: {
        decision: 'approve_model_candidate',
        summary: 'Promoted 模型优于 baseline，可进入模型注册/默认模型审批。',
      },
    },
    trainingGate: {
      decision: 'approve_model_candidate',
      allowDefaultModelPromotion: true,
      summary: 'Promoted 模型优于 baseline，可进入模型注册/默认模型审批。',
    },
    featureKey: 'factor_alpha',
    featureSetVersionId: 'feature-set-e2e',
    requestPayload: {
      factor_research: {
        feature_key: 'factor_alpha',
        baseline_training_run_id: 'baseline-train-e2e',
      },
    },
    response: { runId: 'train-e2e', status: 'completed' },
    metadata: approved
      ? {
        auto_baseline_training_run_id: 'baseline-train-e2e',
        approval: {
          default_model_set: true,
          model_id: 'model_train_e2e',
        },
      }
      : { auto_baseline_training_run_id: 'baseline-train-e2e' },
    createdAt: now,
    updatedAt: now,
  };
}

function factorApprovalAudit() {
  return {
    id: 'approval-audit-e2e',
    tenantId: 'default',
    userId: String(user.id),
    trainingId: 'factor-training-e2e',
    factorRunId: 'run-e2e',
    promotionId: 'promotion-e2e',
    candidateId: 'candidate-e2e',
    modelId: 'model_train_e2e',
    action: 'approve_default_model',
    status: 'approved',
    reason: 'factor_research_gate_approved',
    idempotent: false,
    requestMetadata: { submitted_from: 'factor_research_workbench' },
    approval: { model_id: 'model_train_e2e', default_model_set: true },
    defaultModel: { model_id: 'model_train_e2e', is_default: true },
    gate: { decision: 'approve_model_candidate' },
    createdAt: now,
  };
}

function factorApprovalRequest() {
  return {
    id: 'approval-request-e2e',
    tenantId: 'default',
    userId: String(user.id),
    trainingId: 'factor-training-e2e',
    modelId: 'model_train_e2e',
    status: 'pending',
    requestedBy: String(user.id),
    requestReason: 'factor_research_gate_approved',
    requestMetadata: { submitted_from: 'factor_research_workbench' },
    reviewerUserId: null,
    reviewerNote: null,
    decision: {},
    reviewedAt: null,
    createdAt: now,
    updatedAt: now,
  };
}

function factorApprovalPolicy(allowDirectApproval = true) {
  return {
    tenantId: 'default',
    enabled: true,
    allowDirectApproval,
    allowSelfApproval: true,
    minApprovals: 1,
    reviewerPermission: 'factor.approve',
    metadata: {},
    updatedBy: String(user.id),
    createdAt: now,
    updatedAt: now,
  };
}

function factorFeatureCatalog() {
  return {
    version_id: 'factor_shadow_feature_set_e2e',
    version_name: '因子研究 Shadow Feature Set',
    feature_count: 2,
    source: 'database',
    categories: [
      {
        id: 'factor_research',
        name: '因子研究晋升特征',
        order: 1,
        feature_count: 1,
        features: [
          {
            feature_id: 'factor_alpha',
            key: 'factor_alpha',
            feature_name: 'Alpha 价格均值偏离',
            formula: 'rank(close / ts_mean(close, 20))',
            source_table_fields: 'qm_factor_values.factor_value',
            enabled: true,
            order_no: 1,
          },
        ],
      },
      {
        id: 'momentum',
        name: '动量',
        order: 2,
        feature_count: 1,
        features: [
          {
            feature_id: 'mom_ret_5d',
            key: 'mom_ret_5d',
            feature_name: '5日收益率动量',
            formula: 'ret_5d',
            source_table_fields: 'model_features.mom_ret_5d',
            enabled: true,
            order_no: 1,
          },
        ],
      },
    ],
    data_coverage: {
      source: 'feature_snapshots',
      snapshot_dir: 'db/feature_snapshots',
      file_count: 1,
      scanned_files: 1,
      failed_files: 0,
      total_rows: 100,
      min_date: '2026-01-01',
      max_date: '2026-06-24',
      suggested_periods: {
        train: ['2026-01-01', '2026-03-31'],
        val: ['2026-04-01', '2026-05-15'],
        test: ['2026-05-16', '2026-06-24'],
      },
    },
  };
}

function factorRegisteredModel() {
  return {
    tenant_id: 'default',
    user_id: String(user.id),
    model_id: 'model_train_e2e',
    source_run_id: 'train-e2e',
    status: 'ready',
    storage_path: '/tmp/model_train_e2e',
    model_file: 'model.lgb',
    is_default: true,
    created_at: now,
    updated_at: now,
    activated_at: now,
    metrics_json: {
      test_auc: 0.58,
    },
    metadata_json: {
      display_name: '因子研究 Shadow 训练 - factor_alpha',
      model_name: '因子研究 Shadow 训练 - factor_alpha',
      source_pipeline: 'factor_shadow_training',
      promoted_factor_key: 'factor_alpha',
      promoted_factor_expression: 'rank(close / ts_mean(close, 20))',
      feature_set_version_id: 'feature-set-e2e',
      factor_research: {
        promotion_id: 'promotion-e2e',
        candidate_id: 'candidate-e2e',
        factor_run_id: 'run-e2e',
        feature_key: 'factor_alpha',
        feature_set_version_id: 'feature-set-e2e',
        expression: 'rank(close / ts_mean(close, 20))',
        pipeline_stage: 'factor_shadow_training',
        includes_promoted_factor: true,
        baseline_training_run_id: 'baseline-train-e2e',
      },
    },
  };
}

function factorHealth(status: 'healthy' | 'warning' | 'critical' = 'warning') {
  return {
    tenantId: 'default',
    userId: String(user.id),
    windowHours: 24,
    status,
    statusCounts: {
      run: { completed: 1, failed: status === 'healthy' ? 0 : 1 },
      campaign: { running: 1 },
    },
    indicators: {
      recent_failed_runs: status === 'healthy' ? 0 : 1,
      stale_runs: 0,
      pending_materializations: status === 'healthy' ? 0 : 2,
      active_campaigns: 1,
      worker_recent_events: status === 'healthy' ? 0 : 4,
      worker_recent_failures: 0,
      pending_approval_requests: 0,
      shadow_stream_published: 0,
    },
    slo: {
      status: status === 'healthy' ? 'met' : 'breached',
      metrics: {
        runSuccessRate: status === 'healthy' ? 1 : 0.75,
        campaignSuccessRate: status === 'healthy' ? 1 : 0.5,
        campaignP95DurationSeconds: status === 'healthy' ? 120 : 1200,
        pendingCampaigns: 1,
        staleRunningCampaigns: 0,
        backfillFailedJobs: status === 'healthy' ? 0 : 1,
      },
      objectives: {
        runSuccessRate: 0.9,
        campaignSuccessRate: 0.9,
        campaignP95DurationSeconds: 900,
      },
      breaches: status === 'healthy' ? [] : ['run_success_rate', 'backfill_failed_jobs'],
      windowHours: 24,
    },
    quotaPolicy: {
      max_candidates_per_campaign: 20,
      max_active_campaigns_per_user: 1,
      daily_candidate_budget: 100,
    },
    alerts: status === 'healthy'
      ? []
      : [
          {
            level: 'warning',
            code: 'pending_feature_materializations',
            message: 'pending feature materializations',
            value: 2,
          },
        ],
    generatedAt: now,
  };
}

function factorWorkerEvents() {
  return {
    items: [
      {
        id: 'worker-event-e2e',
        eventType: 'processed',
        campaignId: 'campaign-e2e',
        tenantId: 'default',
        userId: String(user.id),
        status: 'completed',
        details: {
          completedRuns: 2,
          itemCount: 3,
        },
        createdAt: now,
      },
    ],
    total: 1,
    pagination: {
      limit: 5,
      offset: 0,
      returned: 1,
      hasMore: false,
    },
  };
}

function factorCampaign(status: 'running' | 'cancelled' = 'running') {
  return {
    id: 'campaign-e2e',
    name: '自动因子挖掘',
    strategy: 'template_mutation',
    status,
    seedExpression: 'rank(close / ts_mean(close, 20))',
    params: { n_candidates: 5 },
    summary: status === 'cancelled'
      ? {
          totalCandidates: 5,
          completedRuns: 0,
          bestExpression: null,
          cancelled: true,
          cancelReason: 'factor_research_workbench_cancel',
        }
      : {
          totalCandidates: 5,
          completedRuns: 1,
          bestCandidateId: 'candidate-campaign-1',
          bestRunId: 'run-campaign-1',
          bestExpression: 'rank(close / ts_mean(close, 20))',
          bestScore: 0.0234,
          maxGenerations: 2,
          completedGenerations: 2,
          generationStats: [
            {
              generation: 1,
              totalCandidates: 2,
              completedRuns: 1,
              failedRuns: 1,
              bestExpression: 'rank(close / ts_mean(close, 20))',
              bestScore: 0.0234,
            },
            {
              generation: 2,
              totalCandidates: 1,
              completedRuns: 1,
              failedRuns: 0,
              bestExpression: 'rank(close / ts_mean(close, 40))',
              bestScore: 0.0312,
            },
          ],
          operatorStats: [
            { operator: 'mutation', totalCandidates: 1, completedRuns: 1, bestScore: 0.0312 },
            { operator: 'seed', totalCandidates: 1, completedRuns: 1, bestScore: 0.0234 },
          ],
          reasonStats: [
            { reason: 'local window/operator mutation', count: 1 },
            { reason: 'seed expression', count: 1 },
          ],
          lineageEdges: [
            {
              fromExpression: 'rank(close / ts_mean(close, 20))',
              toExpression: 'rank(close / ts_mean(close, 40))',
              operator: 'mutation',
              generation: 2,
              score: 0.0312,
            },
          ],
        },
    metadata: {},
    items: [
      {
        campaignId: 'campaign-e2e',
        candidateId: 'candidate-campaign-1',
        runId: 'run-campaign-1',
        generation: 1,
        rankNo: 1,
        expression: 'rank(close / ts_mean(close, 20))',
        status: 'completed',
        score: 0.0234,
        reason: 'eligible',
        metrics: { rank_ic_mean: 0.0234 },
        metadata: {
          operator: 'seed',
          parentExpressions: [],
          evolutionReason: 'seed expression',
        },
        createdAt: now,
        updatedAt: now,
      },
      {
        campaignId: 'campaign-e2e',
        candidateId: 'candidate-campaign-2',
        runId: 'run-campaign-2',
        generation: 2,
        rankNo: 2,
        expression: 'rank(close / ts_mean(close, 40))',
        status: 'completed',
        score: 0.0312,
        reason: 'eligible',
        metrics: { rank_ic_mean: 0.0312 },
        metadata: {
          operator: 'mutation',
          parentExpressions: ['rank(close / ts_mean(close, 20))'],
          evolutionReason: 'local window/operator mutation',
        },
        createdAt: now,
        updatedAt: now,
      },
    ],
    startedAt: now,
    completedAt: status === 'cancelled' ? now : null,
    createdAt: now,
    updatedAt: now,
  };
}

function factorArchivedCampaign() {
  return {
    id: 'campaign-history',
    name: '上一轮因子挖掘',
    strategy: 'template_mutation',
    status: 'completed',
    seedExpression: 'rank(ts_delta(close, 5) / ts_shift(close, 5))',
    params: { n_candidates: 3 },
    summary: {
      totalCandidates: 3,
      completedRuns: 3,
      bestCandidateId: 'candidate-history-1',
      bestRunId: 'run-history-1',
      bestExpression: 'rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))',
      bestScore: 0.0412,
      maxGenerations: 3,
      completedGenerations: 3,
      generationStats: [
        {
          generation: 1,
          totalCandidates: 1,
          completedRuns: 1,
          failedRuns: 0,
          bestExpression: 'rank(ts_delta(close, 5) / ts_shift(close, 5))',
          bestScore: 0.0199,
        },
        {
          generation: 2,
          totalCandidates: 1,
          completedRuns: 1,
          failedRuns: 0,
          bestExpression: 'rank(close / ts_mean(close, 40))',
          bestScore: 0.0288,
        },
        {
          generation: 3,
          totalCandidates: 1,
          completedRuns: 1,
          failedRuns: 0,
          bestExpression: 'rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))',
          bestScore: 0.0412,
        },
      ],
    },
    metadata: {},
    items: [
      {
        campaignId: 'campaign-history',
        candidateId: 'candidate-history-1',
        runId: 'run-history-1',
        generation: 3,
        rankNo: 3,
        expression: 'rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))',
        status: 'completed',
        score: 0.0412,
        reason: 'eligible',
        metrics: { rank_ic_mean: 0.0412, ic_ir: 0.37, turnover_mean: 0.18 },
        createdAt: now,
        updatedAt: now,
      },
    ],
    startedAt: now,
    completedAt: now,
    createdAt: now,
    updatedAt: now,
  };
}

test('factor research creates an evaluation task and polls it to completion', async ({ page }) => {
  let candidateCreated = false;
  let evaluationCreated = false;
  let backfillPayload: Record<string, unknown> | null = null;
  let backfillRan = false;
  let candidateReadsAfterSubmit = 0;
  const requestedPaths: string[] = [];

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    requestedPaths.push(`${request.method()} ${path}`);

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/candidates') && request.method() === 'GET') {
      let items: unknown[] = [];
      if (evaluationCreated) {
        candidateReadsAfterSubmit += 1;
        items = [
          factorCandidate(candidateReadsAfterSubmit >= 2 ? 'completed' : 'running'),
        ];
      } else if (candidateCreated) {
        items = [factorCandidate('running')];
      }
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: {
              limit: 20,
              offset: 0,
              returned: items.length,
              hasMore: false,
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/health')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { health: factorHealth('warning') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaign-worker-events')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: factorWorkerEvents(),
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/value-backfills') && request.method() === 'GET') {
      const items = backfillRan ? [factorBackfillJob('completed')] : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: {
              limit: 5,
              offset: 0,
              returned: items.length,
              hasMore: false,
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/value-backfills') && request.method() === 'POST') {
      backfillPayload = await request.postDataJSON();
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { job: factorBackfillJob('pending') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/value-backfills/backfill-job-e2e/run')) {
      backfillRan = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { job: factorBackfillJob('completed') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/runs/run-e2e/values')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: factorRunValues(),
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/candidates') && request.method() === 'POST') {
      candidateCreated = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { candidate: factorCandidate('running') },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/candidates/candidate-e2e/evaluate')
      && request.method() === 'POST'
    ) {
      evaluationCreated = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { run: factorRun('running') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/trainings')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');

  await expect(page.getByRole('heading', { name: '因子研究', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '因子研究是模型训练的前置流水线' })).toBeVisible();
  await expect(page.getByText('因子研究工作台')).toBeVisible();
  await expect(page.getByText('运行健康')).toBeVisible();
  await expect(page.getByText('存在待物化特征')).toBeVisible();
  await expect(page.getByText('待物化', { exact: true })).toBeVisible();
  await expect(page.getByText('Worker 事件')).toBeVisible();
  const sloPanel = page.getByTestId('factor-research-slo-panel');
  await expect(sloPanel.getByText('SLO')).toBeVisible();
  await expect(sloPanel.getByText('需关注')).toBeVisible();
  await expect(sloPanel.getByText('Run 成功率 75.0%')).toBeVisible();
  await expect(sloPanel.getByText('Backfill 失败 1')).toBeVisible();
  await expect(page.getByText('Worker 最近事件')).toBeVisible();
  await expect(page.getByText('已处理')).toBeVisible();

  await page.getByRole('button', { name: /提交评估/ }).click();

  await expect(page.getByText('运行中').first()).toBeVisible();
  await expect(page.getByText('最新候选：价格均值偏离')).toBeVisible();

  await expect.poll(() => candidateReadsAfterSubmit, { timeout: 7000 }).toBeGreaterThanOrEqual(2);
  await expect(page.getByText('已完成').first()).toBeVisible();
  await expect(page.getByText('满足晋升门禁')).toBeVisible();
  await expect(page.getByText('Factor Values 预览')).toBeVisible();
  await expect(page.getByText('100 条')).toBeVisible();
  await expect(page.getByText('空值 0')).toBeVisible();
  await expect(page.getByText('异常代码 0')).toBeVisible();
  await expect(page.getByText('来源：local_stock_daily_latest:100')).toBeVisible();
  await expect(page.getByText('SH600001')).toBeVisible();
  await expect(page.getByText('0.5123')).toBeVisible();
  await expect(page.getByText('因子值回填')).toBeVisible();
  await page.getByRole('button', { name: /回填最新 Run/ }).click();
  await expect.poll(() => backfillPayload, { timeout: 5000 }).not.toBeNull();
  expect(backfillPayload).toMatchObject({
    run_ids: ['run-e2e'],
    dry_run: true,
    metadata: {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'factor_value_backfill',
    },
  });
  await expect.poll(() => backfillRan, { timeout: 5000 }).toBe(true);
  expect(requestedPaths).toContain('POST /api/v1/research/factors/candidates');
  expect(requestedPaths).toContain('POST /api/v1/research/factors/candidates/candidate-e2e/evaluate');
  expect(requestedPaths).toContain('POST /api/v1/research/factors/value-backfills');
  expect(requestedPaths).toContain('POST /api/v1/research/factors/value-backfills/backfill-job-e2e/run');
  expect(requestedPaths).toContain('GET /api/v1/research/factors/runs/run-e2e/values');
  expect(requestedPaths).toContain('GET /api/v1/research/factors/health');
  expect(requestedPaths).toContain('GET /api/v1/research/factors/campaign-worker-events');
});

test('factor research starts bounded campaign and shows generation summary', async ({ page }) => {
  let campaignStarted = false;
  let campaignPayload: Record<string, unknown> | null = null;
  const requestedPaths: string[] = [];

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    requestedPaths.push(`${request.method()} ${path}`);

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/campaigns/campaign-e2e')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { campaign: factorCampaign('running') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns/campaign-history')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { campaign: factorArchivedCampaign() },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns') && request.method() === 'POST') {
      campaignStarted = true;
      campaignPayload = await request.postDataJSON();
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { campaign: factorCampaign('running') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      const items = campaignStarted
        ? [factorCampaign('running'), factorArchivedCampaign()]
        : [factorArchivedCampaign()];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: {
              limit: 10,
              offset: 0,
              returned: items.length,
              hasMore: false,
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/health')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { health: factorHealth('healthy') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/trainings')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');
  await expect(page.getByText('Campaign 状态')).toBeVisible();
  await expect(page.getByText('最近 24 小时无运行告警')).toBeVisible();

  await expect(page.getByText('"strategy": "mutation_crossover"')).toBeVisible();
  await expect(page.getByText('因子进化')).toBeVisible();
  await expect(page.getByText('因子交叉')).toBeVisible();
  await page.getByText('因子进化').click();
  await expect(page.getByText('"strategy": "quantgpt_meta_evolution"')).toBeVisible();
  await page.getByText('仅突变').click();
  await expect(page.getByText('"strategy": "template_mutation"')).toBeVisible();
  await page.getByLabel('Campaign 代数').fill('2');
  await expect(page.getByText('"max_generations": 2')).toBeVisible();
  await page.getByRole('button', { name: /启动 Campaign/ }).click();

  await expect.poll(() => campaignPayload, { timeout: 5000 }).not.toBeNull();
  expect(campaignPayload).toMatchObject({
    strategy: 'template_mutation',
    n_candidates: 5,
    max_generations: 2,
    run_async: true,
    neutralize_industry: true,
    neutralize_cap: true,
    metadata: {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'factor_campaign',
      max_generations: 2,
    },
  });
  expect(requestedPaths).toContain('POST /api/v1/research/factors/campaigns');

  await expect(page.getByText('代际进度：2/2')).toBeVisible();
  await expect.poll(
    () => requestedPaths.includes('GET /api/v1/research/factors/campaigns/campaign-e2e'),
    { timeout: 5000 },
  ).toBeTruthy();
  await expect(page.getByText('G1', { exact: true })).toBeVisible();
  await expect(page.getByText('G2', { exact: true })).toBeVisible();
  await expect(page.getByText('G2.2')).toBeVisible();
  await expect(page.getByText('rank(close / ts_mean(close, 40))').first()).toBeVisible();
  await expect(page.getByText('进化摘要')).toBeVisible();
  await expect(page.getByText('lineage edges: 1')).toBeVisible();
  await expect(page.getByText('算子 mutation')).toBeVisible();
  await expect(page.getByText(/parents: rank\(close \/ ts_mean\(close, 20\)\)/)).toBeVisible();
  await expect(page.getByText('进化理由：local window/operator mutation')).toBeVisible();
  await expect(page.getByText('Campaign 历史')).toBeVisible();
  await expect(page.getByRole('button', { name: /上一轮因子挖掘/ })).toBeVisible();
  await page.getByRole('button', { name: /上一轮因子挖掘/ }).click();
  await expect(page.getByText('当前 Campaign：上一轮因子挖掘')).toBeVisible();
  await expect(page.getByText('代际进度：3/3')).toBeVisible();
  await expect(page.getByText('G3', { exact: true })).toBeVisible();
  await expect(page.getByText('G3.3')).toBeVisible();
  await expect(page.getByText('0.0412').first()).toBeVisible();
  await expect(page.getByText('run: run-history-1')).toBeVisible();
  await expect(page.getByText('candidate: candidate-history-1')).toBeVisible();
  await expect(page.getByText('RankIC 0.0412 · ICIR 0.37 · Turnover 0.18')).toBeVisible();
  await expect(page.getByText('原因：eligible')).toBeVisible();
  await expect(page.getByText('rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))').first()).toBeVisible();
  expect(requestedPaths).toContain('GET /api/v1/research/factors/campaigns/campaign-history');
});

test('factor research cancels active campaign from workbench', async ({ page }) => {
  let campaignCancelled = false;
  let campaignPromotePayload: Record<string, unknown> | null = null;
  const requestedPaths: string[] = [];

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    requestedPaths.push(`${request.method()} ${path}`);

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/candidates/candidate-campaign-1/promote')) {
      campaignPromotePayload = await request.postDataJSON();
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { promotion: factorPromotion('pending_materialization') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns/campaign-e2e/cancel')) {
      campaignCancelled = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { campaign: factorCampaign('cancelled') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns/campaign-e2e')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { campaign: factorCampaign(campaignCancelled ? 'cancelled' : 'running') },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      const campaign = factorCampaign(campaignCancelled ? 'cancelled' : 'running');
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [campaign],
            total: 1,
            pagination: { limit: 10, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/trainings')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(5) } });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(5) } });
      return;
    }

    if (path.endsWith('/research/factors/health')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { health: factorHealth('warning') },
        },
      });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');
  await expect(page.getByText('Campaign 状态')).toBeVisible();
  await expect(page.getByText('自动刷新中')).toBeVisible();
  await expect(page.getByText('候选历史')).toBeVisible();
  await expect(page.getByText('代际进度：2/2')).toBeVisible();
  await expect(page.getByText('G1.1')).toBeVisible();
  await expect(page.getByText('G2.2')).toBeVisible();
  await expect(page.getByText('0.0234').first()).toBeVisible();
  await expect(page.getByText('0.0312').first()).toBeVisible();
  await expect(page.getByText('rank(close / ts_mean(close, 40))').first()).toBeVisible();
  expect(requestedPaths).toContain('GET /api/v1/research/factors/campaigns/campaign-e2e');

  await page.getByRole('button', { name: /晋升最佳候选/ }).click();
  await expect.poll(() => campaignPromotePayload, { timeout: 5000 }).not.toBeNull();
  expect(campaignPromotePayload).toMatchObject({
    run_id: 'run-campaign-1',
    force_shadow: true,
    metadata: {
      source: 'campaign_best_candidate',
      campaign_id: 'campaign-e2e',
    },
  });
  expect(requestedPaths).toContain('POST /api/v1/research/factors/candidates/candidate-campaign-1/promote');

  await page.getByRole('button', { name: /取消 Campaign/ }).click();

  await expect(page.getByText('factor_research_workbench_cancel')).toBeVisible();
  expect(requestedPaths).toContain('POST /api/v1/research/factors/campaigns/campaign-e2e/cancel');
});

test('factor research launches shadow training with auto baseline payload', async ({ page }) => {
  let launchPayload: Record<string, unknown> | null = null;
  let approvalPayload: Record<string, unknown> | null = null;
  let trainingSubmitted = false;
  let trainingApproved = false;

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorCandidate('completed')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorPromotion('materialized')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/trainings') && request.method() === 'GET') {
      const items = trainingSubmitted ? [factorTrainingRun(trainingApproved)] : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/trainings/factor-training-e2e/approve')
      && request.method() === 'POST'
    ) {
      approvalPayload = request.postDataJSON();
      trainingApproved = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            training: factorTrainingRun(true),
            approval: {
              status: 'approved',
              model_id: 'model_train_e2e',
              default_model_set: true,
            },
            defaultModel: { model_id: 'model_train_e2e', is_default: true },
          },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/promotions/promotion-e2e/train')
      && request.method() === 'POST'
    ) {
      launchPayload = request.postDataJSON();
      trainingSubmitted = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { training: factorTrainingRun() },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      const items = trainingApproved ? [factorApprovalAudit()] : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      const items = trainingSubmitted && !trainingApproved ? [factorApprovalRequest()] : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/models/feature-catalog')) {
      await route.fulfill({ json: factorFeatureCatalog() });
      return;
    }

    if (path.endsWith('/models/model_train_e2e/shap-summary')) {
      await route.fulfill({
        json: {
          model_id: 'model_train_e2e',
          status: 'completed',
          split: 'valid',
          rows_requested: 30000,
          rows_used: 1200,
          file: 'shap_summary.csv',
          file_exists: true,
          total: 1,
          items: [
            {
              rank: 1,
              feature: 'factor_alpha',
              mean_abs_shap: 0.42,
              mean_shap: 0.12,
              positive_ratio: 0.67,
            },
          ],
        },
      });
      return;
    }

    if (path.endsWith('/models') && request.method() === 'GET') {
      await route.fulfill({ json: { items: [factorRegisteredModel()], total: 1 } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');

  await expect(page.getByText('Feature 晋升状态')).toBeVisible();
  await expect(page.getByText('Feature Key：')).toBeVisible();
  await expect(page.getByText('factor_alpha').first()).toBeVisible();

  await page.getByRole('button', { name: /发起 Shadow 训练/ }).click();

  await expect.poll(() => launchPayload, { timeout: 5000 }).not.toBeNull();
  expect(launchPayload).toMatchObject({
    display_name: '因子研究 Shadow 训练 - factor_alpha',
    baseline_display_name: '因子研究 Baseline 训练 - factor_alpha',
    auto_baseline: true,
    metadata: {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'factor_shadow_training',
    },
  });
  await expect(page.getByText('train-e2e').first()).toBeVisible();
  await expect(page.getByText('待审批晋升').first()).toBeVisible();
  await expect(page.getByText('审批请求', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /审批为默认模型/ }).click();
  await expect.poll(() => approvalPayload, { timeout: 5000 }).not.toBeNull();
  expect(approvalPayload).toMatchObject({
    set_default_model: true,
    reason: 'factor_research_gate_approved',
  });
  await expect(page.getByText('已设为默认模型：model_train_e2e')).toBeVisible();
  await expect(page.getByText('审批审计')).toBeVisible();
  await expect(page.getByText('model_train_e2e').last()).toBeVisible();
  await expect(page.getByText('前往模型管理生成生产批次')).toBeVisible();

  await page.goto('/#/model-training');
  await expect(page.getByText('上游：因子研究')).toBeVisible();
  await expect(page.getByText('因子研究晋升特征')).toBeVisible();
  await page.getByRole('button', { name: /因子研究晋升特征/ }).click();
  await expect(page.getByText('Alpha 价格均值偏离')).toBeVisible();

  await page.goto('/#/model-registry');
  await expect(page.getByText('因子研究 Shadow 训练 - factor_alpha').first()).toBeVisible();
  await page.getByRole('tab', { name: /归因分析/ }).click();
  await expect(page.getByText('因子研究来源')).toBeVisible();
  await expect(page.getByText('factor_shadow_training')).toBeVisible();
  await expect(page.getByText('factor_alpha').first()).toBeVisible();
  await expect(page.getByText('baseline-train-e2e')).toBeVisible();
});

test('factor research approval policy disables direct approval and enables request flow', async ({ page }) => {
  let approvalPolicy = factorApprovalPolicy(true);
  let policyPayload: Record<string, unknown> | null = null;

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/approval-policy')) {
      if (request.method() === 'PUT') {
        policyPayload = request.postDataJSON();
        approvalPolicy = {
          ...approvalPolicy,
          allowDirectApproval: Boolean(policyPayload?.allow_direct_approval),
          allowSelfApproval: Boolean(policyPayload?.allow_self_approval),
          minApprovals: Number(policyPayload?.min_approvals || 1),
          metadata: policyPayload?.metadata as Record<string, unknown>,
        };
      }
      await route.fulfill({ json: { code: 0, message: 'ok', data: { policy: approvalPolicy } } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorCandidate('completed')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorPromotion('materialized')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/trainings')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorTrainingRun(false)],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');

  await expect(page.getByText('默认模型审批策略')).toBeVisible();
  await expect(page.getByRole('button', { name: /审批为默认模型/ })).toBeEnabled();
  await expect(page.getByRole('button', { name: /提交审批请求/ })).toBeDisabled();

  await page.getByRole('switch').first().click();
  await page.getByRole('button', { name: /保存策略/ }).click();

  await expect.poll(() => policyPayload, { timeout: 5000 }).not.toBeNull();
  expect(policyPayload).toMatchObject({
    allow_direct_approval: false,
    allow_self_approval: true,
    min_approvals: 1,
    reviewer_permission: 'factor.approve',
  });
  await expect(page.getByText('需走审批请求')).toBeVisible();
  await expect(page.getByRole('button', { name: /审批为默认模型/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /提交审批请求/ })).toBeEnabled();
});

test('factor research lets admins review pending approval requests', async ({ page }) => {
  let reviewPayload: Record<string, unknown> | null = null;
  let requestReviewed = false;

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: user });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: user } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorCandidate('completed')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorPromotion('materialized')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/trainings') && request.method() === 'GET') {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorTrainingRun(requestReviewed)],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/approval-requests/approval-request-e2e/review')
      && request.method() === 'POST'
    ) {
      reviewPayload = request.postDataJSON();
      requestReviewed = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            request: {
              ...factorApprovalRequest(),
              status: 'approved',
              reviewerUserId: String(user.id),
              reviewerNote: 'approved_from_factor_research_workbench',
            },
            approvalResult: {
              approval: { model_id: 'model_train_e2e', approved_by: String(user.id) },
              defaultModel: { model_id: 'model_train_e2e', is_default: true },
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      const items = requestReviewed ? [] : [factorApprovalRequest()];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      const items = requestReviewed ? [factorApprovalAudit()] : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');
  await expect(page.getByText('审批请求', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /通过请求/ }).click();

  await expect.poll(() => reviewPayload, { timeout: 5000 }).not.toBeNull();
  expect(reviewPayload).toMatchObject({
    approve: true,
    decision: 'approve',
    reason: 'factor_research_admin_review',
    metadata: {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'factor_model_approval_review',
    },
  });
  await expect(page.getByText('审批审计')).toBeVisible();
  await expect(page.getByText('已设为默认模型：model_train_e2e')).toBeVisible();
});

test('factor research lets permissioned reviewers approve pending requests', async ({ page }) => {
  const reviewerUser = {
    ...user,
    id: 78124590,
    username: 'factor-reviewer-e2e',
    email: 'factor-reviewer-e2e@example.com',
    is_admin: false,
  };
  let reviewPayload: Record<string, unknown> | null = null;

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: reviewerUser });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: reviewerUser } });
      return;
    }

    if (path.endsWith('/rbac/check-permission')) {
      expect(url.searchParams.get('permission_code')).toBe('factor.approve');
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: { has_permission: true, permission_code: 'factor.approve' },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorCandidate('completed')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorPromotion('materialized')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/trainings') && request.method() === 'GET') {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorTrainingRun(false)],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/approval-requests/approval-request-e2e/review')
      && request.method() === 'POST'
    ) {
      reviewPayload = request.postDataJSON();
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            request: {
              ...factorApprovalRequest(),
              status: 'approved',
              reviewerUserId: String(reviewerUser.id),
            },
            approvalResult: {
              approval: { model_id: 'model_train_e2e', approved_by: String(reviewerUser.id) },
              defaultModel: { model_id: 'model_train_e2e', is_default: true },
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorApprovalRequest()],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');
  await expect(page.getByRole('button', { name: /提交审批请求/ })).toBeDisabled();
  await page.getByRole('button', { name: /通过请求/ }).click();

  await expect.poll(() => reviewPayload, { timeout: 5000 }).not.toBeNull();
  expect(reviewPayload).toMatchObject({
    approve: true,
    decision: 'approve',
    reason: 'factor_research_admin_review',
  });
});

test('factor research lets regular users submit approval requests', async ({ page }) => {
  const regularUser = {
    ...user,
    id: 90545323,
    username: 'factor-user-e2e',
    email: 'factor-user-e2e@example.com',
    is_admin: false,
  };
  let requestPayload: Record<string, unknown> | null = null;
  let requestSubmitted = false;

  await page.addInitScript(({ token, storedUser }) => {
    window.localStorage.setItem('access_token', token);
    window.localStorage.setItem('refresh_token', '');
    window.localStorage.setItem('tenant_id', 'default');
    window.localStorage.setItem('user', JSON.stringify(storedUser));
  }, { token: accessToken, storedUser: regularUser });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith('/users/me')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: regularUser } });
      return;
    }

    if (path.endsWith('/research/factors/candidates')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorCandidate('completed')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/promotions')) {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorPromotion('materialized')],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/trainings') && request.method() === 'GET') {
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items: [factorTrainingRun(false)],
            total: 1,
            pagination: { limit: 20, offset: 0, returned: 1, hasMore: false },
          },
        },
      });
      return;
    }

    if (
      path.endsWith('/research/factors/trainings/factor-training-e2e/approval-requests')
      && request.method() === 'POST'
    ) {
      requestPayload = request.postDataJSON();
      requestSubmitted = true;
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            request: {
              ...factorApprovalRequest(),
              userId: String(regularUser.id),
              requestedBy: String(regularUser.id),
            },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approval-requests')) {
      const items = requestSubmitted
        ? [{
            ...factorApprovalRequest(),
            userId: String(regularUser.id),
            requestedBy: String(regularUser.id),
          }]
        : [];
      await route.fulfill({
        json: {
          code: 0,
          message: 'ok',
          data: {
            items,
            total: items.length,
            pagination: { limit: 20, offset: 0, returned: items.length, hasMore: false },
          },
        },
      });
      return;
    }

    if (path.endsWith('/research/factors/approvals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    if (path.endsWith('/research/factors/campaigns')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(10) } });
      return;
    }

    if (path.endsWith('/research/factors/signals')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: emptyListData(20) } });
      return;
    }

    await route.fulfill({ json: { code: 0, message: 'ok', data: {} } });
  });

  await page.goto('/#/factor-research');
  await expect(page.getByRole('button', { name: /审批为默认模型/ })).toBeDisabled();
  await page.getByRole('button', { name: /提交审批请求/ }).click();

  await expect.poll(() => requestPayload, { timeout: 5000 }).not.toBeNull();
  expect(requestPayload).toMatchObject({
    reason: 'factor_research_gate_approved',
    metadata: {
      submitted_from: 'factor_research_workbench',
      pipeline_stage: 'factor_model_approval_request',
    },
  });
  await expect(page.getByText('审批请求', { exact: true })).toBeVisible();
  await expect(page.getByText('model_train_e2e')).toBeVisible();
});
