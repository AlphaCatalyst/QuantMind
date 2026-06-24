from contextlib import asynccontextmanager
from datetime import date, datetime
import json
import sys
import types

import pytest

from backend.services.api.routers import research_factor_market_data as market_adapter
from backend.services.api.routers import research_factor_service as svc
from backend.services.engine.research import factor_campaign_service as campaign_svc
from backend.services.engine.research import factor_value_store


async def _default_policy(tenant_id: str) -> dict:
    return svc._default_factor_approval_policy(tenant_id)


def test_factor_expression_hash_normalizes_whitespace():
    assert svc.factor_expression_hash(" rank(close) ") == svc.factor_expression_hash(
        "rank(close)"
    )
    assert svc.factor_expression_hash("rank( close )") != svc.factor_expression_hash(
        "rank(close)"
    )


@pytest.mark.asyncio
async def test_ensure_research_factor_tables_executes_candidate_and_run_ddl(
    monkeypatch,
):
    executed: list[str] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            executed.append(str(statement))

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    await svc.ensure_research_factor_tables()

    joined = "\n".join(executed)
    assert "CREATE TABLE IF NOT EXISTS qm_factor_candidates" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_candidate_runs" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_values" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_value_backfill_jobs" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_value_backfill_events" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_feature_promotions" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_feature_set_version" in joined
    assert "CREATE TABLE IF NOT EXISTS engine_feature_runs" in joined
    assert "CREATE TABLE IF NOT EXISTS engine_signal_scores" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_signal_runs" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_campaigns" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_campaign_worker_events" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_campaign_items" in joined
    assert "ALTER TABLE qm_factor_campaign_items" in joined
    assert "ADD COLUMN IF NOT EXISTS metadata_json" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_training_runs" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_approval_audit" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_approval_requests" in joined
    assert "CREATE TABLE IF NOT EXISTS qm_factor_approval_policies" in joined
    assert "uq_qm_factor_candidates_scope_expr" in joined


@pytest.mark.asyncio
async def test_create_factor_candidate_normalizes_and_persists(monkeypatch):
    captured: dict = {}

    class FakeMappings:
        def one(self):
            return {
                "id": "candidate-1",
                "tenant_id": "tenant",
                "user_id": "user",
                "expression": "rank(close)",
                "expression_hash": svc.factor_expression_hash("rank(close)"),
                "name": "close rank",
                "description": None,
                "source": "manual",
                "family": "momentum",
                "status": "draft",
                "tags": ["momentum"],
                "metadata_json": {"origin": "test"},
                "created_at": None,
                "updated_at": None,
            }

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.create_factor_candidate(
        "tenant",
        "user",
        {
            "name": "close rank",
            "expression": "  rank(close)  ",
            "source": "manual",
            "family": "momentum",
            "tags": ["momentum"],
            "metadata": {"origin": "test"},
        },
    )

    assert "ON CONFLICT" in captured["sql"]
    assert captured["params"]["expression"] == "rank(close)"
    assert captured["params"]["expression_hash"] == svc.factor_expression_hash(
        "rank(close)"
    )
    assert result["id"] == "candidate-1"
    assert result["status"] == "draft"


@pytest.mark.asyncio
async def test_create_factor_candidate_rejects_empty_expression():
    with pytest.raises(ValueError, match="factor expression is required"):
        await svc.create_factor_candidate("tenant", "user", {"expression": "   "})


def test_factor_raw_value_sql_only_allows_supported_templates():
    assert svc._factor_raw_value_sql("rank(close / ts_mean(close, 20))") is not None
    assert "39 PRECEDING" in svc._factor_raw_value_sql(
        "rank(close / ts_mean(close, 40))"
    )
    assert (
        svc._factor_raw_value_sql("rank(ts_delta(close, 5) / ts_shift(close, 5))")
        is not None
    )
    assert "LAG(close, 10)" in svc._factor_raw_value_sql(
        "rank(ts_delta(close, 10) / ts_shift(close, 10))"
    )
    hybrid_sql = svc._factor_raw_value_sql(
        "rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))"
    )
    assert hybrid_sql is not None
    assert "19 PRECEDING" in hybrid_sql
    assert "LAG(close, 5)" in hybrid_sql
    corr_sql = svc._factor_raw_value_sql("rank(ts_corr(rank(close), rank(volume), 10))")
    assert corr_sql is not None
    assert "CORR(close, volume)" in corr_sql
    assert "9 PRECEDING" in corr_sql
    volume_sql = svc._factor_raw_value_sql("rank(volume / ts_mean(volume, 20))")
    assert volume_sql is not None
    assert "AVG(volume)" in volume_sql
    volatility_sql = svc._factor_raw_value_sql("rank(ts_std(close, 20))")
    assert volatility_sql is not None
    assert "STDDEV_SAMP(close)" in volatility_sql
    tanh_sql = svc._factor_raw_value_sql(
        "rank(tanh(ts_delta(close, 5) / ts_shift(close, 5)))"
    )
    assert tanh_sql is not None
    assert "LAG(close, 5)" in tanh_sql
    amount_sql = svc._factor_raw_value_sql("rank(amount / ts_mean(amount, 20))")
    assert amount_sql is not None
    assert "AVG(amount)" in amount_sql
    vwap_sql = svc._factor_raw_value_sql("rank(vwap / ts_mean(vwap, 20))")
    assert vwap_sql is not None
    assert "AVG(vwap)" in vwap_sql
    ts_rank_sql = svc._factor_raw_value_sql("rank(ts_rank(close, 20))")
    assert ts_rank_sql is not None
    assert "LIMIT 20" in ts_rank_sql
    decay_sql = svc._factor_raw_value_sql("rank(decay_linear(close, 20))")
    assert decay_sql is not None
    assert "ROW_NUMBER()" in decay_sql
    zscore_sql = svc._factor_raw_value_sql("rank(zscore(close, 20))")
    assert zscore_sql is not None
    assert "STDDEV_SAMP(close)" in zscore_sql
    scale_sql = svc._factor_raw_value_sql("rank(scale(volume))")
    assert scale_sql == "volume"
    where_sql = svc._factor_raw_value_sql(
        "rank(where(close > ts_mean(close, 20), close / ts_mean(close, 20), 0))"
    )
    assert where_sql is not None
    assert "CASE WHEN close > AVG(close)" in where_sql
    assert svc._factor_raw_value_sql("rank(close / ts_mean(close, 999))") is None


def test_generate_campaign_expressions_mutates_supported_seed():
    expressions = svc._generate_campaign_expressions(
        {
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "n_candidates": 4,
        }
    )

    assert len(expressions) == 4
    assert expressions[0] == "rank(close / ts_mean(close, 20))"
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_respects_excluded_previous_generation():
    expressions = svc._generate_campaign_expressions(
        {
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "n_candidates": 3,
        },
        exclude_keys={svc.factor_expression_key("rank(close / ts_mean(close, 20))")},
    )

    assert expressions
    assert "rank(close / ts_mean(close, 20))" not in expressions
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_adds_default_crossover_hybrid_candidates():
    expressions = svc._generate_campaign_expressions(
        {
            "seed_expressions": [
                "rank(close / ts_mean(close, 20))",
                "rank(ts_delta(close, 5) / ts_shift(close, 5))",
            ],
            "n_candidates": 3,
        }
    )

    assert (
        "rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))"
        in expressions
    )
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_can_disable_crossover_with_template_strategy():
    expressions = svc._generate_campaign_expressions(
        {
            "strategy": "template_mutation",
            "seed_expressions": [
                "rank(close / ts_mean(close, 20))",
                "rank(ts_delta(close, 5) / ts_shift(close, 5))",
            ],
            "n_candidates": 6,
        }
    )

    assert all("*" not in svc.factor_expression_key(expr) for expr in expressions)
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_supports_quantgpt_meta_evolution_strategy():
    expressions = svc._generate_campaign_expressions(
        {
            "strategy": "quantgpt_meta_evolution",
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "iteration_history": [
                {
                    "expression": "rank(close / ts_mean(close, 20))",
                    "score": 18.0,
                },
                {
                    "expression": "rank(ts_delta(close, 5) / ts_shift(close, 5))",
                    "score": 42.0,
                },
            ],
            "n_candidates": 5,
        }
    )

    assert expressions
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_supports_quantgpt_crossover_only_strategy():
    expressions = svc._generate_campaign_expressions(
        {
            "strategy": "quantgpt_crossover_only",
            "seed_expressions": [
                "rank(close / ts_mean(close, 40))",
                "rank(ts_delta(close, 10) / ts_shift(close, 10))",
            ],
            "n_candidates": 3,
        }
    )

    assert expressions == [
        "rank((close / ts_mean(close, 40)) * (ts_delta(close, 10) / ts_shift(close, 10)))"
    ]
    assert all(svc._factor_raw_value_sql(expr) is not None for expr in expressions)


def test_generate_campaign_expressions_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="unsupported campaign strategy"):
        svc._generate_campaign_expressions(
            {
                "strategy": "external_cloud_search",
                "seed_expression": "rank(close / ts_mean(close, 20))",
                "n_candidates": 3,
            }
        )


def test_campaign_quota_policy_defaults_are_conservative(monkeypatch):
    monkeypatch.delenv("QUANTMIND_FACTOR_CAMPAIGN_MAX_CANDIDATES", raising=False)
    monkeypatch.delenv("QUANTMIND_FACTOR_CAMPAIGN_MAX_ACTIVE_PER_USER", raising=False)
    monkeypatch.delenv(
        "QUANTMIND_FACTOR_CAMPAIGN_DAILY_CANDIDATE_BUDGET", raising=False
    )

    policy = svc._campaign_quota_policy()

    assert policy.max_candidates_per_campaign == 20
    assert policy.max_active_campaigns_per_user == 1
    assert policy.daily_candidate_budget_per_user == 100


def test_validate_campaign_requested_candidates_rejects_above_quota():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=3,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=10,
    )

    with pytest.raises(ValueError, match="candidate quota exceeded"):
        svc._validate_campaign_requested_candidates({"n_candidates": 4}, policy)


def test_validate_campaign_requested_candidates_counts_generations():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=6,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=10,
    )

    assert (
        svc._validate_campaign_requested_candidates(
            {"n_candidates": 3, "max_generations": 2}, policy
        )
        == 6
    )
    with pytest.raises(ValueError, match="candidate quota exceeded"):
        svc._validate_campaign_requested_candidates(
            {"n_candidates": 4, "max_generations": 2}, policy
        )


def test_validate_campaign_requested_candidates_allows_exact_quota_boundary():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    assert (
        svc._validate_campaign_requested_candidates(
            {"n_candidates": 4, "max_generations": 5}, policy
        )
        == 20
    )


@pytest.mark.asyncio
async def test_enforce_factor_campaign_quota_rejects_active_campaign():
    class FakeMappings:
        def first(self):
            return {"active_campaigns": 1, "today_candidates": 0}

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            assert "qm_factor_campaigns" in str(statement)
            return FakeResult()

    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    with pytest.raises(ValueError, match="active quota exceeded"):
        await svc._enforce_factor_campaign_quota(
            FakeSession(),
            tenant_id="tenant",
            user_id="user",
            requested_candidates=5,
            policy=policy,
        )


@pytest.mark.asyncio
async def test_enforce_factor_campaign_quota_rejects_daily_candidate_budget():
    class FakeMappings:
        def first(self):
            return {"active_campaigns": 0, "today_candidates": 98}

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            assert "max_generations" in str(statement)
            return FakeResult()

    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    with pytest.raises(ValueError, match="daily candidate quota exceeded"):
        await svc._enforce_factor_campaign_quota(
            FakeSession(),
            tenant_id="tenant",
            user_id="user",
            requested_candidates=5,
            policy=policy,
        )


@pytest.mark.asyncio
async def test_enforce_factor_campaign_quota_allows_exact_daily_budget_boundary():
    class FakeMappings:
        def first(self):
            return {"active_campaigns": 0, "today_candidates": 80}

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            assert "qm_factor_campaigns" in str(statement)
            assert params == {"tenant_id": "tenant", "user_id": "user"}
            return FakeResult()

    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    usage = await svc._enforce_factor_campaign_quota(
        FakeSession(),
        tenant_id="tenant",
        user_id="user",
        requested_candidates=20,
        policy=policy,
    )

    assert usage == {
        "activeCampaigns": 0,
        "todayCandidates": 80,
        "requestedCandidates": 20,
        "projectedDailyCandidates": 100,
        "policy": {
            "maxCandidatesPerCampaign": 20,
            "maxActiveCampaignsPerUser": 1,
            "dailyCandidateBudgetPerUser": 100,
        },
    }


