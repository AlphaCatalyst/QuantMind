import json
import sys

import httpx
import pytest

from backend.services.engine.scripts.factor_research_live_api_smoke import (
    DateWindow,
    SmokeConfig,
    _parse_args,
    _unwrap_api_data,
    run_live_api_smoke,
)


def _config() -> SmokeConfig:
    return SmokeConfig(
        base_url="http://testserver",
        token=None,
        tenant_id="default",
        username=None,
        password=None,
        email=None,
        expression="rank(close / ts_mean(close, 20))",
        start_date="2026-01-01",
        end_date="2026-04-30",
        data_table="stock_daily_latest",
        lookback_days=80,
        min_symbols_per_day=20,
        top_n=5,
        bootstrap_from_westock=False,
        bootstrap_symbols=[],
        bootstrap_limit=100,
        include_materialize=True,
        include_campaign_flow=False,
        include_campaign_worker_flow=False,
        include_approval_flow=False,
        include_meta_evolution_flow=False,
        include_slo_health_flow=False,
        include_factor_value_backfill_flow=False,
        include_shadow_simulation_flow=False,
        keep_approval_flow_data=False,
        check_strategy_list=True,
        check_ai_ide_files=True,
        timeout_seconds=5.0,
    )


def test_unwrap_api_data_accepts_wrapped_and_plain_payloads():
    assert _unwrap_api_data({"code": 200, "data": {"ok": True}}) == {"ok": True}
    assert _unwrap_api_data({"access_token": "token"}) == {"access_token": "token"}


def test_parse_args_full_profile_enables_acceptance_flows(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "factor_research_live_api_smoke.py",
            "--base-url",
            "http://testserver",
            "--full-profile",
        ],
    )

    config = _parse_args()

    assert config.include_materialize is True
    assert config.include_campaign_flow is True
    assert config.include_campaign_worker_flow is True
    assert config.include_slo_health_flow is True
    assert config.include_factor_value_backfill_flow is True
    assert config.include_approval_flow is True
    assert config.include_shadow_simulation_flow is True