@pytest.mark.asyncio
async def test_cancel_factor_campaign_marks_active_campaign_cancelled(monkeypatch):
    captured: dict[str, dict] = {}

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def one(self):
            return self.rows[0]

        def all(self):
            return self.rows

    class FakeResult:
        def __init__(self, rows=None):
            self.rows = rows or []

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "FROM qm_factor_campaigns" in sql and "FOR UPDATE" in sql:
                return FakeResult(
                    [
                        {
                            "id": "campaign-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "name": "Campaign",
                            "strategy": "template_mutation",
                            "status": "running",
                            "seed_expression": "rank(close / ts_mean(close, 20))",
                            "params_json": {},
                            "summary_json": {},
                            "metadata_json": {},
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "UPDATE qm_factor_campaigns" in sql:
                captured["campaign_update"] = params
                summary = json.loads(params["summary_json"])
                metadata = json.loads(params["metadata_json"])
                return FakeResult(
                    [
                        {
                            "id": "campaign-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "name": "Campaign",
                            "strategy": "template_mutation",
                            "status": "cancelled",
                            "seed_expression": "rank(close / ts_mean(close, 20))",
                            "params_json": {},
                            "summary_json": summary,
                            "metadata_json": metadata,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "UPDATE qm_factor_campaign_items" in sql:
                captured["item_update"] = params
                return FakeResult()
            if "FROM qm_factor_campaign_items" in sql:
                return FakeResult(
                    [
                        {
                            "campaign_id": "campaign-1",
                            "candidate_id": None,
                            "run_id": None,
                            "generation": 1,
                            "rank_no": 1,
                            "expression": "rank(close / ts_mean(close, 20))",
                            "status": "cancelled",
                            "score": None,
                            "reason": "manual",
                            "metrics_json": {},
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.cancel_factor_campaign(
        "tenant", "user", "campaign-1", reason="manual"
    )

    assert result["status"] == "cancelled"
    assert result["summary"]["cancelled"] is True
    assert result["summary"]["cancelReason"] == "manual"
    assert result["metadata"]["cancellation"]["cancelledBy"] == "user"
    assert result["items"][0]["status"] == "cancelled"
    assert captured["item_update"]["reason"] == "manual"


@pytest.mark.asyncio
async def test_factor_research_health_summarizes_status_and_alerts(monkeypatch):
    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

        def one(self):
            return self.rows[0]

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            assert params["tenant_id"] == "tenant"
            assert params["user_id"] == "user"
            if "UNION ALL" in sql:
                return FakeResult(
                    [
                        {"entity": "run", "status": "completed", "count": 3},
                        {"entity": "run", "status": "failed", "count": 1},
                        {"entity": "campaign", "status": "running", "count": 1},
                    ]
                )
            return FakeResult(
                [
                    {
                        "recent_failed_runs": 1,
                        "stale_runs": 2,
                        "pending_materializations": 1,
                        "active_campaigns": 1,
                        "stale_campaigns": 0,
                        "today_campaign_candidates": 100,
                        "worker_recent_events": 3,
                        "worker_recent_failures": 1,
                        "pending_approval_requests": 0,
                        "shadow_stream_published": 0,
                        "window_run_total": 4,
                        "window_run_completed": 3,
                        "window_campaign_total": 2,
                        "window_campaign_completed": 1,
                        "pending_campaigns": 1,
                        "campaign_p95_duration_seconds": 1200.5,
                        "backfill_failed_jobs": 1,
                    }
                ]
            )

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        assert kwargs.get("read_only") is True
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.get_factor_research_health("tenant", "user", window_hours=999)

    assert result["status"] == "critical"
    assert result["windowHours"] == 168
    assert result["statusCounts"]["run"]["completed"] == 3
    assert result["statusCounts"]["campaign"]["running"] == 1
    assert result["indicators"]["stale_runs"] == 2
    assert result["indicators"]["today_campaign_candidates"] == 100
    assert result["indicators"]["worker_recent_events"] == 3
    assert result["indicators"]["worker_recent_failures"] == 1
    assert result["slo"]["status"] == "breached"
    assert result["slo"]["metrics"]["runSuccessRate"] == 0.75
    assert result["slo"]["metrics"]["campaignSuccessRate"] == 0.5
    assert result["slo"]["metrics"]["campaignP95DurationSeconds"] == 1200.5
    assert set(result["slo"]["breaches"]) >= {
        "run_success_rate",
        "campaign_success_rate",
        "campaign_p95_duration",
        "backfill_failed_jobs",
    }
    assert result["quotaPolicy"]["maxActiveCampaignsPerUser"] == 1
    assert {alert["code"] for alert in result["alerts"]} >= {
        "stale_factor_runs",
        "recent_failed_factor_runs",
        "factor_campaign_worker_failures",
        "campaign_daily_candidate_quota_used",
        "pending_feature_materializations",
    }


def test_factor_research_health_status_is_healthy_without_alerts():
    assert svc._factor_health_status([]) == "healthy"
    assert svc._factor_health_status([{"level": "warning"}]) == "warning"
    assert svc._factor_health_status([{"level": "critical"}]) == "critical"


def test_factor_research_health_alerts_report_daily_campaign_capacity():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    near_limit_alerts = svc._build_factor_health_alerts(
        {"active_campaigns": 0, "today_campaign_candidates": 90},
        quota_policy=policy,
    )
    assert near_limit_alerts == [
        {
            "level": "warning",
            "code": "campaign_daily_candidate_quota_near_limit",
            "message": "Daily factor campaign candidate budget is near limit",
            "value": 90,
            "threshold": 90,
        }
    ]

    used_alerts = svc._build_factor_health_alerts(
        {"active_campaigns": 0, "today_campaign_candidates": 100},
        quota_policy=policy,
    )
    assert used_alerts == [
        {
            "level": "critical",
            "code": "campaign_daily_candidate_quota_used",
            "message": "Daily factor campaign candidate budget is fully used",
            "value": 100,
            "threshold": 100,
        }
    ]


def test_factor_research_health_alerts_report_stale_campaigns():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    alerts = svc._build_factor_health_alerts(
        {"active_campaigns": 0, "stale_campaigns": 2},
        quota_policy=policy,
    )
    assert alerts == [
        {
            "level": "warning",
            "code": "stale_factor_campaigns",
            "message": "Factor campaigns are stale and should be requeued",
            "value": 2,
            "threshold": 0,
        }
    ]


def test_factor_research_health_alerts_report_worker_failures():
    policy = svc.FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=20,
        max_active_campaigns_per_user=1,
        daily_candidate_budget_per_user=100,
    )

    alerts = svc._build_factor_health_alerts(
        {"active_campaigns": 0, "worker_recent_failures": 2},
        quota_policy=policy,
    )
    assert alerts == [
        {
            "level": "warning",
            "code": "factor_campaign_worker_failures",
            "message": "Recent factor campaign worker events failed",
            "value": 2,
            "threshold": 0,
        }
    ]


def test_factor_research_metrics_export_health_payload():
    prometheus_client = pytest.importorskip("prometheus_client")
    from backend.shared.factor_research_metrics import update_factor_research_metrics

    update_factor_research_metrics(
        {
            "status": "warning",
            "alerts": [
                {
                    "level": "warning",
                    "code": "campaign_daily_candidate_quota_near_limit",
                }
            ],
            "indicators": {
                "today_campaign_candidates": 90,
                "active_campaigns": 0,
            },
            "quotaPolicy": {
                "dailyCandidateBudgetPerUser": 100,
                "maxActiveCampaignsPerUser": 1,
            },
        }
    )

    body = prometheus_client.generate_latest().decode()
    assert 'quantmind_factor_research_health_status{status="warning"} 1.0' in body
    assert "quantmind_factor_research_alerts_total 1.0" in body
    assert (
        'quantmind_factor_research_indicator_value{indicator="today_campaign_candidates"} 90.0'
        in body
    )
    assert (
        'quantmind_factor_research_quota_policy_value{quota="dailyCandidateBudgetPerUser"} 100.0'
        in body
    )


@pytest.mark.asyncio
async def test_promotion_lookup_filters_requested_run_inside_lateral_query():
    captured: dict[str, object] = {}

    class FakeMappings:
        def first(self):
            return None

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params
            return FakeResult()

    await svc._get_candidate_and_run_for_promotion(
        FakeSession(),
        tenant_id="tenant",
        user_id="user",
        candidate_id="candidate-1",
        run_id="run-old",
    )

    sql = str(captured["sql"])
    lateral_sql = sql.split("JOIN LATERAL", 1)[1].split(") r ON TRUE", 1)[0]
    outer_sql = sql.split(") r ON TRUE", 1)[1]
    assert "r0.id = :run_id" in lateral_sql
    assert "r.id = :run_id" not in outer_sql
    assert captured["params"]["run_id"] == "run-old"


def test_score_campaign_run_prefers_completed_metrics():
    score = svc._score_campaign_run(
        {"rank_ic_mean": 0.03, "coverage_days": 130, "inserted_values": 500},
        {"eligible": True},
    )

    assert score is not None
    assert score > 0


def test_summarize_campaign_items_returns_generation_stats():
    summary = svc._summarize_campaign_items(
        [
            {
                "candidateId": "candidate-1",
                "runId": "run-1",
                "generation": 1,
                "expression": "rank(close / ts_mean(close, 20))",
                "status": "completed",
                "score": 0.2,
                "metadata": {
                    "operator": "seed",
                    "evolutionReason": "seed expression",
                    "parentExpressions": [],
                },
            },
            {
                "candidateId": "candidate-2",
                "runId": "run-2",
                "generation": 2,
                "expression": "rank(close / ts_mean(close, 40))",
                "status": "completed",
                "score": 0.4,
                "metadata": {
                    "operator": "mutation",
                    "evolutionReason": "local window/operator mutation",
                    "parentExpressions": ["rank(close / ts_mean(close, 20))"],
                },
            },
            {
                "candidateId": "candidate-3",
                "runId": "run-3",
                "generation": 2,
                "expression": "rank(close / ts_mean(close, 60))",
                "status": "failed",
                "score": None,
                "reason": "unsupported_expression",
                "metadata": {
                    "operator": "mutation",
                    "evolutionReason": "local window/operator mutation",
                    "parentExpressions": ["rank(close / ts_mean(close, 20))"],
                },
            },
        ]
    )

    assert summary["totalCandidates"] == 3
    assert summary["maxGenerations"] == 2
    assert summary["completedGenerations"] == 2
    assert summary["bestCandidateId"] == "candidate-2"
    assert summary["generationStats"][1] == {
        "generation": 2,
        "totalCandidates": 2,
        "completedRuns": 1,
        "failedRuns": 1,
        "operatorStats": [
            {
                "operator": "mutation",
                "totalCandidates": 2,
                "completedRuns": 1,
                "bestScore": 0.4,
            }
        ],
        "bestCandidateId": "candidate-2",
        "bestRunId": "run-2",
        "bestExpression": "rank(close / ts_mean(close, 40))",
        "bestScore": 0.4,
    }
    assert summary["operatorStats"] == [
        {
            "operator": "mutation",
            "totalCandidates": 2,
            "completedRuns": 1,
            "bestScore": 0.4,
        },
        {
            "operator": "seed",
            "totalCandidates": 1,
            "completedRuns": 1,
            "bestScore": 0.2,
        },
    ]
    assert summary["reasonStats"] == [
        {"reason": "local window/operator mutation", "count": 2},
        {"reason": "seed expression", "count": 1},
    ]
    assert summary["lineageEdges"] == [
        {
            "fromExpression": "rank(close / ts_mean(close, 20))",
            "toExpression": "rank(close / ts_mean(close, 40))",
            "operator": "mutation",
            "generation": 2,
            "score": 0.4,
        },
        {
            "fromExpression": "rank(close / ts_mean(close, 20))",
            "toExpression": "rank(close / ts_mean(close, 60))",
            "operator": "mutation",
            "generation": 2,
            "score": None,
        },
    ]


@pytest.mark.asyncio
async def test_create_factor_campaign_runs_multiple_generations(monkeypatch):
    captured: dict[str, object] = {}
    calls: list[dict[str, object]] = []

    async def fake_enforce_quota(
        session, *, tenant_id, user_id, requested_candidates, policy
    ):
        captured["requested_candidates"] = requested_candidates
        return {
            "activeCampaigns": 0,
            "todayCandidates": 0,
            "requestedCandidates": requested_candidates,
            "projectedDailyCandidates": requested_candidates,
            "policy": {},
        }

    async def fake_run_campaign_expression(
        *,
        tenant_id,
        user_id,
        campaign_id,
        generation,
        rank_no,
        expression,
        params,
        item_metadata=None,
    ):
        calls.append(
            {
                "generation": generation,
                "rank_no": rank_no,
                "expression": expression,
                "item_metadata": item_metadata,
            }
        )
        return {
            "campaignId": campaign_id,
            "candidateId": f"candidate-{generation}-{rank_no}",
            "runId": f"run-{generation}-{rank_no}",
            "generation": generation,
            "rankNo": rank_no,
            "expression": expression,
            "status": "completed",
            "score": float(generation * 10 + rank_no),
            "reason": "eligible",
            "metrics": {"rank_ic_mean": 0.02},
            "metadata": item_metadata or {},
            "createdAt": None,
            "updatedAt": None,
        }

    class FakeMappings:
        def one(self):
            return {
                "id": "campaign-1",
                "tenant_id": "tenant",
                "user_id": "user",
                "name": "multi generation",
                "strategy": "template_mutation",
                "status": "completed",
                "seed_expression": "rank(close / ts_mean(close, 20))",
                "params_json": captured.get("params_json") or {},
                "summary_json": captured.get("summary_json") or {},
                "metadata_json": captured.get("metadata_json") or {},
                "started_at": None,
                "completed_at": None,
                "created_at": None,
                "updated_at": None,
            }

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "INSERT INTO qm_factor_campaigns" in sql:
                captured["params_json"] = json.loads(params["params_json"])
                captured["metadata_json"] = json.loads(params["metadata_json"])
                return FakeResult()
            if "UPDATE qm_factor_campaigns" in sql:
                captured["summary_json"] = json.loads(params["summary_json"])
                captured["status"] = params["status"]
                return FakeResult()
            raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "_enforce_factor_campaign_quota", fake_enforce_quota)
    monkeypatch.setattr(
        campaign_svc, "_run_campaign_expression", fake_run_campaign_expression
    )

    result = await svc.create_factor_campaign(
        "tenant",
        "user",
        {
            "name": "multi generation",
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "n_candidates": 2,
            "max_generations": 2,
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "worker_policy": {
                "worker_id": "ui-worker",
                "concurrency": 999,
                "max_claims": 999,
                "heartbeat_interval_seconds": 999,
            },
            "retry_policy": {
                "max_attempts": 999,
                "retry_failed_after_minutes": 9999,
            },
            "execution_lease": {"lease_seconds": 999999},
            "metadata": {"workerPolicy": {"concurrency": 9999}},
        },
    )

    assert captured["requested_candidates"] == 4
    assert captured["params_json"]["n_candidates"] == 4
    assert captured["params_json"]["candidates_per_generation"] == 2
    assert captured["params_json"]["max_generations"] == 2
    assert captured["metadata_json"]["generator"] == "quantmind_mutation_crossover"
    assert (
        captured["metadata_json"]["generationStrategy"]
        == "local_iterative_mutation_crossover"
    )
    assert captured["status"] == "completed"
    assert [call["generation"] for call in calls] == [1, 1, 2, 2]
    assert all(isinstance(call["item_metadata"], dict) for call in calls)
    assert calls[0]["item_metadata"]["operator"] == "seed"
    assert calls[2]["item_metadata"]["parentExpressions"]
    assert result["summary"]["maxGenerations"] == 2
    assert result["summary"]["completedGenerations"] == 2
    assert len(result["items"]) == 4


@pytest.mark.asyncio
async def test_create_factor_campaign_can_schedule_async_execution(monkeypatch):
    captured: dict[str, object] = {}
    scheduled: list[dict[str, str]] = []

    async def fake_enforce_quota(
        session, *, tenant_id, user_id, requested_candidates, policy
    ):
        return {
            "activeCampaigns": 0,
            "todayCandidates": 0,
            "requestedCandidates": requested_candidates,
            "projectedDailyCandidates": requested_candidates,
            "policy": {},
        }

    async def fake_run_campaign_expression(**kwargs):
        raise AssertionError("async campaign creation must not run evaluator inline")

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "INSERT INTO qm_factor_campaigns" in sql:
                captured["params_json"] = json.loads(params["params_json"])
                captured["metadata_json"] = json.loads(params["metadata_json"])
                captured["status"] = params["status"]
                captured["started_at"] = params["started_at"]
                return object()
            raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    def fake_schedule_factor_campaign_execution(*, tenant_id, user_id, campaign_id):
        scheduled.append(
            {"tenant_id": tenant_id, "user_id": user_id, "campaign_id": campaign_id}
        )

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "_enforce_factor_campaign_quota", fake_enforce_quota)
    monkeypatch.setattr(svc, "_run_campaign_expression", fake_run_campaign_expression)
    monkeypatch.setattr(
        svc,
        "_schedule_factor_campaign_execution",
        fake_schedule_factor_campaign_execution,
    )

    result = await svc.create_factor_campaign(
        "tenant",
        "user",
        {
            "name": "async campaign",
            "run_async": True,
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "n_candidates": 2,
            "max_generations": 2,
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "worker_policy": {
                "worker_id": "ui-worker",
                "concurrency": 999,
                "max_claims": 999,
                "heartbeat_interval_seconds": 999,
            },
            "retry_policy": {
                "max_attempts": 999,
                "retry_failed_after_minutes": 9999,
            },
            "execution_lease": {"lease_seconds": 999999},
            "metadata": {"workerPolicy": {"concurrency": 9999}},
        },
    )

    assert captured["status"] == "pending"
    assert captured["started_at"] is None
    assert captured["params_json"]["n_candidates"] == 4
    assert captured["params_json"]["candidates_per_generation"] == 2
    assert captured["metadata_json"]["executionMode"] == "async"
    assert captured["metadata_json"]["workerPolicy"] == {
        "workerId": "ui-worker",
        "externalWorkerRequired": False,
        "concurrency": 4,
        "maxClaims": 20,
        "heartbeatIntervalSeconds": 300,
    }
    assert captured["metadata_json"]["retryPolicy"] == {
        "maxAttempts": 3,
        "retryFailedAfterMinutes": 1440,
    }
    assert captured["metadata_json"]["executionLease"] == {"leaseSeconds": 7200}
    assert captured["params_json"]["worker_policy"] == captured["metadata_json"][
        "workerPolicy"
    ]
    assert captured["params_json"]["retry_policy"] == captured["metadata_json"][
        "retryPolicy"
    ]
    assert captured["params_json"]["execution_lease"] == captured["metadata_json"][
        "executionLease"
    ]
    assert result["status"] == "pending"
    assert result["items"] == []
    assert len(scheduled) == 1
    assert scheduled[0]["tenant_id"] == "tenant"
    assert scheduled[0]["user_id"] == "user"


@pytest.mark.asyncio
async def test_create_factor_campaign_external_worker_does_not_schedule_inline(
    monkeypatch,
):
    captured: dict[str, object] = {}
    scheduled: list[dict[str, str]] = []

    async def fake_enforce_quota(
        session, *, tenant_id, user_id, requested_candidates, policy
    ):
        return {
            "activeCampaigns": 0,
            "todayCandidates": 0,
            "requestedCandidates": requested_candidates,
            "projectedDailyCandidates": requested_candidates,
            "policy": {},
        }

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "INSERT INTO qm_factor_campaigns" in sql:
                captured["metadata_json"] = json.loads(params["metadata_json"])
                captured["status"] = params["status"]
                return object()
            raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    def fake_schedule_factor_campaign_execution(*, tenant_id, user_id, campaign_id):
        scheduled.append(
            {"tenant_id": tenant_id, "user_id": user_id, "campaign_id": campaign_id}
        )

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "_enforce_factor_campaign_quota", fake_enforce_quota)
    monkeypatch.setattr(
        svc,
        "_schedule_factor_campaign_execution",
        fake_schedule_factor_campaign_execution,
    )

    result = await svc.create_factor_campaign(
        "tenant",
        "user",
        {
            "name": "external worker campaign",
            "run_async": True,
            "seed_expression": "rank(close / ts_mean(close, 20))",
            "n_candidates": 1,
            "max_generations": 1,
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "worker_policy": {"external_worker": True, "worker_id": "worker-live"},
        },
    )

    assert result["status"] == "pending"
    assert captured["status"] == "pending"
    assert captured["metadata_json"]["worker"] == "external_factor_campaign_worker"
    assert captured["metadata_json"]["workerPolicy"]["externalWorkerRequired"] is True
    assert scheduled == []


@pytest.mark.asyncio
async def test_execute_factor_campaign_processes_pending_campaign(monkeypatch):
    captured: dict[str, object] = {}
    calls: list[dict[str, object]] = []

    async def fake_run_campaign_expression(
        *,
        tenant_id,
        user_id,
        campaign_id,
        generation,
        rank_no,
        expression,
        params,
        item_metadata=None,
    ):
        calls.append(
            {
                "generation": generation,
                "rank_no": rank_no,
                "expression": expression,
                "start_date": params["start_date"],
                "item_metadata": item_metadata,
            }
        )
        return {
            "campaignId": campaign_id,
            "candidateId": f"candidate-{rank_no}",
            "runId": f"run-{rank_no}",
            "generation": generation,
            "rankNo": rank_no,
            "expression": expression,
            "status": "completed",
            "score": 1.0,
            "reason": "eligible",
            "metrics": {"rank_ic_mean": 0.02},
            "metadata": item_metadata or {},
            "createdAt": None,
            "updatedAt": None,
        }

    pending_row = {
        "id": "campaign-async",
        "tenant_id": "tenant",
        "user_id": "user",
        "name": "async campaign",
        "strategy": "mutation_crossover",
        "status": "running",
        "seed_expression": "rank(close / ts_mean(close, 20))",
        "params_json": {
            "universe": "hs300",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "n_groups": 5,
            "holding_period": 5,
            "neutralize_industry": True,
            "neutralize_cap": True,
            "validation_profile": "campaign",
            "metadata": {"pipeline_stage": "factor_campaign"},
            "n_candidates": 2,
            "candidates_per_generation": 2,
            "max_generations": 1,
        },
        "summary_json": {},
        "metadata_json": {"executionMode": "async"},
        "started_at": None,
        "completed_at": None,
        "created_at": None,
        "updated_at": None,
    }

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def one(self):
            return self.rows[0]

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "SET status = 'running'" in sql:
                captured["claimed"] = params
                return FakeResult([pending_row])
            if "SET status = :status" in sql:
                captured["final_status"] = params["status"]
                captured["summary_json"] = json.loads(params["summary_json"])
                final_row = {
                    **pending_row,
                    "status": params["status"],
                    "summary_json": captured["summary_json"],
                }
                return FakeResult([final_row])
            raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)
    monkeypatch.setattr(
        campaign_svc, "_run_campaign_expression", fake_run_campaign_expression
    )

    result = await campaign_svc.execute_factor_campaign(
        tenant_id="tenant",
        user_id="user",
        campaign_id="campaign-async",
    )

    assert captured["claimed"]["campaign_id"] == "campaign-async"
    assert captured["final_status"] == "completed"
    assert captured["summary_json"]["completedRuns"] == 2
    assert len(calls) == 2
    assert {call["generation"] for call in calls} == {1}
    assert all(isinstance(call["item_metadata"], dict) for call in calls)
    assert all(call["start_date"] == "2026-01-01" for call in calls)
    assert result["status"] == "completed"
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_api_execute_factor_campaign_delegates_to_engine(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_engine_execute_campaign(*, tenant_id, user_id, campaign_id):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
            }
        )
        return {"id": campaign_id, "status": "completed"}

    monkeypatch.setattr(
        campaign_svc,
        "execute_factor_campaign",
        fake_engine_execute_campaign,
    )

    result = await svc.execute_factor_campaign(
        tenant_id="tenant",
        user_id="user",
        campaign_id="campaign-async",
    )

    assert captured == {
        "tenant_id": "tenant",
        "user_id": "user",
        "campaign_id": "campaign-async",
    }
    assert result == {"id": "campaign-async", "status": "completed"}


@pytest.mark.asyncio
async def test_claim_next_pending_factor_campaign_claims_atomically(monkeypatch):
    captured: dict[str, object] = {}
    claimed_row = {
        "id": "campaign-claim",
        "tenant_id": "tenant",
        "user_id": "user",
        "status": "running",
    }

    class FakeMappings:
        def first(self):
            return claimed_row

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params or {}
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_execute_claimed_factor_campaign(
        campaign,
        *,
        tenant_id,
        user_id,
        campaign_id,
    ):
        captured["claimed"] = {
            "campaign": dict(campaign),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "campaign_id": campaign_id,
        }
        return {"id": campaign_id, "status": "completed", "summary": {}}

    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)
    monkeypatch.setattr(
        campaign_svc,
        "execute_claimed_factor_campaign",
        fake_execute_claimed_factor_campaign,
    )

    result = await campaign_svc.claim_next_pending_factor_campaign(
        worker_id="worker-1",
        lease_seconds=120,
    )

    sql = str(captured["sql"])
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "UPDATE qm_factor_campaigns" in sql
    assert "workerPolicy" in sql
    assert "metadata_json->'workerPolicy'->>'workerId' = :worker_id" in sql
    assert "COALESCE(metadata_json->'workerPolicy'->>'workerId', '') = ''" in sql
    assert "currentWorkerId" in sql
    assert "attemptNo" in sql
    assert captured["params"]["worker_id"] == "worker-1"
    assert captured["params"]["lease_seconds"] == 120
    assert captured["claimed"]["campaign_id"] == "campaign-claim"
    assert captured["claimed"]["tenant_id"] == "tenant"
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_claim_next_pending_factor_campaign_returns_none_when_idle(monkeypatch):
    class FakeMappings:
        def first(self):
            return None

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)

    assert await campaign_svc.claim_next_pending_factor_campaign() is None


@pytest.mark.asyncio
async def test_recover_stale_running_factor_campaigns_requeues_old_running_rows():
    captured: dict[str, object] = {}

    class FakeMappings:
        def all(self):
            return [{"id": "campaign-1"}, {"id": "campaign-2"}]

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)
    try:
        count = await campaign_svc.recover_stale_running_factor_campaigns(
            stale_after_minutes=15
        )
    finally:
        monkeypatch.undo()

    sql = str(captured["sql"])
    assert "SET status = 'pending'" in sql
    assert "stale_running_worker_requeue" in sql
    assert "failed_worker_retry_requeue" in sql
    assert "status = 'running'" in sql
    assert "status = 'failed'" in sql
    assert "retryPolicy" in sql
    assert "maxAttempts" in sql
    assert "retryFailedAfterMinutes" in sql
    assert captured["params"]["stale_after_minutes"] == 15
    assert count == 2


@pytest.mark.asyncio
async def test_record_factor_campaign_worker_event_persists_payload(monkeypatch):
    captured: dict[str, object] = {}

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)

    event_id = await campaign_svc.record_factor_campaign_worker_event(
        event_type="processed",
        campaign_id="campaign-1",
        tenant_id="tenant",
        user_id="user",
        worker_id="worker-1",
        attempt_no=3,
        duration_ms=456,
        status="completed",
        details={"completedRuns": 2},
    )

    assert event_id
    sql = str(captured["sql"])
    params = captured["params"]
    assert "INSERT INTO qm_factor_campaign_worker_events" in sql
    assert params["event_type"] == "processed"
    assert params["campaign_id"] == "campaign-1"
    assert params["tenant_id"] == "tenant"
    assert params["user_id"] == "user"
    assert params["worker_id"] == "worker-1"
    assert params["attempt_no"] == 3
    assert params["duration_ms"] == 456
    assert params["status"] == "completed"
    assert json.loads(params["details_json"]) == {"completedRuns": 2}


@pytest.mark.asyncio
async def test_list_factor_campaign_worker_events_filters_scope_and_campaign(
    monkeypatch,
):
    captured: list[tuple[str, dict]] = []

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeResult:
        def __init__(self, rows=None, scalar=None):
            self.rows = rows or []
            self.scalar = scalar

        def mappings(self):
            return FakeMappings(self.rows)

        def scalar_one(self):
            return self.scalar

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            captured.append((sql, params))
            if "SELECT COUNT" in sql:
                return FakeResult(scalar=1)
            return FakeResult(
                rows=[
                    {
                        "id": "event-1",
                        "event_type": "processed",
                        "campaign_id": "campaign-1",
                        "tenant_id": "tenant",
                        "user_id": "user",
                        "worker_id": "worker-1",
                        "attempt_no": 2,
                        "duration_ms": 345,
                        "heartbeat_at": datetime(2026, 1, 2, 3, 4, 6),
                        "status": "completed",
                        "details_json": {"completedRuns": 2},
                        "created_at": datetime(2026, 1, 2, 3, 4, 5),
                    }
                ]
            )

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        assert kwargs.get("read_only") is True
        yield FakeSession()

    monkeypatch.setattr(campaign_svc, "get_session", fake_get_session)

    result = await campaign_svc.list_factor_campaign_worker_events(
        "tenant",
        "user",
        campaign_id="campaign-1",
        worker_id="worker-1",
        event_type="processed",
        status="completed",
        limit=500,
        offset=-1,
    )

    sql, params = captured[0]
    assert "(tenant_id = :tenant_id OR tenant_id IS NULL)" in sql
    assert "(user_id = :user_id OR user_id IS NULL)" in sql
    assert "campaign_id = :campaign_id" in sql
    assert "worker_id = :worker_id" in sql
    assert "event_type = :event_type" in sql
    assert "status = :status" in sql
    assert params["limit"] == 100
    assert params["offset"] == 0
    assert result["total"] == 1
    assert result["items"][0]["eventType"] == "processed"
    assert result["items"][0]["workerId"] == "worker-1"
    assert result["items"][0]["attemptNo"] == 2
    assert result["items"][0]["durationMs"] == 345
    assert result["items"][0]["details"] == {"completedRuns": 2}