@pytest.mark.asyncio
async def test_live_api_smoke_runs_factor_research_flow_with_mock_transport():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        path = request.url.path
        method = request.method
        if method == "GET" and path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if method == "POST" and path == "/api/v1/auth/register":
            return httpx.Response(
                201,
                json={
                    "access_token": "token-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                    "user": {"id": "user-1"},
                },
            )
        if method == "GET" and path == "/api/v1/strategies":
            return httpx.Response(
                200,
                json={"total": 1, "strategies": [{"id": "strategy-1"}]},
            )
        if method == "GET" and path == "/api/v1/ai-ide/files/list":
            return httpx.Response(
                200,
                json={
                    "items": [{"name": "README.md", "type": "file"}],
                    "base": "/workspace",
                    "parent": None,
                    "current": "",
                },
            )
        if method == "POST" and path == "/api/v1/research/factors/candidates":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"candidate": {"id": "candidate-1"}}},
            )
        if (
            method == "POST"
            and path == "/api/v1/research/factors/candidates/candidate-1/evaluate"
        ):
            return httpx.Response(
                200,
                json={"code": 200, "data": {"run": {"id": "run-1"}}},
            )
        if method == "GET" and path == "/api/v1/research/factors/runs/run-1":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "run": {
                            "id": "run-1",
                            "status": "completed",
                            "metrics": {
                                "inserted_values": 100,
                                "coverage_days": 40,
                            },
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/runs/run-1/values":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "summary": {
                            "total": 100,
                            "tradeDateCount": 40,
                            "symbolCount": 25,
                            "invalidSymbolCount": 0,
                            "sourceCount": 1,
                            "sourceDistribution": [
                                {"source": "local_stock_daily_latest", "count": 100}
                            ],
                            "recentDateDistribution": [
                                {"tradeDate": "2026-04-30", "count": 25}
                            ],
                        },
                        "items": [
                            {
                                "tradeDate": "2026-04-30",
                                "symbol": "SH600001",
                                "factorValue": 0.5,
                            }
                        ],
                        "pagination": {
                            "limit": 5,
                            "offset": 0,
                            "returned": 1,
                            "hasMore": True,
                        },
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/candidates":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {"items": [{"id": "candidate-1"}], "total": 1},
                },
            )
        if (
            method == "POST"
            and path == "/api/v1/research/factors/candidates/candidate-1/promote"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "promotion": {
                            "id": "promotion-1",
                            "status": "pending_materialization",
                            "materializationStatus": "pending_materialization",
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/promotions":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {"items": [{"id": "promotion-1"}], "total": 1},
                },
            )
        if (
            method == "POST"
            and path == "/api/v1/research/factors/promotions/promotion-1/materialize"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "promotion": {
                            "id": "promotion-1",
                            "status": "materialized",
                            "materializationStatus": "materialized",
                        }
                    },
                },
            )
        if (
            method == "POST"
            and path
            == "/api/v1/research/factors/candidates/candidate-1/publish-shadow-signal"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "signalRun": {
                            "id": "signal-1",
                            "signalCount": 5,
                            "streamPublishedCount": 0,
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/approvals":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [], "total": 0}},
            )
        if method == "GET" and path == "/api/v1/research/factors/approval-requests":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [], "total": 0}},
            )
        if method == "GET" and path == "/api/v1/research/factors/health":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "health": {
                            "status": "warning",
                            "alerts": [{"level": "warning", "code": "pending"}],
                        }
                    },
                },
            )
        return httpx.Response(404, json={"detail": f"unhandled {method} {path}"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = await run_live_api_smoke(_config(), client=client)

    assert result.status == "passed"
    assert result.auth_source == "register"
    assert result.user_id == "user-1"
    assert result.date_window == DateWindow(
        start_date="2026-01-01",
        end_date="2026-04-30",
        coverage_days=0,
        min_symbols_per_day=0,
        max_symbols_per_day=0,
    )
    assert result.run_id == "run-1"
    assert result.inserted_values == 100
    assert result.factor_value_total == 100
    assert result.factor_value_sample_count == 1
    assert result.strategy_total == 1
    assert result.ai_ide_file_count == 1
    assert result.approval_audit_total == 0
    assert result.approval_request_total == 0
    assert result.approval_flow_request_status is None
    assert result.approval_flow_review_status is None
    assert result.approval_flow_reject_status is None
    assert result.approval_flow_default_model_id is None
    assert result.approval_flow_notification_count is None
    assert result.approval_flow_policy_min_approvals is None
    assert result.factor_health_status == "warning"
    assert result.factor_health_alert_count == 1
    assert result.campaign_flow_id is None
    assert result.campaign_flow_total_candidates is None
    assert result.campaign_flow_completed_generations is None
    assert result.campaign_flow_item_count is None
    assert result.shadow_simulation_unauthorized_status is None
    assert result.shadow_simulation_authorized_task_status is None
    assert result.shadow_simulation_authorized_trading_mode is None
    assert result.materialization_status == "materialized"
    assert result.signal_run_id == "signal-1"
    assert ("POST", "/api/v1/research/factors/candidates/candidate-1/promote") in seen
    assert ("GET", "/api/v1/research/factors/approvals") in seen
    assert ("GET", "/api/v1/research/factors/approval-requests") in seen
    assert ("GET", "/api/v1/research/factors/health") in seen
    assert ("GET", "/api/v1/research/factors/runs/run-1/values") in seen


@pytest.mark.asyncio
async def test_live_api_smoke_verifies_campaign_generation_flow_with_mock_transport(
    monkeypatch,
):
    config = _config()
    config = SmokeConfig(
        **{
            **config.__dict__,
            "include_materialize": False,
            "include_campaign_flow": True,
            "include_campaign_worker_flow": True,
            "check_strategy_list": False,
            "check_ai_ide_files": False,
        }
    )
    seen: list[tuple[str, str]] = []
    worker_campaign_ids: list[str] = []
    worker_calls = 0

    async def fake_run_worker(**kwargs):
        nonlocal worker_calls
        worker_calls += 1
        worker_id = kwargs["worker_id"]
        assert worker_id.startswith("live-smoke-worker-")
        assert kwargs["max_claims"] == 1
        assert kwargs["concurrency"] == 1
        if len(worker_campaign_ids) == 1:
            return 1 if "-worker-a-" in worker_id else 0
        return 1 if "-worker-b-" in worker_id else 0

    monkeypatch.setattr(
        "backend.services.engine.scripts.factor_research_live_api_smoke.run_factor_campaign_worker",
        fake_run_worker,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        path = request.url.path
        method = request.method
        if method == "GET" and path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if method == "POST" and path == "/api/v1/auth/register":
            return httpx.Response(
                201,
                json={
                    "access_token": "token-1",
                    "refresh_token": "refresh-1",
                    "expires_in": 3600,
                    "user": {"id": "user-1"},
                },
            )
        if method == "POST" and path == "/api/v1/research/factors/candidates":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"candidate": {"id": "candidate-1"}}},
            )
        if (
            method == "POST"
            and path == "/api/v1/research/factors/candidates/candidate-1/evaluate"
        ):
            return httpx.Response(
                200,
                json={"code": 200, "data": {"run": {"id": "run-1"}}},
            )
        if method == "GET" and path == "/api/v1/research/factors/runs/run-1":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "run": {
                            "id": "run-1",
                            "status": "completed",
                            "metrics": {
                                "inserted_values": 100,
                                "coverage_days": 40,
                            },
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/runs/run-1/values":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "summary": {
                            "total": 100,
                            "tradeDateCount": 40,
                            "symbolCount": 25,
                            "invalidSymbolCount": 0,
                            "sourceCount": 1,
                            "sourceDistribution": [
                                {"source": "local_stock_daily_latest", "count": 100}
                            ],
                            "recentDateDistribution": [
                                {"tradeDate": "2026-04-30", "count": 25}
                            ],
                        },
                        "items": [{"symbol": "SH600001", "factorValue": 0.5}],
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/candidates":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {"items": [{"id": "candidate-1"}], "total": 1},
                },
            )
        if method == "POST" and path == "/api/v1/research/factors/campaigns":
            body = json.loads(request.content.decode() or "{}")
            if (body.get("worker_policy") or {}).get("external_worker") is True:
                campaign_id = f"campaign-worker-{len(worker_campaign_ids) + 1}"
                worker_campaign_ids.append(campaign_id)
                return httpx.Response(
                    200,
                    json={
                        "code": 200,
                        "data": {
                            "campaign": {
                                "id": campaign_id,
                                "status": "pending",
                                "summary": {},
                                "items": [],
                            }
                        },
                    },
                )
            if body.get("run_async") is True:
                return httpx.Response(
                    200,
                    json={
                        "code": 200,
                        "data": {
                            "campaign": {
                                "id": "campaign-async-1",
                                "status": "pending",
                                "summary": {},
                                "items": [],
                            }
                        },
                    },
                )
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "campaign": {
                            "id": "campaign-1",
                            "summary": {
                                "totalCandidates": 4,
                                "completedGenerations": 2,
                                "generationStats": [
                                    {"generation": 1, "totalCandidates": 2},
                                    {"generation": 2, "totalCandidates": 2},
                                ],
                            },
                            "items": [
                                {"generation": 1, "rankNo": 1},
                                {"generation": 2, "rankNo": 3},
                            ],
                        }
                    },
                },
            )
        if method == "GET" and path.startswith(
            "/api/v1/research/factors/campaigns/campaign-worker-"
        ):
            campaign_id = path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "campaign": {
                            "id": campaign_id,
                            "status": "completed",
                            "items": [{"generation": 1, "rankNo": 1}],
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/campaigns/campaign-1":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "campaign": {
                            "id": "campaign-1",
                            "items": [
                                {"generation": 1, "rankNo": 1},
                                {"generation": 2, "rankNo": 3},
                            ],
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/campaign-worker-events":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "items": [
                            {
                                "id": "event-1",
                                "eventType": "processed",
                                "workerId": request.url.params.get("worker_id"),
                            },
                            {
                                "id": "event-2",
                                "eventType": "processed",
                                "workerId": request.url.params.get("worker_id"),
                            },
                        ],
                        "total": 2,
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/campaigns/campaign-async-1":
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "campaign": {
                            "id": "campaign-async-1",
                            "status": "completed",
                            "items": [{"generation": 1, "rankNo": 1}],
                        }
                    },
                },
            )
        if (
            method == "POST"
            and path == "/api/v1/research/factors/candidates/candidate-1/promote"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "promotion": {
                            "id": "promotion-1",
                            "status": "pending_materialization",
                            "materializationStatus": "pending_materialization",
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/promotions":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [{"id": "promotion-1"}], "total": 1}},
            )
        if (
            method == "POST"
            and path
            == "/api/v1/research/factors/candidates/candidate-1/publish-shadow-signal"
        ):
            return httpx.Response(
                200,
                json={
                    "code": 200,
                    "data": {
                        "signalRun": {
                            "id": "signal-1",
                            "signalCount": 5,
                            "streamPublishedCount": 0,
                        }
                    },
                },
            )
        if method == "GET" and path == "/api/v1/research/factors/approvals":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [], "total": 0}},
            )
        if method == "GET" and path == "/api/v1/research/factors/approval-requests":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"items": [], "total": 0}},
            )
        if method == "GET" and path == "/api/v1/research/factors/health":
            return httpx.Response(
                200,
                json={"code": 200, "data": {"health": {"status": "healthy", "alerts": []}}},
            )
        return httpx.Response(404, json={"detail": f"unhandled {method} {path}"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        result = await run_live_api_smoke(config, client=client)

    assert result.status == "passed"
    assert result.campaign_flow_id == "campaign-1"
    assert result.campaign_flow_total_candidates == 4
    assert result.campaign_flow_completed_generations == 2
    assert result.campaign_flow_item_count == 2
    assert result.campaign_worker_flow_processed == 2
    assert result.campaign_worker_flow_event_count == 4
    assert worker_calls == 4
    assert ("POST", "/api/v1/research/factors/campaigns") in seen
    assert ("GET", "/api/v1/research/factors/campaigns/campaign-1") in seen
    assert ("GET", "/api/v1/research/factors/campaign-worker-events") in seen