@pytest.mark.asyncio
async def test_api_campaign_worker_event_wrapper_delegates_to_engine(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_engine_list_events(
        tenant_id,
        user_id,
        *,
        campaign_id=None,
        worker_id=None,
        event_type=None,
        status=None,
        limit=20,
        offset=0,
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "campaign_id": campaign_id,
                "worker_id": worker_id,
                "event_type": event_type,
                "status": status,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [{"id": "event-1"}], "total": 1}

    monkeypatch.setattr(
        campaign_svc,
        "list_factor_campaign_worker_events",
        fake_engine_list_events,
    )

    result = await svc.list_factor_campaign_worker_events(
        "tenant",
        "user",
        campaign_id="campaign-1",
        worker_id="worker-1",
        event_type="processed",
        status="completed",
        limit=7,
        offset=2,
    )

    assert captured == {
        "tenant_id": "tenant",
        "user_id": "user",
        "campaign_id": "campaign-1",
        "worker_id": "worker-1",
        "event_type": "processed",
        "status": "completed",
        "limit": 7,
        "offset": 2,
    }
    assert result == {"items": [{"id": "event-1"}], "total": 1}


def test_build_factor_training_payload_includes_active_feature_and_factor_metadata():
    payload = svc._build_factor_training_payload(
        {
            "id": "promotion-1",
            "candidate_id": "candidate-1",
            "run_id": "run-1",
            "candidate_name": "factor alpha",
            "feature_key": "factor_alpha",
            "version_id": "feature-set-1",
            "expression": "rank(close / ts_mean(close, 20))",
            "run_params_json": {
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
                "holding_period": 5,
            },
        },
        ["mom_ret_1d", "factor_alpha"],
        {
            "num_boost_round": 200,
            "baseline_training_run_id": "baseline-train-1",
            "baseline_metrics": {
                "test": {"auc": 0.52, "rmse": 0.24},
                "train": {"auc": 0.58, "rmse": 0.16},
                "val": {"auc": 0.54, "rmse": 0.22},
            },
        },
    )

    assert payload["features"] == ["mom_ret_1d", "factor_alpha"]
    assert payload["factor_research"]["promotion_id"] == "promotion-1"
    assert payload["target_horizon_days"] == 5
    assert payload["num_boost_round"] == 200
    assert payload["train_start"] < payload["train_end"] < payload["valid_start"]
    assert payload["factor_research"]["baseline_training_run_id"] == "baseline-train-1"
    assert payload["factor_research"]["baseline_metrics"]["test"]["auc"] == 0.52


def test_build_factor_training_payload_can_build_baseline_without_factor():
    payload = svc._build_factor_training_payload(
        {
            "id": "promotion-1",
            "candidate_id": "candidate-1",
            "run_id": "run-1",
            "candidate_name": "factor alpha",
            "feature_key": "factor_alpha",
            "version_id": "feature-set-1",
            "expression": "rank(close / ts_mean(close, 20))",
            "run_params_json": {
                "start_date": "2026-01-01",
                "end_date": "2026-06-30",
                "holding_period": 5,
            },
        },
        ["mom_ret_1d", "factor_alpha"],
        {},
        include_factor=False,
    )

    assert payload["features"] == ["mom_ret_1d"]
    assert payload["job_name"].startswith("factor_baseline_factor_alpha_")
    assert payload["factor_research"]["pipeline_stage"] == "factor_baseline_training"
    assert payload["factor_research"]["includes_promoted_factor"] is False


def test_should_launch_auto_baseline_training_respects_overrides():
    assert svc._should_launch_auto_baseline_training({}) is True
    assert svc._should_launch_auto_baseline_training({"auto_baseline": False}) is False
    assert (
        svc._should_launch_auto_baseline_training(
            {"baseline_training_run_id": "baseline-1"}
        )
        is False
    )
    assert (
        svc._should_launch_auto_baseline_training(
            {"baseline_metrics": {"test": {"auc": 0.52}}}
        )
        is False
    )


@pytest.mark.asyncio
async def test_launch_factor_promotion_training_auto_submits_baseline(monkeypatch):
    promotion_row = {
        "id": "promotion-1",
        "candidate_id": "candidate-1",
        "run_id": "run-1",
        "tenant_id": "tenant",
        "user_id": "user",
        "materialization_status": "materialized",
        "candidate_name": "factor alpha",
        "feature_key": "factor_alpha",
        "version_id": "feature-set-1",
        "expression": "rank(close / ts_mean(close, 20))",
        "run_params_json": {
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "holding_period": 5,
        },
    }
    submitted_payloads: list[dict] = []
    inserted_records: list[dict] = []

    class FakeMappings:
        def first(self):
            return promotion_row

    class FakeResult:
        def mappings(self):
            return FakeMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_load_active_feature_catalog_items(session):
        return [
            {"feature_key": "mom_ret_1d", "enabled": True},
            {"feature_key": "factor_alpha", "enabled": True},
        ]

    async def fake_submit_training_job(payload, background_tasks, current_user):
        submitted_payloads.append(payload)
        return {"runId": f"train-{len(submitted_payloads)}", "status": "pending"}

    async def fake_insert_factor_training_run_record(**kwargs):
        inserted_records.append(kwargs)
        return {
            "id": f"factor-training-{len(inserted_records)}",
            "promotion_id": kwargs["promotion_id"],
            "candidate_id": kwargs["promotion_row"]["candidate_id"],
            "factor_run_id": kwargs["promotion_row"]["run_id"],
            "training_run_id": kwargs["training_run_id"],
            "status": kwargs["training_response"]["status"],
            "feature_key": kwargs["promotion_row"]["feature_key"],
            "feature_set_version_id": kwargs["promotion_row"]["version_id"],
            "request_payload_json": kwargs["training_payload"],
            "response_json": kwargs["training_response"],
            "metadata_json": kwargs["metadata"],
            "created_at": datetime(2026, 6, 1, 9, 0, 0),
            "updated_at": datetime(2026, 6, 1, 9, 0, 0),
        }

    fake_admin_pkg = types.ModuleType("backend.services.api.routers.admin")
    fake_admin_pkg.__path__ = []
    fake_admin_training = types.ModuleType(
        "backend.services.api.routers.admin.admin_training"
    )
    fake_admin_training.submit_training_job = fake_submit_training_job
    monkeypatch.setitem(
        sys.modules, "backend.services.api.routers.admin", fake_admin_pkg
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.services.api.routers.admin.admin_training",
        fake_admin_training,
    )
    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(
        svc,
        "_load_active_feature_catalog_items",
        fake_load_active_feature_catalog_items,
    )
    monkeypatch.setattr(
        svc,
        "_insert_factor_training_run_record",
        fake_insert_factor_training_run_record,
    )

    result = await svc.launch_factor_promotion_training(
        "tenant",
        "user",
        "promotion-1",
        {},
        background_tasks=None,
        current_user={"id": "user"},
    )

    assert len(submitted_payloads) == 2
    assert submitted_payloads[0]["features"] == ["mom_ret_1d"]
    assert submitted_payloads[0]["factor_research"]["pipeline_stage"] == (
        "factor_baseline_training"
    )
    assert submitted_payloads[1]["features"] == ["mom_ret_1d", "factor_alpha"]
    assert submitted_payloads[1]["factor_research"]["baseline_training_run_id"] == (
        "train-1"
    )
    assert inserted_records[0]["metadata"]["pipeline_stage"] == (
        "factor_baseline_training"
    )
    assert inserted_records[1]["metadata"]["auto_baseline_training_run_id"] == "train-1"
    assert result["trainingRunId"] == "train-2"


def test_row_to_factor_training_run_keeps_legacy_record_without_training_snapshot():
    item = svc._row_to_factor_training_run(
        {
            "id": "factor-training-1",
            "promotion_id": "promotion-1",
            "candidate_id": "candidate-1",
            "factor_run_id": "run-1",
            "training_run_id": "train-1",
            "status": "pending",
            "feature_key": "factor_alpha",
            "feature_set_version_id": "feature-set-1",
            "request_payload_json": {"features": ["factor_alpha"]},
            "response_json": {"runId": "train-1", "status": "pending"},
            "metadata_json": {"source": "factor_research"},
            "created_at": datetime(2026, 6, 1, 9, 0, 0),
            "updated_at": datetime(2026, 6, 1, 9, 0, 0),
        }
    )

    assert item["status"] == "pending"
    assert item["trainingStatus"] == "pending"
    assert item["trainingProgress"] is None
    assert item["trainingResult"] == {}
    assert "trainingJob" not in item["response"]


def test_row_to_factor_training_run_merges_training_job_snapshot():
    item = svc._row_to_factor_training_run(
        {
            "id": "factor-training-1",
            "promotion_id": "promotion-1",
            "candidate_id": "candidate-1",
            "factor_run_id": "run-1",
            "training_run_id": "train-1",
            "status": "running",
            "feature_key": "factor_alpha",
            "feature_set_version_id": "feature-set-1",
            "request_payload_json": {"features": ["factor_alpha"]},
            "response_json": {"runId": "train-1", "status": "running"},
            "metadata_json": {"source": "factor_research"},
            "created_at": datetime(2026, 6, 1, 9, 0, 0),
            "updated_at": datetime(2026, 6, 1, 9, 0, 0),
            "training_job_status": "completed",
            "training_job_progress": 100,
            "training_job_result": {
                "metrics": {
                    "train": {"rmse": 0.12, "auc": 0.61},
                    "val": {"rmse": 0.18, "auc": 0.57},
                    "test": {"rmse": 0.2, "auc": 0.55},
                },
                "artifacts": [{"name": "model.pkl", "key": "models/train-1/model.pkl"}],
                "summary": {"status": "训练完成", "message": "done"},
            },
            "training_job_logs": "completed",
            "training_job_request_payload": {
                "features": ["factor_alpha"],
                "factor_research": {
                    "baseline_metrics": {
                        "train": {"rmse": 0.13, "auc": 0.58},
                        "val": {"rmse": 0.2, "auc": 0.54},
                        "test": {"rmse": 0.24, "auc": 0.52},
                    }
                },
            },
            "training_job_updated_at": datetime(2026, 6, 1, 10, 0, 0),
        }
    )

    assert item["status"] == "completed"
    assert item["trainingStatus"] == "completed"
    assert item["trainingProgress"] == 100
    assert item["trainingResult"]["metrics"]["test"]["auc"] == 0.55
    assert item["trainingComparison"]["status"] == "improved"
    assert item["trainingComparison"]["delta"]["test_auc"] == pytest.approx(0.03)
    assert item["trainingComparison"]["gate"]["decision"] == "approve_model_candidate"
    assert item["trainingGate"]["allowDefaultModelPromotion"] is True
    assert item["response"]["trainingJob"]["isCompleted"] is True


def test_factor_training_comparison_reports_missing_baseline():
    comparison = svc._build_factor_training_comparison(
        promoted_result={
            "metrics": {
                "train": {"rmse": 0.12, "auc": 0.61},
                "val": {"rmse": 0.18, "auc": 0.57},
                "test": {"rmse": 0.2, "auc": 0.55},
            }
        },
        request_payload={"factor_research": {"feature_key": "factor_alpha"}},
        row={},
    )

    assert comparison["status"] == "baseline_missing"
    assert comparison["promoted"]["test"]["auc"] == 0.55
    assert comparison["gate"]["decision"] == "blocked"


def test_factor_training_gate_recommends_rollback_for_regression():
    comparison = svc._build_factor_training_comparison(
        promoted_result={
            "metrics": {
                "train": {"rmse": 0.16, "auc": 0.55},
                "val": {"rmse": 0.22, "auc": 0.5},
                "test": {"rmse": 0.3, "auc": 0.48},
            }
        },
        request_payload={
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            }
        },
        row={},
    )

    assert comparison["status"] == "regressed"
    assert comparison["gate"]["decision"] == "rollback_recommended"
    assert comparison["gate"]["allowDefaultModelPromotion"] is False


def test_factor_training_approval_requires_completed_gate():
    item = {
        "status": "pending",
        "trainingStatus": "pending",
        "trainingGate": {
            "decision": "approve_model_candidate",
            "allowDefaultModelPromotion": True,
        },
    }

    assert svc._factor_training_gate_allows_default_promotion(item) is False

    item["status"] = "completed"
    item["trainingStatus"] = "completed"
    assert svc._factor_training_gate_allows_default_promotion(item) is True

    item["trainingGate"]["decision"] = "observe"
    assert svc._factor_training_gate_allows_default_promotion(item) is False


def test_extract_registered_model_id_requires_ready_registration():
    assert (
        svc._extract_registered_model_id_from_training_item(
            {
                "trainingResult": {
                    "model_registration": {
                        "model_id": "model_train_1",
                        "status": "ready",
                    }
                }
            }
        )
        == "model_train_1"
    )
    assert (
        svc._extract_registered_model_id_from_training_item(
            {
                "trainingResult": {
                    "model_registration": {
                        "model_id": "model_failed",
                        "status": "failed",
                    }
                }
            }
        )
        == ""
    )


@pytest.mark.asyncio
async def test_approve_factor_training_run_requires_explicit_default_flag():
    with pytest.raises(ValueError, match="set_default_model=true"):
        await svc.approve_factor_training_run(
            "default",
            "user-1",
            "factor-training-1",
            {"reason": "manual_review"},
        )


@pytest.mark.asyncio
async def test_approve_factor_training_run_sets_default_and_persists_approval(
    monkeypatch,
):
    row = {
        "id": "factor-training-1",
        "promotion_id": "promotion-1",
        "candidate_id": "candidate-1",
        "factor_run_id": "run-1",
        "training_run_id": "train-1",
        "status": "running",
        "feature_key": "factor_alpha",
        "feature_set_version_id": "feature-set-1",
        "request_payload_json": {
            "features": ["factor_alpha"],
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            },
        },
        "response_json": {"runId": "train-1", "status": "completed"},
        "metadata_json": {"source": "factor_research"},
        "created_at": datetime(2026, 6, 1, 9, 0, 0),
        "updated_at": datetime(2026, 6, 1, 9, 0, 0),
        "training_job_status": "completed",
        "training_job_progress": 100,
        "training_job_result": {
            "metrics": {
                "train": {"rmse": 0.12, "auc": 0.61},
                "val": {"rmse": 0.18, "auc": 0.57},
                "test": {"rmse": 0.2, "auc": 0.55},
            },
            "artifacts": [{"name": "model.pkl", "key": "models/train-1/model.pkl"}],
            "summary": {"status": "训练完成", "message": "done"},
            "model_registration": {"model_id": "model_train_1", "status": "ready"},
        },
        "training_job_logs": "completed",
        "training_job_request_payload": {
            "features": ["factor_alpha"],
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            },
        },
        "training_job_updated_at": datetime(2026, 6, 1, 10, 0, 0),
    }
    seen: dict[str, object] = {"updates": []}

    async def fake_get_factor_training_run_row(
        session, *, tenant_id, user_id, training_id
    ):
        seen["lookup"] = (tenant_id, user_id, training_id)
        return row

    class FakeSession:
        async def execute(self, statement, params=None):
            seen["updates"].append((str(statement), params or {}))

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    class FakeModelRegistryService:
        async def set_default_model(self, *, tenant_id, user_id, model_id):
            seen["default_model"] = (tenant_id, user_id, model_id)
            return {"model_id": model_id, "is_default": True}

    monkeypatch.setattr(
        svc, "_get_factor_training_run_row", fake_get_factor_training_run_row
    )
    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "model_registry_service", FakeModelRegistryService())
    monkeypatch.setattr(
        svc,
        "get_factor_approval_policy",
        _default_policy,
    )

    result = await svc.approve_factor_training_run(
        "default",
        "user-1",
        "factor-training-1",
        {
            "set_default_model": True,
            "reason": "reviewed_by_factor_committee",
            "metadata": {"ticket": "FR-1"},
        },
    )

    assert seen["lookup"] == ("default", "user-1", "factor-training-1")
    assert seen["default_model"] == ("default", "user-1", "model_train_1")
    assert result["approval"]["model_id"] == "model_train_1"
    assert result["approval"]["request_metadata"] == {"ticket": "FR-1"}
    assert result["training"]["metadata"]["approval"]["default_model_set"] is True
    update_params = seen["updates"][0][1]
    assert json.loads(update_params["metadata_json"])["approval"]["reason"] == (
        "reviewed_by_factor_committee"
    )
    assert json.loads(update_params["response_json"])["approval"]["model_id"] == (
        "model_train_1"
    )
    audit_statement, audit_params = seen["updates"][1]
    assert "INSERT INTO qm_factor_approval_audit" in audit_statement
    assert audit_params["training_id"] == "factor-training-1"
    assert audit_params["model_id"] == "model_train_1"
    assert audit_params["status"] == "approved"
    assert audit_params["idempotent"] is False
    assert json.loads(audit_params["request_metadata"]) == {"ticket": "FR-1"}
    assert json.loads(audit_params["approval_json"])["reason"] == (
        "reviewed_by_factor_committee"
    )


@pytest.mark.asyncio
async def test_approve_factor_training_run_is_idempotent_when_default_already_set(
    monkeypatch,
):
    original_approval = {
        "status": "approved",
        "set_default_model": True,
        "model_id": "model_train_1",
        "default_model_set": True,
        "approved_by": "user-1",
        "approved_at": "2026-06-01T10:30:00+00:00",
        "reason": "reviewed_by_factor_committee",
        "request_metadata": {"ticket": "FR-1"},
    }
    row = {
        "id": "factor-training-1",
        "promotion_id": "promotion-1",
        "candidate_id": "candidate-1",
        "factor_run_id": "run-1",
        "training_run_id": "train-1",
        "status": "running",
        "feature_key": "factor_alpha",
        "feature_set_version_id": "feature-set-1",
        "request_payload_json": {
            "features": ["factor_alpha"],
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            },
        },
        "response_json": {
            "runId": "train-1",
            "status": "completed",
            "approval": original_approval,
        },
        "metadata_json": {
            "source": "factor_research",
            "approval": original_approval,
        },
        "created_at": datetime(2026, 6, 1, 9, 0, 0),
        "updated_at": datetime(2026, 6, 1, 9, 0, 0),
        "training_job_status": "completed",
        "training_job_progress": 100,
        "training_job_result": {
            "metrics": {
                "train": {"rmse": 0.12, "auc": 0.61},
                "val": {"rmse": 0.18, "auc": 0.57},
                "test": {"rmse": 0.2, "auc": 0.55},
            },
            "artifacts": [{"name": "model.pkl", "key": "models/train-1/model.pkl"}],
            "summary": {"status": "训练完成", "message": "done"},
            "model_registration": {"model_id": "model_train_1", "status": "ready"},
        },
        "training_job_logs": "completed",
        "training_job_request_payload": {
            "features": ["factor_alpha"],
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            },
        },
        "training_job_updated_at": datetime(2026, 6, 1, 10, 0, 0),
    }
    seen: dict[str, object] = {"updates": []}

    async def fake_get_factor_training_run_row(
        session, *, tenant_id, user_id, training_id
    ):
        seen["lookup"] = (tenant_id, user_id, training_id)
        return row

    class FakeSession:
        async def execute(self, statement, params=None):
            seen["updates"].append((str(statement), params or {}))

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    class FakeModelRegistryService:
        async def get_default_model(self, *, tenant_id, user_id):
            seen["current_default"] = (tenant_id, user_id)
            return {"model_id": "model_train_1", "is_default": True}

        async def set_default_model(self, *, tenant_id, user_id, model_id):
            raise AssertionError("idempotent approval must not reset default model")

    monkeypatch.setattr(
        svc, "_get_factor_training_run_row", fake_get_factor_training_run_row
    )
    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "model_registry_service", FakeModelRegistryService())
    monkeypatch.setattr(
        svc,
        "get_factor_approval_policy",
        _default_policy,
    )

    result = await svc.approve_factor_training_run(
        "default",
        "user-1",
        "factor-training-1",
        {
            "set_default_model": True,
            "reason": "retry_should_be_idempotent",
        },
    )

    assert seen["lookup"] == ("default", "user-1", "factor-training-1")
    assert seen["current_default"] == ("default", "user-1")
    assert len(seen["updates"]) == 1
    audit_statement, audit_params = seen["updates"][0]
    assert "INSERT INTO qm_factor_approval_audit" in audit_statement
    assert audit_params["training_id"] == "factor-training-1"
    assert audit_params["model_id"] == "model_train_1"
    assert audit_params["status"] == "idempotent_replay"
    assert audit_params["idempotent"] is True
    assert json.loads(audit_params["request_metadata"]) == {"ticket": "FR-1"}
    assert json.loads(audit_params["approval_json"]) == original_approval
    assert result["idempotent"] is True


@pytest.mark.asyncio
async def test_approve_factor_training_run_respects_no_direct_approval_policy(
    monkeypatch,
):
    async def fake_policy(tenant_id):
        policy = svc._default_factor_approval_policy(tenant_id)
        policy["allowDirectApproval"] = False
        return policy

    monkeypatch.setattr(svc, "get_factor_approval_policy", fake_policy)

    with pytest.raises(ValueError, match="requires approval request review"):
        await svc.approve_factor_training_run(
            "default",
            "user-1",
            "factor-training-1",
            {"set_default_model": True},
            approver_user_id="reviewer-1",
        )


@pytest.mark.asyncio
async def test_list_factor_approval_audits_filters_and_maps_rows(monkeypatch):
    seen: list[tuple[str, dict]] = []
    audit_row = {
        "id": "audit-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "factor_run_id": "run-1",
        "promotion_id": "promotion-1",
        "candidate_id": "candidate-1",
        "model_id": "model_train_1",
        "action": "approve_default_model",
        "status": "idempotent_replay",
        "reason": "retry",
        "idempotent": True,
        "request_metadata": {"ticket": "FR-1"},
        "approval_json": {"model_id": "model_train_1"},
        "default_model_json": {"is_default": True},
        "gate_json": {"decision": "approve_model_candidate"},
        "created_at": datetime(2026, 6, 1, 10, 30, 0),
    }

    class FakeMappings:
        def all(self):
            return [audit_row]

    class FakeRowsResult:
        def mappings(self):
            return FakeMappings()

    class FakeCountResult:
        def scalar_one(self):
            return 1

    class FakeSession:
        async def execute(self, statement, params=None):
            seen.append((str(statement), params or {}))
            if "COUNT" in str(statement):
                return FakeCountResult()
            return FakeRowsResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.list_factor_approval_audits(
        "default",
        "user-1",
        training_id="factor-training-1",
        model_id="model_train_1",
        status="idempotent_replay",
    )

    assert result["total"] == 1
    assert result["pagination"]["returned"] == 1
    item = result["items"][0]
    assert item["id"] == "audit-1"
    assert item["trainingId"] == "factor-training-1"
    assert item["modelId"] == "model_train_1"
    assert item["status"] == "idempotent_replay"
    assert item["idempotent"] is True
    assert item["requestMetadata"] == {"ticket": "FR-1"}
    assert item["gate"] == {"decision": "approve_model_candidate"}
    assert seen[0][1]["training_id"] == "factor-training-1"
    assert seen[0][1]["model_id"] == "model_train_1"
    assert seen[0][1]["status"] == "idempotent_replay"


@pytest.mark.asyncio
async def test_create_factor_training_approval_request_is_pending(monkeypatch):
    training_row = {
        "id": "factor-training-1",
        "promotion_id": "promotion-1",
        "candidate_id": "candidate-1",
        "factor_run_id": "run-1",
        "training_run_id": "train-1",
        "status": "completed",
        "feature_key": "factor_alpha",
        "feature_set_version_id": "feature-set-1",
        "request_payload_json": {},
        "response_json": {"runId": "train-1", "status": "completed"},
        "metadata_json": {},
        "created_at": datetime(2026, 6, 1, 9, 0, 0),
        "updated_at": datetime(2026, 6, 1, 9, 0, 0),
        "training_job_status": "completed",
        "training_job_progress": 100,
        "training_job_result": {
            "metrics": {
                "train": {"rmse": 0.12, "auc": 0.61},
                "val": {"rmse": 0.18, "auc": 0.57},
                "test": {"rmse": 0.2, "auc": 0.55},
            },
            "artifacts": [{"name": "model.pkl", "key": "models/train-1/model.pkl"}],
            "model_registration": {"model_id": "model_train_1", "status": "ready"},
        },
        "training_job_logs": "completed",
        "training_job_request_payload": {
            "factor_research": {
                "baseline_metrics": {
                    "train": {"rmse": 0.13, "auc": 0.58},
                    "val": {"rmse": 0.2, "auc": 0.54},
                    "test": {"rmse": 0.24, "auc": 0.52},
                }
            }
        },
        "training_job_updated_at": datetime(2026, 6, 1, 10, 0, 0),
    }
    inserted_row = {
        "id": "approval-request-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "model_id": "model_train_1",
        "status": "pending",
        "requested_by": "user-1",
        "request_reason": "please approve",
        "request_metadata": {"ticket": "FR-2"},
        "reviewer_user_id": None,
        "reviewer_note": None,
        "decision_json": {},
        "reviewed_at": None,
        "created_at": datetime(2026, 6, 1, 10, 30, 0),
        "updated_at": datetime(2026, 6, 1, 10, 30, 0),
    }
    seen: list[tuple[str, dict]] = []

    async def fake_get_factor_training_run_row(
        session, *, tenant_id, user_id, training_id
    ):
        return training_row

    class EmptyMappings:
        def first(self):
            return None

    class InsertMappings:
        def one(self):
            return inserted_row

    class FakeResult:
        def __init__(self, mappings):
            self._mappings = mappings

        def mappings(self):
            return self._mappings

    class FakeSession:
        async def execute(self, statement, params=None):
            seen.append((str(statement), params or {}))
            if "INSERT INTO qm_factor_approval_requests" in str(statement):
                return FakeResult(InsertMappings())
            return FakeResult(EmptyMappings())

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(
        svc, "_get_factor_training_run_row", fake_get_factor_training_run_row
    )
    monkeypatch.setattr(svc, "get_session", fake_get_session)
    notification_calls: list[tuple[str, dict]] = []

    async def fake_notify_request_created(tenant_id, request):
        notification_calls.append((tenant_id, request))
        return {"reviewerCount": 1, "sent": 2}

    monkeypatch.setattr(
        svc,
        "_notify_factor_approval_request_created",
        fake_notify_request_created,
    )

    result = await svc.create_factor_training_approval_request(
        "default",
        "user-1",
        "factor-training-1",
        {"reason": "please approve", "metadata": {"ticket": "FR-2"}},
    )

    assert result["id"] == "approval-request-1"
    assert result["status"] == "pending"
    assert result["modelId"] == "model_train_1"
    assert result["requestMetadata"]["ticket"] == "FR-2"
    insert_params = seen[-1][1]
    assert insert_params["model_id"] == "model_train_1"
    request_metadata = json.loads(insert_params["request_metadata"])
    assert request_metadata["ticket"] == "FR-2"
    assert request_metadata["approval_policy"]["minApprovals"] == 1
    assert result["notification"] == {"reviewerCount": 1, "sent": 2}
    assert notification_calls == [("default", result)]


@pytest.mark.asyncio
async def test_upsert_factor_approval_policy_persists_tenant_policy(monkeypatch):
    policy_row = {
        "tenant_id": "default",
        "enabled": True,
        "allow_direct_approval": False,
        "allow_self_approval": False,
        "min_approvals": 2,
        "reviewer_permission": "factor.approve",
        "metadata_json": {"scope": "committee"},
        "updated_by": "admin-1",
        "created_at": datetime(2026, 6, 1, 10, 0, 0),
        "updated_at": datetime(2026, 6, 1, 10, 5, 0),
    }
    seen: list[tuple[str, dict]] = []

    class EmptyMappings:
        def first(self):
            return None

    class PolicyMappings:
        def one(self):
            return policy_row

        def first(self):
            return policy_row

    class FakeResult:
        def __init__(self, mappings):
            self._mappings = mappings

        def mappings(self):
            return self._mappings

    class FakeSession:
        async def execute(self, statement, params=None):
            text_statement = str(statement)
            seen.append((text_statement, params or {}))
            if "INSERT INTO qm_factor_approval_policies" in text_statement:
                return FakeResult(PolicyMappings())
            return FakeResult(EmptyMappings())

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.upsert_factor_approval_policy(
        "default",
        {
            "allow_direct_approval": False,
            "allow_self_approval": False,
            "min_approvals": 2,
            "metadata": {"scope": "committee"},
        },
        updated_by="admin-1",
    )

    assert result["allowDirectApproval"] is False
    assert result["allowSelfApproval"] is False
    assert result["minApprovals"] == 2
    insert_params = seen[-1][1]
    assert insert_params["allow_direct_approval"] is False
    assert insert_params["allow_self_approval"] is False
    assert insert_params["min_approvals"] == 2
    assert json.loads(insert_params["metadata_json"]) == {"scope": "committee"}


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_approves_as_reviewer(
    monkeypatch,
):
    request_row = {
        "id": "approval-request-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "model_id": "model_train_1",
        "status": "pending",
        "requested_by": "user-1",
        "request_reason": "please approve",
        "request_metadata": {"ticket": "FR-2"},
        "reviewer_user_id": None,
        "reviewer_note": None,
        "decision_json": {},
        "reviewed_at": None,
        "created_at": datetime(2026, 6, 1, 10, 30, 0),
        "updated_at": datetime(2026, 6, 1, 10, 30, 0),
    }
    updated_row = {
        **request_row,
        "status": "approved",
        "reviewer_user_id": "admin-1",
        "reviewer_note": "ok",
        "decision_json": {"status": "approved"},
        "reviewed_at": datetime(2026, 6, 1, 10, 35, 0),
    }
    seen: dict[str, object] = {}

    class SelectMappings:
        def first(self):
            return request_row

    class UpdateMappings:
        def one(self):
            return updated_row

    class FakeResult:
        def __init__(self, mappings):
            self._mappings = mappings

        def mappings(self):
            return self._mappings

    class FakeSession:
        async def execute(self, statement, params=None):
            seen.setdefault("execute", []).append((str(statement), params or {}))
            if "UPDATE qm_factor_approval_requests" in str(statement):
                return FakeResult(UpdateMappings())
            return FakeResult(SelectMappings())

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_approve_factor_training_run(
        tenant_id,
        user_id,
        training_id,
        payload,
        *,
        approver_user_id=None,
    ):
        seen["approval_call"] = (
            tenant_id,
            user_id,
            training_id,
            payload,
            approver_user_id,
        )
        return {
            "approval": {"model_id": "model_train_1", "approved_by": approver_user_id},
            "defaultModel": {"model_id": "model_train_1"},
        }

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(
        svc,
        "approve_factor_training_run",
        fake_approve_factor_training_run,
    )
    monkeypatch.setattr(svc, "get_factor_approval_policy", _default_policy)
    notification_calls: list[tuple[str, dict]] = []

    async def fake_notify_reviewed(tenant_id, request):
        notification_calls.append((tenant_id, request))
        return True

    monkeypatch.setattr(
        svc,
        "_notify_factor_approval_request_reviewed",
        fake_notify_reviewed,
    )

    result = await svc.review_factor_training_approval_request(
        "default",
        "approval-request-1",
        "admin-1",
        {"approve": True, "reviewer_note": "ok", "metadata": {"review": "ops"}},
    )

    assert result["request"]["status"] == "approved"
    assert result["request"]["reviewerUserId"] == "admin-1"
    assert result["approvalResult"]["approval"]["approved_by"] == "admin-1"
    approval_call = seen["approval_call"]
    assert approval_call[1] == "user-1"
    assert approval_call[2] == "factor-training-1"
    assert approval_call[4] == "admin-1"
    assert approval_call[3]["metadata"]["approval_request_id"] == "approval-request-1"
    assert notification_calls == [("default", result["request"])]


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_waits_for_min_approvals(
    monkeypatch,
):
    request_row = {
        "id": "approval-request-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "model_id": "model_train_1",
        "status": "pending",
        "requested_by": "user-1",
        "request_reason": "please approve",
        "request_metadata": {"ticket": "FR-2"},
        "reviewer_user_id": None,
        "reviewer_note": None,
        "decision_json": {},
        "reviewed_at": None,
        "created_at": datetime(2026, 6, 1, 10, 30, 0),
        "updated_at": datetime(2026, 6, 1, 10, 30, 0),
    }
    updated_row = {
        **request_row,
        "reviewer_user_id": "reviewer-1",
        "reviewer_note": "first ok",
        "decision_json": {"status": "pending"},
        "updated_at": datetime(2026, 6, 1, 10, 35, 0),
    }
    seen: dict[str, object] = {"updates": []}

    class SelectMappings:
        def first(self):
            return request_row

    class UpdateMappings:
        def one(self):
            return updated_row

    class FakeResult:
        def __init__(self, mappings):
            self._mappings = mappings

        def mappings(self):
            return self._mappings

    class FakeSession:
        async def execute(self, statement, params=None):
            seen["updates"].append((str(statement), params or {}))
            if "UPDATE qm_factor_approval_requests" in str(statement):
                return FakeResult(UpdateMappings())
            return FakeResult(SelectMappings())

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_policy(tenant_id):
        policy = svc._default_factor_approval_policy(tenant_id)
        policy["minApprovals"] = 2
        return policy

    async def fail_approve(*args, **kwargs):
        raise AssertionError("first approval must not set default model")

    async def fail_notify(*args, **kwargs):
        raise AssertionError("partial approval must not notify final result")

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "get_factor_approval_policy", fake_policy)
    monkeypatch.setattr(svc, "approve_factor_training_run", fail_approve)
    monkeypatch.setattr(svc, "_notify_factor_approval_request_reviewed", fail_notify)

    result = await svc.review_factor_training_approval_request(
        "default",
        "approval-request-1",
        "reviewer-1",
        {"approve": True, "reviewer_note": "first ok"},
    )

    assert result["request"]["status"] == "pending"
    assert result["approvalResult"] is None
    update_params = seen["updates"][-1][1]
    assert update_params["status"] == "pending"
    decision = json.loads(update_params["decision_json"])
    assert decision["requiredApprovals"] == 2
    assert decision["approvals"][0]["reviewed_by"] == "reviewer-1"


@pytest.mark.asyncio
async def test_review_factor_training_approval_request_rejects_self_approval_policy(
    monkeypatch,
):
    request_row = {
        "id": "approval-request-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "training_id": "factor-training-1",
        "model_id": "model_train_1",
        "status": "pending",
        "requested_by": "user-1",
        "request_reason": "please approve",
        "request_metadata": {},
        "reviewer_user_id": None,
        "reviewer_note": None,
        "decision_json": {},
        "reviewed_at": None,
        "created_at": datetime(2026, 6, 1, 10, 30, 0),
        "updated_at": datetime(2026, 6, 1, 10, 30, 0),
    }

    class SelectMappings:
        def first(self):
            return request_row

    class FakeResult:
        def mappings(self):
            return SelectMappings()

    class FakeSession:
        async def execute(self, statement, params=None):
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    async def fake_policy(tenant_id):
        policy = svc._default_factor_approval_policy(tenant_id)
        policy["allowSelfApproval"] = False
        return policy

    monkeypatch.setattr(svc, "get_session", fake_get_session)
    monkeypatch.setattr(svc, "get_factor_approval_policy", fake_policy)

    with pytest.raises(ValueError, match="rejects self approval"):
        await svc.review_factor_training_approval_request(
            "default",
            "approval-request-1",
            "user-1",
            {"approve": True},
        )


@pytest.mark.asyncio
async def test_factor_approval_request_created_notification_fans_out(monkeypatch):
    sent: list[dict[str, object]] = []

    async def fake_list_reviewers(tenant_id, *, exclude_user_id=None, limit=50):
        assert tenant_id == "default"
        assert exclude_user_id == "user-1"
        assert limit == 50
        return ["admin-1", "reviewer-1"]

    async def fake_publish(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(
        svc, "_list_factor_approval_reviewer_user_ids", fake_list_reviewers
    )
    monkeypatch.setattr(svc, "_publish_factor_notification", fake_publish)

    result = await svc._notify_factor_approval_request_created(
        "default",
        {
            "userId": "user-1",
            "modelId": "model_train_1",
            "trainingId": "factor-training-1",
        },
    )

    assert result == {"reviewerCount": 2, "sent": 3}
    assert [item["user_id"] for item in sent] == ["user-1", "admin-1", "reviewer-1"]
    assert sent[0]["title"] == "因子模型审批请求已提交"
    assert sent[1]["title"] == "新的因子模型审批请求"


@pytest.mark.asyncio
async def test_factor_approval_review_notification_targets_requester(monkeypatch):
    sent: list[dict[str, object]] = []

    async def fake_publish(**kwargs):
        sent.append(kwargs)
        return True

    monkeypatch.setattr(svc, "_publish_factor_notification", fake_publish)

    ok = await svc._notify_factor_approval_request_reviewed(
        "default",
        {
            "userId": "user-1",
            "modelId": "model_train_1",
            "reviewerUserId": "reviewer-1",
            "status": "rejected",
        },
    )

    assert ok is True
    assert sent == [
        {
            "tenant_id": "default",
            "user_id": "user-1",
            "title": "因子模型审批已拒绝",
            "content": "模型 model_train_1 的默认模型审批已拒绝，审核人 reviewer-1。",
            "level": "warning",
        }
    ]


def test_shadow_stream_publish_requires_explicit_allow_flag():
    assert svc._resolve_shadow_stream_publish({"publish_stream": False}) is False
    assert (
        svc._resolve_shadow_stream_publish(
            {"publish_stream": True, "allow_shadow_stream": True}
        )
        is True
    )
    with pytest.raises(ValueError, match="allow_shadow_stream=true"):
        svc._resolve_shadow_stream_publish({"publish_stream": True})


def test_publish_factor_shadow_signal_stream_writes_stream_and_latest_key():
    class FakeRedis:
        def __init__(self):
            self.stream_events: list[tuple[str, dict, int, bool]] = []
            self.latest: dict[str, tuple[str, int]] = {}

        def xadd(self, stream, payload, maxlen, approximate):
            self.stream_events.append((stream, payload, maxlen, approximate))
            return "1-1"

        def set(self, key, value, ex):
            self.latest[key] = (value, ex)
            return True

    fake_redis = FakeRedis()

    count = svc._publish_factor_shadow_signal_stream(
        tenant_id="default",
        user_id="u1",
        signal_run_id="signal-run-1",
        enabled=True,
        redis_client=fake_redis,
        signals=[
            {
                "signal_id": "sig-1",
                "client_order_id": "coid-1",
                "symbol": "SH600519",
                "side": "BUY",
                "trade_action": "buy_to_open",
                "position_side": "long",
                "is_margin_trade": False,
                "quantity": 100,
                "price": 0.0,
                "score": 0.8,
                "trade_date": "2026-06-01",
            }
        ],
    )

    assert count == 1
    assert fake_redis.stream_events[0][0] == "qm:signal:stream:default"
    assert fake_redis.stream_events[0][1]["signal_source"] == "factor_shadow"
    assert fake_redis.stream_events[0][1]["symbol"] == "SH600519"
    assert fake_redis.latest["qm:signal:latest:default:u1"] == ("signal-run-1", 86400)


@pytest.mark.asyncio
async def test_activate_feature_set_without_feature_excludes_rolled_back_factor():
    captured_params: list[dict] = []

    class FakeSession:
        async def execute(self, statement, params=None):
            if params:
                captured_params.append(params)

    version_id = await svc._activate_feature_set_without_feature(
        FakeSession(),
        feature_key="factor_alpha",
        promotion_id="promotion-rollback-1",
        reason="bad_shadow_metrics",
        base_items=[
            {
                "category_id": "base",
                "category_name": "基础特征",
                "category_order": 1,
                "feature_id": "feat_mom",
                "feature_key": "mom_ret_1d",
                "feature_name": "1日动量",
                "formula": "close / pre_close - 1",
                "source_table_fields": "market_data_daily",
                "enabled": True,
                "order_no": 1,
                "metadata": {},
            },
            {
                "category_id": "factor_research",
                "category_name": "因子研究",
                "category_order": 900,
                "feature_id": "feat_factor_alpha",
                "feature_key": "factor_alpha",
                "feature_name": "alpha",
                "formula": "rank(close)",
                "source_table_fields": "qm_factor_values",
                "enabled": True,
                "order_no": 2,
                "metadata": {"source": "factor_research"},
            },
        ],
    )

    inserted_feature_keys = [
        params.get("feature_key")
        for params in captured_params
        if params.get("version_id") == version_id and "feature_key" in params
    ]
    metadata_payloads = [
        params["metadata_json"]
        for params in captured_params
        if "metadata_json" in params
    ]

    assert version_id == "factor_rollback_promotionrol"
    assert inserted_feature_keys == ["mom_ret_1d"]
    assert "factor_alpha" not in inserted_feature_keys
    assert any("bad_shadow_metrics" in payload for payload in metadata_payloads)


def test_split_training_dates_rejects_invalid_explicit_order():
    with pytest.raises(ValueError, match="strictly increasing"):
        svc._split_training_dates(
            date(2026, 1, 1),
            date(2026, 6, 1),
            {
                "train_start": "2026-01-01",
                "train_end": "2026-03-01",
                "valid_start": "2026-02-01",
                "valid_end": "2026-04-01",
                "test_start": "2026-04-02",
                "test_end": "2026-06-01",
            },
        )


def test_safe_table_name_rejects_sql_injection():
    assert svc._safe_table_name("stock_daily_latest") == "stock_daily_latest"
    with pytest.raises(ValueError, match="invalid factor research data table"):
        svc._safe_table_name("stock_daily_latest;DROP TABLE users")


def test_local_market_data_adapter_contract_is_local_ohlcv_only():
    contract = market_adapter.local_market_data_contract("stock_daily_latest")
    base_sql = market_adapter.build_local_ohlcv_base_cte("stock_daily_latest")

    assert contract.source == "local_stock_daily_latest"
    assert contract.required_columns == (
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )
    assert "FROM stock_daily_latest" in base_sql
    assert "AS amount" in base_sql
    assert "AS vwap" in base_sql
    assert "open::double precision AS open" in base_sql
    assert "high::double precision AS high" in base_sql
    assert "low::double precision AS low" in base_sql
    assert "close::double precision AS close" in base_sql
    assert "volume::double precision AS volume" in base_sql
    assert "http" not in base_sql.lower()
    assert "akshare" not in base_sql.lower()


def test_local_market_data_adapter_prefixes_suffix_stock_codes():
    symbol_sql = market_adapter.prefix_symbol_sql("symbol")

    assert "'SH' || LEFT(symbol, 6)" in symbol_sql
    assert "'SZ' || LEFT(symbol, 6)" in symbol_sql
    assert "'BJ' || LEFT(symbol, 6)" in symbol_sql
    assert "^[0-9]{6}" in symbol_sql
    with pytest.raises(ValueError, match="invalid symbol column"):
        market_adapter.prefix_symbol_sql("symbol);DROP")


def test_safe_feature_key_normalizes_and_rejects_invalid_values():
    assert svc._safe_feature_key("Factor Alpha-01") == "factor_alpha_01"
    with pytest.raises(ValueError, match="invalid feature key"):
        svc._safe_feature_key("1bad")


def test_factor_feature_id_is_derived_from_final_feature_key():
    assert svc._factor_feature_id("factor_d73368561c9307f9") == (
        "feat_factor_d73368561c9307f9"
    )
    assert svc._factor_feature_id("factor_live_smoke_123") == (
        "feat_factor_live_smoke_123"
    )


def test_fallback_feature_catalog_items_are_available():
    items = svc._load_fallback_feature_catalog_items()

    assert items
    assert any(item["feature_key"] == "mom_ret_1d" for item in items)
    assert all(item["category_id"] for item in items)


def test_feature_snapshot_materialization_reports_missing_dir(monkeypatch, tmp_path):
    missing_dir = tmp_path / "missing"
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", missing_dir)

    result = svc._check_feature_snapshot_materialization("factor_alpha")

    assert result["status"] == "pending_materialization"
    assert result["reason"] == "feature_snapshot_dir_missing"


def test_snapshot_symbol_key_normalizes_supported_formats():
    assert svc._snapshot_symbol_key("SH600002") == "600002"
    assert svc._snapshot_symbol_key("600002.SH") == "600002"
    assert svc._snapshot_symbol_key("SZ000009") == "000009"
    assert svc._snapshot_symbol_key("9") == "000009"


def test_materialize_feature_values_to_existing_snapshot(monkeypatch, tmp_path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "model_features_2026.parquet"
    pd.DataFrame(
        {
            "trade_date": ["2026-01-01", "2026-01-01", "2026-01-02"],
            "symbol": ["600002", "000009", "600002"],
            "open": [1.0, 2.0, 3.0],
        }
    ).to_parquet(snapshot_path, index=False, engine="pyarrow")
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)

    result = svc._materialize_feature_values_to_snapshots(
        feature_key="factor_alpha",
        values=[
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SH600002",
                "factor_value": 0.25,
            },
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SZ000009",
                "factor_value": 0.75,
            },
        ],
    )
    updated = pd.read_parquet(snapshot_path, engine="pyarrow")

    assert result["status"] == "materialized"
    assert result["updated_rows"] == 2
    assert "factor_alpha" in updated.columns
    assert updated.loc[updated["symbol"] == "600002", "factor_alpha"].iloc[
        0
    ] == pytest.approx(0.25)
    assert updated.loc[updated["symbol"] == "000009", "factor_alpha"].iloc[
        0
    ] == pytest.approx(0.75)
    assert pd.isna(
        updated.loc[updated["trade_date"] == "2026-01-02", "factor_alpha"].iloc[0]
    )


def test_materialize_feature_values_creates_baseline_snapshot(monkeypatch, tmp_path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)

    result = svc._materialize_feature_values_to_snapshots(
        feature_key="factor_alpha",
        values=[
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SH600002",
                "factor_value": 0.25,
            },
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SZ000009",
                "factor_value": 0.75,
            },
        ],
        base_rows=[
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SH600002",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SZ000009",
                "open": 20,
                "high": 21,
                "low": 19,
                "close": 20.5,
                "volume": 2000,
            },
        ],
    )

    snapshot_path = snapshot_dir / "model_features_2026.parquet"
    created = pd.read_parquet(snapshot_path, engine="pyarrow")

    assert result["status"] == "materialized"
    assert result["reason"] == "baseline_snapshots_created_from_local_market_data"
    assert result["updated_rows"] == 2
    assert result["created_baseline_files"] == 1
    assert {
        "trade_date",
        "symbol",
        "open",
        "close",
        "volume",
        "factor_alpha",
    }.issubset(created.columns)
    assert created["symbol"].tolist() == ["000009", "600002"]
    assert created.loc[created["symbol"] == "600002", "factor_alpha"].iloc[
        0
    ] == pytest.approx(0.25)


def test_materialize_feature_values_reports_missing_baseline_data(
    monkeypatch, tmp_path
):
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)

    result = svc._materialize_feature_values_to_snapshots(
        feature_key="factor_alpha",
        values=[
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SH600002",
                "factor_value": 0.25,
            },
        ],
    )

    assert result["status"] == "pending_materialization"
    assert result["reason"] == "feature_snapshot_dir_missing"


def test_materialize_feature_values_creates_baseline_snapshot_from_qlib(
    monkeypatch, tmp_path
):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    provider_uri = tmp_path / "qlib_data"
    provider_uri.mkdir()
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)
    monkeypatch.setenv("FACTOR_RESEARCH_QLIB_PROVIDER_URI", str(provider_uri))

    qlib_frame = pd.DataFrame(
        [
            {"$open": 10, "$high": 11, "$low": 9, "$close": 10.5, "$volume": 1000},
            {"$open": 20, "$high": 21, "$low": 19, "$close": 20.5, "$volume": 2000},
            {"$open": 30, "$high": 31, "$low": 29, "$close": 30.5, "$volume": 3000},
        ],
        index=pd.MultiIndex.from_tuples(
            [
                ("SH600002", pd.Timestamp("2026-01-01")),
                ("SZ000009", pd.Timestamp("2026-01-01")),
                ("SH600003", pd.Timestamp("2026-01-01")),
            ],
            names=["instrument", "datetime"],
        ),
    )

    class FakeD:
        @staticmethod
        def instruments(name):
            return name

        @staticmethod
        def list_instruments(_pool, as_list=False):
            return ["SH600002", "SZ000009", "SH600003"]

        @staticmethod
        def features(_requested, _fields, start_time=None, end_time=None):
            assert start_time == "2026-01-01"
            assert end_time == "2026-01-01"
            return qlib_frame

    monkeypatch.setitem(
        sys.modules, "qlib", types.SimpleNamespace(init=lambda **_: None)
    )
    monkeypatch.setitem(sys.modules, "qlib.data", types.SimpleNamespace(D=FakeD))

    result = svc._materialize_feature_values_to_snapshots(
        feature_key="factor_alpha",
        values=[
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SH600002",
                "factor_value": 0.25,
            },
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SZ000009",
                "factor_value": 0.75,
            },
        ],
    )

    snapshot_path = snapshot_dir / "model_features_2026.parquet"
    created = pd.read_parquet(snapshot_path, engine="pyarrow")

    assert result["status"] == "materialized"
    assert result["reason"] == "baseline_snapshots_created_from_qlib_provider"
    assert result["updated_rows"] == 2
    assert result["created_baseline_files"] == 1
    assert result["files"][0]["base_source"] == "qlib_provider"
    assert created["symbol"].tolist() == ["000009", "600002"]
    assert created.loc[created["symbol"] == "600002", "factor_alpha"].iloc[
        0
    ] == pytest.approx(0.25)


def test_feature_snapshot_factor_values_use_training_snapshot_ohlcv(
    monkeypatch, tmp_path
):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    snapshot_dir.mkdir()
    snapshot_path = snapshot_dir / "model_features_2026.parquet"
    rows = []
    for day in range(1, 13):
        for idx, symbol in enumerate(
            ["600001", "600002", "600003", "000001", "000002", "000003"],
            start=1,
        ):
            rows.append(
                {
                    "trade_date": f"2026-01-{day:02d}",
                    "symbol": symbol,
                    "open": 10 + idx + day * 0.1,
                    "high": 11 + idx + day * 0.1,
                    "low": 9 + idx + day * 0.1,
                    "close": 10
                    + idx * 0.7
                    + day * (0.02 * idx)
                    + ((day * idx) % 7) * 0.13,
                    "volume": 1000 + day * idx + ((day + idx) % 5) * 11,
                }
            )
    pd.DataFrame(rows).to_parquet(snapshot_path, index=False, engine="pyarrow")
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)

    loaded = svc._load_feature_snapshot_ohlcv_frame(date(2026, 1, 1), date(2026, 1, 12))
    assert loaded["status"] == "loaded"
    for expression in [
        "rank(close / ts_mean(close, 3))",
        "rank(volume / ts_mean(volume, 3))",
        "rank(ts_delta(close, 3) / ts_shift(close, 3))",
        "rank(tanh(ts_delta(close, 3) / ts_shift(close, 3)))",
        "rank(ts_std(close, 3))",
        "rank(ts_corr(rank(close), rank(volume), 3))",
        "rank((close / ts_mean(close, 3)) * (ts_delta(close, 3) / ts_shift(close, 3)))",
        "rank(amount / ts_mean(amount, 3))",
        "rank(vwap / ts_mean(vwap, 3))",
        "rank(ts_rank(close, 3))",
        "rank(decay_linear(close, 3))",
        "rank(zscore(close, 3))",
        "rank(scale(volume))",
        "rank(where(close > ts_mean(close, 3), close / ts_mean(close, 3), 0))",
    ]:
        factor_data = svc._calculate_feature_snapshot_factor_values(
            frame=loaded["frame"],
            expression=expression,
            holding_period=2,
        )

        assert factor_data["status"] == "loaded", expression
        assert factor_data["metrics"]["inserted_values"] == len(factor_data["rows"])
        assert factor_data["rows"], expression
        assert {row["symbol"][:2] for row in factor_data["rows"]} == {"SH", "SZ"}


def test_quantgpt_runner_market_frame_derives_required_columns_from_ohlcv():
    pd = pytest.importorskip("pandas")
    frame = pd.DataFrame(
        [
            {
                "trade_date": "2026-01-01",
                "symbol": "SH600001",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.0,
                "volume": 1000,
            },
            {
                "trade_date": "2026-01-02",
                "symbol": "600001.SH",
                "open": 10.5,
                "high": 11.5,
                "low": 10.0,
                "close": 11.0,
                "volume": 1200,
            },
            {
                "trade_date": "2026-01-01",
                "symbol": "SZ000001",
                "open": 20.0,
                "high": 21.0,
                "low": 19.0,
                "close": 20.0,
                "volume": 2000,
            },
        ]
    )

    result = svc._build_quantgpt_runner_market_frame(
        frame,
        source="unit_test_ohlcv",
    )
    runner_frame = result["frame"]

    assert result["status"] == "loaded"
    assert result["row_count"] == 3
    assert result["stock_count"] == 2
    assert list(runner_frame.columns) == [
        "trade_date",
        "stock_code",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "pct_change",
    ]
    assert runner_frame["stock_code"].tolist() == [
        "sh.600001",
        "sh.600001",
        "sz.000001",
    ]
    second_row = runner_frame.iloc[1]
    assert second_row["amount"] == pytest.approx(11.0 * 1200)
    assert second_row["pct_change"] == pytest.approx(10.0)
    assert runner_frame.iloc[0]["pct_change"] == pytest.approx(0.0)


def test_load_qlib_quantgpt_runner_input_uses_qlib_provider_contract(
    monkeypatch, tmp_path
):
    pd = pytest.importorskip("pandas")
    provider_uri = tmp_path / "qlib_data"
    provider_uri.mkdir()
    monkeypatch.setenv("FACTOR_RESEARCH_QLIB_PROVIDER_URI", str(provider_uri))
    qlib_frame = pd.DataFrame(
        [
            {"$open": 10, "$high": 11, "$low": 9, "$close": 10, "$volume": 1000},
            {"$open": 12, "$high": 13, "$low": 11, "$close": 12, "$volume": 1200},
            {"$open": 20, "$high": 21, "$low": 19, "$close": 20, "$volume": 2000},
        ],
        index=pd.MultiIndex.from_tuples(
            [
                ("SH600001", pd.Timestamp("2026-01-01")),
                ("SH600001", pd.Timestamp("2026-01-02")),
                ("SZ000001", pd.Timestamp("2026-01-01")),
            ],
            names=["instrument", "datetime"],
        ),
    )

    class FakeD:
        @staticmethod
        def instruments(name):
            return name

        @staticmethod
        def list_instruments(_pool, as_list=False):
            return ["SH600001", "SZ000001"]

        @staticmethod
        def features(_requested, _fields, start_time=None, end_time=None):
            assert _fields == ["$open", "$high", "$low", "$close", "$volume"]
            assert start_time == "2026-01-01"
            assert end_time == "2026-01-02"
            return qlib_frame

    monkeypatch.setitem(
        sys.modules, "qlib", types.SimpleNamespace(init=lambda **_: None)
    )
    monkeypatch.setitem(sys.modules, "qlib.data", types.SimpleNamespace(D=FakeD))

    result = svc._load_qlib_quantgpt_runner_input(
        date(2026, 1, 1),
        date(2026, 1, 2),
    )
    runner_frame = result["frame"]

    assert result["status"] == "loaded"
    assert result["reason"] == "quantgpt_runner_input_loaded"
    assert result["source"] == "qlib_provider"
    assert result["instrument_count"] == 2
    assert runner_frame["stock_code"].tolist() == [
        "sh.600001",
        "sh.600001",
        "sz.000001",
    ]
    assert runner_frame.iloc[1]["pct_change"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_load_local_snapshot_base_rows_passes_factor_keys_json():
    executions: list[tuple[str, dict]] = []

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeResult:
        def __init__(self, *, scalar=None, rows=None):
            self.scalar = scalar
            self.rows = rows or []

        def scalar_one(self):
            return self.scalar

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            params = params or {}
            executions.append((str(statement), params))
            if "to_regclass" in str(statement):
                return FakeResult(scalar="stock_daily_latest")
            keys = json.loads(params["keys_json"])
            assert keys == [
                {"trade_date": "2026-01-01", "symbol": "SH600002"},
                {"trade_date": "2026-01-01", "symbol": "SZ000009"},
            ]
            return FakeResult(
                rows=[
                    {
                        "trade_date": date(2026, 1, 1),
                        "symbol": "SH600002",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.0,
                        "close": 10.5,
                        "volume": 1000.0,
                    }
                ]
            )

    result = await svc._load_local_snapshot_base_rows_for_factor_values(
        FakeSession(),
        [
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "600002.SH",
                "factor_value": 0.25,
            },
            {
                "trade_date": date(2026, 1, 1),
                "symbol": "SZ000009",
                "factor_value": 0.75,
            },
        ],
    )

    assert result["status"] == "loaded"
    assert result["requested_keys"] == 2
    assert result["row_count"] == 1
    assert executions[1][1]["keys_json"] != "[]"


def test_factor_values_cte_keeps_stock_code_regex_quantifier():
    sql = svc._build_factor_values_cte("stock_daily_latest", "close")

    assert "^[0-9]{6}" in sql
    assert "^[0-9]6" not in sql
    assert "open::double precision AS open" in sql
    assert "high::double precision AS high" in sql
    assert "low::double precision AS low" in sql
    assert "FROM base AS b" in sql


@pytest.mark.asyncio
async def test_upsert_factor_values_normalizes_and_filters_rows():
    captured: dict[str, object] = {}

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def one(self):
            return self.rows[0]

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            captured["params"] = params or {}
            values = json.loads(captured["params"]["values_json"])
            return FakeResult(
                [{"inserted_values": len(values), "invalid_symbol_count": 1}]
            )

    result = await factor_value_store.upsert_factor_values(
        FakeSession(),
        tenant_id="tenant",
        user_id="user",
        candidate_id="candidate-1",
        run_id="run-1",
        rows=[
            {"trade_date": "2026-01-01", "symbol": "600001.SH", "factor_value": 0.1},
            {"trade_date": "2026-01-01", "symbol": "000001", "factor_value": 0.2},
            {"trade_date": "2026-01-01", "symbol": "BAD", "factor_value": 0.3},
            {"trade_date": "2026-01-01", "symbol": "SH600002", "factor_value": None},
        ],
        source="unit",
    )

    values = json.loads(captured["params"]["values_json"])
    assert result == {
        "inserted_values": 2,
        "invalid_symbol_count": 1,
        "source": "unit",
    }
    assert [row["symbol"] for row in values] == ["SH600001", "SZ000001"]
    assert "ON CONFLICT (run_id, trade_date, symbol)" in captured["sql"]


@pytest.mark.asyncio
async def test_list_factor_run_values_returns_summary_and_items(monkeypatch):
    captured: list[dict] = []

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def one(self):
            return self.rows[0]

        def all(self):
            return self.rows

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            captured.append(params)
            if "FROM qm_factor_candidate_runs" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "completed",
                            "params_json": {"holding_period": 5},
                            "metrics_json": {"inserted_values": 2},
                            "gate_decision_json": {"eligible": True},
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "COUNT(*) AS total" in sql:
                return FakeResult(
                    [
                        {
                            "total": 2,
                            "trade_date_count": 1,
                            "symbol_count": 2,
                            "min_trade_date": date(2026, 1, 1),
                            "max_trade_date": date(2026, 1, 1),
                            "min_factor_value": 0.1,
                            "max_factor_value": 0.9,
                            "null_value_count": 1,
                            "invalid_symbol_count": 1,
                            "source_count": 2,
                        }
                    ]
                )
            if "SELECT DISTINCT symbol" in sql:
                return FakeResult([{"symbol": "600001.SH"}])
            if "GROUP BY COALESCE(source, 'unknown')" in sql:
                return FakeResult(
                    [
                        {"source": "local_stock_daily_latest", "count": 2},
                        {"source": "feature_snapshot", "count": 1},
                    ]
                )
            if "GROUP BY trade_date" in sql:
                return FakeResult([{"trade_date": date(2026, 1, 1), "count": 2}])
            return FakeResult(
                [
                    {
                        "candidate_id": "candidate-1",
                        "run_id": "run-1",
                        "trade_date": date(2026, 1, 1),
                        "symbol": "SH600001",
                        "factor_value": 0.1,
                        "source": "local_stock_daily_latest",
                        "created_at": None,
                    },
                    {
                        "candidate_id": "candidate-1",
                        "run_id": "run-1",
                        "trade_date": date(2026, 1, 1),
                        "symbol": "SZ000001",
                        "factor_value": 0.9,
                        "source": "local_stock_daily_latest",
                        "created_at": None,
                    },
                ]
            )

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(factor_value_store, "get_session", fake_get_session)

    result = await factor_value_store.list_factor_run_values(
        "tenant", "user", "run-1", limit=5000, offset=-10
    )

    assert result["run"]["id"] == "run-1"
    assert result["summary"] == {
        "total": 2,
        "tradeDateCount": 1,
        "symbolCount": 2,
        "minTradeDate": "2026-01-01",
        "maxTradeDate": "2026-01-01",
        "minFactorValue": 0.1,
        "maxFactorValue": 0.9,
        "nullValueCount": 1,
        "invalidSymbolCount": 1,
        "sourceCount": 2,
        "invalidSymbolSamples": ["600001.SH"],
        "sourceDistribution": [
            {"source": "local_stock_daily_latest", "count": 2},
            {"source": "feature_snapshot", "count": 1},
        ],
        "recentDateDistribution": [{"tradeDate": "2026-01-01", "count": 2}],
    }
    assert result["pagination"] == {
        "limit": 1000,
        "offset": 0,
        "returned": 2,
        "hasMore": False,
    }
    assert result["items"][0]["symbol"] == "SH600001"
    assert captured[-1]["limit"] == 1000
    assert captured[-1]["offset"] == 0


@pytest.mark.asyncio
async def test_api_list_factor_run_values_delegates_to_engine_store(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_engine_list_values(
        tenant_id,
        user_id,
        run_id,
        *,
        limit=100,
        offset=0,
    ):
        captured.update(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "run_id": run_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return {"items": [{"symbol": "SH600001"}], "total": 1}

    monkeypatch.setattr(
        factor_value_store,
        "list_factor_run_values",
        fake_engine_list_values,
    )

    result = await svc.list_factor_run_values(
        "tenant",
        "user",
        "run-1",
        limit=7,
        offset=2,
    )

    assert captured == {
        "tenant_id": "tenant",
        "user_id": "user",
        "run_id": "run-1",
        "limit": 7,
        "offset": 2,
    }
    assert result == {"items": [{"symbol": "SH600001"}], "total": 1}


@pytest.mark.asyncio
async def test_get_factor_campaign_returns_candidate_history(monkeypatch):
    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def all(self):
            return self.rows

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return FakeMappings(self.rows)

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "FROM qm_factor_campaigns" in sql:
                return FakeResult(
                    [
                        {
                            "id": "campaign-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "name": "auto mining",
                            "strategy": "template_mutation",
                            "status": "completed",
                            "seed_expression": "rank(close)",
                            "params_json": {"n_candidates": 2},
                            "summary_json": {"totalCandidates": 2},
                            "metadata_json": {"quota": {}},
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            if "FROM qm_factor_campaign_items" in sql:
                return FakeResult(
                    [
                        {
                            "campaign_id": "campaign-1",
                            "candidate_id": "candidate-1",
                            "run_id": "run-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "generation": 1,
                            "rank_no": 1,
                            "expression": "rank(close)",
                            "status": "completed",
                            "score": 0.1234,
                            "reason": "eligible",
                            "metrics_json": {"rank_ic_mean": 0.1234},
                            "metadata_json": {"operator": "seed"},
                            "created_at": None,
                            "updated_at": None,
                        },
                        {
                            "campaign_id": "campaign-1",
                            "candidate_id": "candidate-2",
                            "run_id": "run-2",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "generation": 1,
                            "rank_no": 2,
                            "expression": "rank(volume)",
                            "status": "failed",
                            "score": None,
                            "reason": "insufficient_coverage",
                            "metrics_json": {},
                            "metadata_json": {"operator": "mutation"},
                            "created_at": None,
                            "updated_at": None,
                        },
                    ]
                )
            raise AssertionError(f"unexpected SQL: {sql}")

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.get_factor_campaign("tenant", "user", "campaign-1")

    assert result["id"] == "campaign-1"
    assert result["items"] == [
        {
            "campaignId": "campaign-1",
            "candidateId": "candidate-1",
            "runId": "run-1",
            "generation": 1,
            "rankNo": 1,
            "expression": "rank(close)",
            "status": "completed",
            "score": 0.1234,
            "reason": "eligible",
            "metrics": {"rank_ic_mean": 0.1234},
            "metadata": {"operator": "seed"},
            "createdAt": None,
            "updatedAt": None,
        },
        {
            "campaignId": "campaign-1",
            "candidateId": "candidate-2",
            "runId": "run-2",
            "generation": 1,
            "rankNo": 2,
            "expression": "rank(volume)",
            "status": "failed",
            "score": None,
            "reason": "insufficient_coverage",
            "metrics": {},
            "metadata": {"operator": "mutation"},
            "createdAt": None,
            "updatedAt": None,
        },
    ]


def test_date_or_none_accepts_api_string_and_date_objects():
    assert svc._date_or_none("2026-01-02") == date(2026, 1, 2)
    assert svc._date_or_none(datetime(2026, 1, 2, 9, 30)).isoformat() == "2026-01-02"
    assert svc._date_or_none("not-a-date") is None


@pytest.mark.asyncio
async def test_evaluate_factor_run_locally_marks_missing_data_table_failed(
    monkeypatch, tmp_path
):
    statements: list[str] = []
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", tmp_path / "missing_snapshots")

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

    class FakeResult:
        def __init__(self, rows=None, scalar=None):
            self.rows = rows or []
            self.scalar = scalar

        def mappings(self):
            return FakeMappings(self.rows)

        def scalar_one(self):
            return self.scalar

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            statements.append(sql)
            if "JOIN qm_factor_candidates" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "pending",
                            "params_json": {
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-31",
                                "holding_period": 5,
                            },
                            "metrics_json": None,
                            "gate_decision_json": {},
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                            "expression": "rank(close / ts_mean(close, 20))",
                            "factor_candidate_id": "candidate-1",
                        }
                    ]
                )
            if "to_regclass" in sql:
                return FakeResult(scalar=None)
            if "SELECT *" in sql and "FROM qm_factor_candidate_runs" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "failed",
                            "params_json": {},
                            "metrics_json": None,
                            "gate_decision_json": {
                                "eligible": False,
                                "reasons": ["data_table_missing"],
                                "policy": "default",
                            },
                            "report_url": None,
                            "error_message": "data_table_missing:stock_daily_latest",
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.evaluate_factor_run_locally("tenant", "user", "run-1")

    assert result["status"] == "failed"
    assert result["errorMessage"] == "data_table_missing:stock_daily_latest"
    assert result["gateDecision"]["reasons"] == ["data_table_missing"]
    assert any("SET status = 'rejected'" in sql for sql in statements)


@pytest.mark.asyncio
async def test_evaluate_factor_run_locally_falls_back_to_feature_snapshot(
    monkeypatch, tmp_path
):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    snapshot_dir = tmp_path / "feature_snapshots"
    snapshot_dir.mkdir()
    rows = []
    for day in range(1, 20):
        for idx, symbol in enumerate(
            ["600001", "600002", "600003", "000001", "000002", "000003"],
            start=1,
        ):
            rows.append(
                {
                    "trade_date": f"2026-01-{day:02d}",
                    "symbol": symbol,
                    "open": 10 + idx,
                    "high": 11 + idx,
                    "low": 9 + idx,
                    "close": 10
                    + idx * 0.7
                    + day * (0.02 * idx)
                    + ((day * idx) % 7) * 0.13,
                    "volume": 1000 + day,
                }
            )
    pd.DataFrame(rows).to_parquet(
        snapshot_dir / "model_features_2026.parquet",
        index=False,
        engine="pyarrow",
    )
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", snapshot_dir)
    captured: dict[str, dict] = {}

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def one(self):
            return self.rows[0]

    class FakeResult:
        def __init__(self, rows=None, scalar=None):
            self.rows = rows or []
            self.scalar = scalar

        def mappings(self):
            return FakeMappings(self.rows)

        def scalar_one(self):
            return self.scalar

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "JOIN qm_factor_candidates" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "pending",
                            "params_json": {
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-19",
                                "holding_period": 2,
                            },
                            "metrics_json": None,
                            "gate_decision_json": {},
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                            "expression": "rank(close / ts_mean(close, 3))",
                            "factor_candidate_id": "candidate-1",
                        }
                    ]
                )
            if "to_regclass" in sql:
                return FakeResult(scalar=None)
            if "INSERT INTO qm_factor_values" in sql:
                captured["insert"] = params
                rows = json.loads(params["values_json"])
                return FakeResult(
                    [{"inserted_values": len(rows), "invalid_symbol_count": 0}]
                )
            if "UPDATE qm_factor_candidate_runs" in sql and "metrics_json" in params:
                captured["run_update"] = params
                return FakeResult()
            if "SELECT *" in sql and "FROM qm_factor_candidate_runs" in sql:
                metrics = json.loads(captured["run_update"]["metrics_json"])
                gate = json.loads(captured["run_update"]["gate_decision_json"])
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "completed",
                            "params_json": {},
                            "metrics_json": metrics,
                            "gate_decision_json": gate,
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.evaluate_factor_run_locally("tenant", "user", "run-1")
    inserted_rows = json.loads(captured["insert"]["values_json"])

    assert result["status"] == "completed"
    assert result["metrics"]["source"] == "feature_snapshot_parquet"
    assert result["metrics"]["inserted_values"] == len(inserted_rows)
    assert result["metrics"]["snapshot_file_count"] == 1
    assert captured["insert"]["data_source"] == "feature_snapshot_parquet"
    assert {row["symbol"][:2] for row in inserted_rows} == {"SH", "SZ"}


@pytest.mark.asyncio
async def test_evaluate_factor_run_locally_falls_back_to_qlib_provider(
    monkeypatch, tmp_path
):
    pd = pytest.importorskip("pandas")
    provider_uri = tmp_path / "qlib_data"
    provider_uri.mkdir()
    monkeypatch.setattr(svc, "_FEATURE_SNAPSHOT_DIR", tmp_path / "missing_snapshots")
    monkeypatch.setenv("FACTOR_RESEARCH_QLIB_PROVIDER_URI", str(provider_uri))

    instruments = [
        "SH600001",
        "SH600002",
        "SH600003",
        "SZ000001",
        "SZ000002",
        "SZ000003",
    ]
    index_rows = []
    feature_rows = []
    for day in range(1, 20):
        for idx, instrument in enumerate(instruments, start=1):
            index_rows.append((instrument, pd.Timestamp(f"2026-01-{day:02d}")))
            feature_rows.append(
                {
                    "$open": 10 + idx,
                    "$high": 11 + idx,
                    "$low": 9 + idx,
                    "$close": 10 + idx * 0.5 + day * (0.03 * idx),
                    "$volume": 1000 + day,
                }
            )
    qlib_frame = pd.DataFrame(
        feature_rows,
        index=pd.MultiIndex.from_tuples(
            index_rows,
            names=["instrument", "datetime"],
        ),
    )
    qlib_calls: list[tuple[str, object]] = []

    class FakeD:
        @staticmethod
        def instruments(name):
            qlib_calls.append(("instruments", name))
            return name

        @staticmethod
        def list_instruments(_pool, as_list=False):
            qlib_calls.append(("list_instruments", as_list))
            return instruments

        @staticmethod
        def features(requested, fields, start_time=None, end_time=None):
            qlib_calls.append(("features", (requested, fields, start_time, end_time)))
            return qlib_frame

    monkeypatch.setitem(
        sys.modules,
        "qlib",
        types.SimpleNamespace(
            init=lambda **kwargs: qlib_calls.append(("init", kwargs))
        ),
    )
    monkeypatch.setitem(sys.modules, "qlib.data", types.SimpleNamespace(D=FakeD))
    captured: dict[str, dict] = {}

    class FakeMappings:
        def __init__(self, rows):
            self.rows = rows

        def first(self):
            return self.rows[0] if self.rows else None

        def one(self):
            return self.rows[0]

    class FakeResult:
        def __init__(self, rows=None, scalar=None):
            self.rows = rows or []
            self.scalar = scalar

        def mappings(self):
            return FakeMappings(self.rows)

        def scalar_one(self):
            return self.scalar

    class FakeSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            params = params or {}
            if "JOIN qm_factor_candidates" in sql:
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "pending",
                            "params_json": {
                                "start_date": "2026-01-01",
                                "end_date": "2026-01-19",
                                "holding_period": 2,
                            },
                            "metrics_json": None,
                            "gate_decision_json": {},
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                            "expression": "rank(close / ts_mean(close, 3))",
                            "factor_candidate_id": "candidate-1",
                        }
                    ]
                )
            if "to_regclass" in sql:
                return FakeResult(scalar=None)
            if "INSERT INTO qm_factor_values" in sql:
                captured["insert"] = params
                rows = json.loads(params["values_json"])
                return FakeResult(
                    [{"inserted_values": len(rows), "invalid_symbol_count": 0}]
                )
            if "UPDATE qm_factor_candidate_runs" in sql and "metrics_json" in params:
                captured["run_update"] = params
                return FakeResult()
            if "SELECT *" in sql and "FROM qm_factor_candidate_runs" in sql:
                metrics = json.loads(captured["run_update"]["metrics_json"])
                gate = json.loads(captured["run_update"]["gate_decision_json"])
                return FakeResult(
                    [
                        {
                            "id": "run-1",
                            "candidate_id": "candidate-1",
                            "tenant_id": "tenant",
                            "user_id": "user",
                            "status": "completed",
                            "params_json": {},
                            "metrics_json": metrics,
                            "gate_decision_json": gate,
                            "report_url": None,
                            "error_message": None,
                            "started_at": None,
                            "completed_at": None,
                            "created_at": None,
                            "updated_at": None,
                        }
                    ]
                )
            return FakeResult()

    @asynccontextmanager
    async def fake_get_session(*args, **kwargs):
        yield FakeSession()

    monkeypatch.setattr(svc, "get_session", fake_get_session)

    result = await svc.evaluate_factor_run_locally("tenant", "user", "run-1")
    inserted_rows = json.loads(captured["insert"]["values_json"])

    assert result["status"] == "completed"
    assert result["metrics"]["source"] == "qlib_provider"
    assert result["metrics"]["inserted_values"] == len(inserted_rows)
    assert result["metrics"]["qlib_instrument_count"] == len(instruments)
    assert result["metrics"]["qlib_row_count"] == len(qlib_frame)
    assert captured["insert"]["data_source"] == "qlib_provider"
    assert {row["symbol"][:2] for row in inserted_rows} == {"SH", "SZ"}
    assert any(call[0] == "features" for call in qlib_calls)
