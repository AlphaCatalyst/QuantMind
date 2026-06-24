from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import text

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.api.routers.research_factor_market_data import (  # noqa: E402
    safe_local_market_table_name,
)
from backend.services.api.routers.research_factor_service import (  # noqa: E402
    create_factor_training_approval_request,
    ensure_research_factor_tables,
    get_factor_approval_policy,
    list_factor_approval_audits,
    list_factor_approval_requests,
    review_factor_training_approval_request,
    upsert_factor_approval_policy,
)
from backend.services.engine.research.quantgpt_mapping import (  # noqa: E402
    normalize_quantgpt_symbol,
)
from backend.services.engine.scripts.quantgpt_real_data_smoke import (  # noqa: E402
    _markdown_table_to_rows,
    _run_westock_kline,
)
from backend.services.engine.scripts.factor_campaign_worker import (  # noqa: E402
    run_worker as run_factor_campaign_worker,
)
from backend.services.engine.scripts.factor_value_backfill_worker import (  # noqa: E402
    run_worker as run_factor_value_backfill_worker,
)
from backend.services.engine.services.model_inference_persistence import (  # noqa: E402
    model_inference_persistence,
)
from backend.services.trade.redis_client import get_redis as get_trade_redis  # noqa: E402
from backend.services.trade.services.manual_execution_persistence import (  # noqa: E402
    manual_execution_persistence,
)
from backend.services.trade.services.manual_execution_service import (  # noqa: E402
    manual_execution_service,
)
from backend.shared.database_manager_v2 import close_database, get_session  # noqa: E402
from backend.shared.model_registry import model_registry_service  # noqa: E402
from backend.shared.strategy_storage import ensure_strategy_storage_tables  # noqa: E402


class SmokeFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    token: str | None
    tenant_id: str
    username: str | None
    password: str | None
    email: str | None
    expression: str
    start_date: str | None
    end_date: str | None
    data_table: str
    lookback_days: int
    min_symbols_per_day: int
    top_n: int
    bootstrap_from_westock: bool
    bootstrap_symbols: list[str]
    bootstrap_limit: int
    include_materialize: bool
    include_campaign_flow: bool
    include_campaign_worker_flow: bool
    include_meta_evolution_flow: bool
    include_slo_health_flow: bool
    include_factor_value_backfill_flow: bool
    include_approval_flow: bool
    include_shadow_simulation_flow: bool
    keep_approval_flow_data: bool
    check_strategy_list: bool
    check_ai_ide_files: bool
    timeout_seconds: float


@dataclass(frozen=True)
class DateWindow:
    start_date: str
    end_date: str
    coverage_days: int
    min_symbols_per_day: int
    max_symbols_per_day: int


@dataclass(frozen=True)
class SmokeResult:
    status: str
    base_url: str
    auth_source: str
    tenant_id: str
    user_id: str | None
    date_window: DateWindow
    expression: str
    candidate_id: str
    run_id: str
    run_status: str
    inserted_values: int
    coverage_days: int
    factor_value_total: int
    factor_value_sample_count: int
    promotion_id: str
    promotion_status: str
    materialization_status: str
    signal_run_id: str
    signal_count: int
    stream_published_count: int
    strategy_total: int | None
    ai_ide_file_count: int | None
    approval_audit_total: int | None
    approval_request_total: int | None
    factor_health_status: str | None
    factor_health_alert_count: int | None
    factor_slo_status: str | None
    factor_slo_breach_count: int | None
    campaign_flow_id: str | None
    campaign_flow_total_candidates: int | None
    campaign_flow_completed_generations: int | None
    campaign_flow_item_count: int | None
    campaign_async_flow_id: str | None
    campaign_async_flow_status: str | None
    campaign_async_flow_item_count: int | None
    campaign_worker_flow_processed: int | None
    campaign_worker_flow_event_count: int | None
    meta_evolution_flow_id: str | None
    meta_evolution_flow_strategy: str | None
    meta_evolution_flow_item_count: int | None
    factor_value_backfill_job_id: str | None
    factor_value_backfill_status: str | None
    factor_value_backfill_processed_runs: int | None
    factor_value_backfill_event_count: int | None
    approval_flow_request_status: str | None
    approval_flow_review_status: str | None
    approval_flow_reject_status: str | None
    approval_flow_default_model_id: str | None
    approval_flow_notification_count: int | None
    approval_flow_policy_min_approvals: int | None
    shadow_simulation_unauthorized_status: int | None
    shadow_simulation_authorized_task_status: str | None
    shadow_simulation_authorized_trading_mode: str | None
    shadow_simulation_executed_task_status: str | None
    shadow_simulation_execution_order_count: int | None
    shadow_simulation_execution_fill_count: int | None
    shadow_simulation_position_lot_count: int | None
    shadow_simulation_cash_ledger_count: int | None
    steps: list[str]


def _unwrap_api_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text_value = str(value).replace(",", "").strip()
    if not text_value or text_value in {"-", "--"}:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


def _json_response(response: httpx.Response, *, step: str) -> Any:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SmokeFailure(f"{step} returned non-JSON response") from exc
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise SmokeFailure(f"{step} failed: HTTP {response.status_code}: {detail}")
    return payload


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    token: str | None = None,
    step: str,
    json_body: dict[str, Any] | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.request(method, path, json=json_body, headers=headers)
    return _json_response(response, step=step)


async def _authenticate(
    client: httpx.AsyncClient,
    config: SmokeConfig,
    stamp: str,
) -> tuple[str, str, str | None]:
    if config.token:
        return config.token, "provided_token", None

    password = config.password or "QuantMindLive123!"
    if config.username:
        payload = {
            "tenant_id": config.tenant_id,
            "username": config.username,
            "password": password,
        }
        auth_payload = await _request_json(
            client,
            "POST",
            "/api/v1/auth/login",
            step="login",
            json_body=payload,
        )
        token = str(auth_payload.get("access_token") or "").strip()
        user = auth_payload.get("user") if isinstance(auth_payload.get("user"), dict) else {}
        raw_user_id = user.get("id")
        user_id = str(raw_user_id) if raw_user_id is not None else None
        _require(bool(token), "login response did not include access_token")
        return token, "login", user_id

    username = f"factorlive{stamp}"
    payload = {
        "tenant_id": config.tenant_id,
        "username": username,
        "email": config.email or f"{username}@example.com",
        "password": password,
        "full_name": "Factor Research Live Smoke",
    }
    auth_payload = await _request_json(
        client,
        "POST",
        "/api/v1/auth/register",
        step="register",
        json_body=payload,
    )
    token = str(auth_payload.get("access_token") or "").strip()
    user = auth_payload.get("user") if isinstance(auth_payload.get("user"), dict) else {}
    raw_user_id = user.get("id")
    user_id = str(raw_user_id) if raw_user_id is not None else None
    _require(bool(token), "register response did not include access_token")
    return token, "register", user_id


async def _bootstrap_stock_daily_latest_from_westock(config: SmokeConfig) -> DateWindow | None:
    if not config.bootstrap_from_westock:
        return None

    table = safe_local_market_table_name(config.data_table)
    if table != "stock_daily_latest":
        raise SmokeFailure("--bootstrap-from-westock only supports stock_daily_latest")

    rows_to_insert: list[dict[str, Any]] = []
    for symbol in config.bootstrap_symbols:
        markdown = _run_westock_kline(symbol, config.bootstrap_limit)
        for row in _markdown_table_to_rows(markdown):
            trade_date = str(row.get("date") or row.get("time") or "")[:10]
            open_price = _float_or_none(row.get("open"))
            high = _float_or_none(row.get("high"))
            low = _float_or_none(row.get("low"))
            close = _float_or_none(row.get("close") or row.get("last") or row.get("price"))
            volume = _float_or_none(row.get("volume"))
            if not trade_date or any(
                item is None for item in (open_price, high, low, close, volume)
            ):
                continue
            rows_to_insert.append(
                {
                    "symbol": normalize_quantgpt_symbol(symbol),
                    "trade_date": date.fromisoformat(trade_date),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

    _require(bool(rows_to_insert), "westock bootstrap produced no OHLCV rows")
    async with get_session() as session:
        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_daily_latest (
                    symbol TEXT NOT NULL,
                    trade_date DATE NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    PRIMARY KEY (symbol, trade_date)
                )
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO stock_daily_latest (
                    symbol, trade_date, open, high, low, close, volume
                )
                VALUES (
                    :symbol, :trade_date, :open, :high, :low, :close, :volume
                )
                ON CONFLICT (symbol, trade_date)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """
            ),
            rows_to_insert,
        )

    dates = sorted({str(row["trade_date"]) for row in rows_to_insert})
    per_day: dict[str, int] = {}
    for row in rows_to_insert:
        per_day[str(row["trade_date"])] = per_day.get(str(row["trade_date"]), 0) + 1
    return DateWindow(
        start_date=dates[0],
        end_date=dates[-1],
        coverage_days=len(dates),
        min_symbols_per_day=min(per_day.values()),
        max_symbols_per_day=max(per_day.values()),
    )


async def _discover_date_window(config: SmokeConfig) -> DateWindow:
    if config.start_date and config.end_date:
        return DateWindow(
            start_date=config.start_date,
            end_date=config.end_date,
            coverage_days=0,
            min_symbols_per_day=0,
            max_symbols_per_day=0,
        )

    table = safe_local_market_table_name(config.data_table)
    async with get_session(read_only=True) as session:
        exists = (
            await session.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table}"},
            )
        ).scalar_one()
        if not exists:
            raise SmokeFailure(
                "local market data table missing: "
                f"{table}; run this smoke with --bootstrap-from-westock on a host "
                "where westock-data is installed, or sync stock_daily_latest first"
            )
        row = (
            await session.execute(
                text(
                    f"""
                    WITH eligible_dates AS (
                        SELECT trade_date::date AS trade_date, COUNT(*) AS symbol_count
                        FROM {table}
                        WHERE open IS NOT NULL
                          AND high IS NOT NULL
                          AND low IS NOT NULL
                          AND close IS NOT NULL
                          AND volume IS NOT NULL
                          AND volume > 0
                        GROUP BY trade_date::date
                        HAVING COUNT(*) >= :min_symbols
                        ORDER BY trade_date::date DESC
                        LIMIT :lookback_days
                    )
                    SELECT
                        MIN(trade_date) AS start_date,
                        MAX(trade_date) AS end_date,
                        COUNT(*) AS coverage_days,
                        MIN(symbol_count) AS min_symbols_per_day,
                        MAX(symbol_count) AS max_symbols_per_day
                    FROM eligible_dates
                    """
                ),
                {
                    "min_symbols": config.min_symbols_per_day,
                    "lookback_days": config.lookback_days,
                },
            )
        ).mappings().one()

    start_date = row.get("start_date")
    end_date = row.get("end_date")
    coverage_days = int(row.get("coverage_days") or 0)
    _require(start_date is not None and end_date is not None, "no eligible market data window found")
    _require(
        coverage_days >= min(config.lookback_days, 30),
        f"insufficient market data coverage: {coverage_days} days",
    )
    return DateWindow(
        start_date=str(start_date),
        end_date=str(end_date),
        coverage_days=coverage_days,
        min_symbols_per_day=int(row.get("min_symbols_per_day") or 0),
        max_symbols_per_day=int(row.get("max_symbols_per_day") or 0),
    )


async def _run_factor_approval_service_smoke(
    config: SmokeConfig,
    *,
    stamp: str,
) -> dict[str, str]:
    await ensure_research_factor_tables()
    await model_registry_service.ensure_tables()

    tenant_id = f"{config.tenant_id}-approval-smoke-{stamp}"
    reviewer_user_id = f"factor-approval-admin-{stamp}"
    expression = "rank(close / ts_mean(close, 20))"
    comparison = {
        "status": "improved",
        "summary": "approval smoke promoted model outperformed baseline",
        "delta": {"test_auc": 0.03, "test_rmse": -0.04},
    }

    async def seed_user(user_id: str, *, is_admin: bool = False) -> None:
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO users (
                        user_id, tenant_id, username, email, password_hash,
                        is_active, is_verified, is_admin, is_deleted
                    ) VALUES (
                        :user_id, :tenant_id, :username, NULL, 'approval-smoke',
                        TRUE, TRUE, :is_admin, FALSE
                    )
                    ON CONFLICT (user_id)
                    DO UPDATE SET tenant_id = EXCLUDED.tenant_id,
                                  username = EXCLUDED.username,
                                  is_active = TRUE,
                                  is_verified = TRUE,
                                  is_admin = EXCLUDED.is_admin,
                                  is_deleted = FALSE,
                                  updated_at = NOW()
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "username": user_id,
                    "is_admin": is_admin,
                },
            )

    async def seed_record(label: str) -> dict[str, str]:
        owner_user_id = f"factor-approval-owner-{stamp}-{label}"
        candidate_id = f"factor-approval-candidate-{stamp}-{label}"
        run_id = f"factor-approval-run-{stamp}-{label}"
        promotion_id = f"factor-approval-promotion-{stamp}-{label}"
        training_id = f"factor-approval-training-{stamp}-{label}"
        model_id = f"factor_approval_model_{stamp}_{label}"
        feature_key = f"factor_approval_smoke_{stamp}_{label}"
        version_id = f"feature-set-approval-smoke-{stamp}-{label}"

        await seed_user(owner_user_id, is_admin=False)
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO qm_factor_candidates (
                        id, tenant_id, user_id, expression, expression_hash, name,
                        source, family, status, tags, metadata_json
                    ) VALUES (
                        :candidate_id, :tenant_id, :user_id, :expression,
                        :expression_hash, :name, 'live_api_smoke', 'smoke',
                        'validated', CAST(:tags AS JSONB), CAST(:metadata AS JSONB)
                    )
                    """
                ),
                {
                    "candidate_id": candidate_id,
                    "tenant_id": tenant_id,
                    "user_id": owner_user_id,
                    "expression": expression,
                    "expression_hash": f"approval-smoke-{stamp}-{label}",
                    "name": f"Approval Smoke {stamp} {label}",
                    "tags": json.dumps(["live_api_smoke"], ensure_ascii=False),
                    "metadata": json.dumps({"smoke_stamp": stamp}, ensure_ascii=False),
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO qm_factor_candidate_runs (
                        id, candidate_id, tenant_id, user_id, status, params_json,
                        metrics_json, gate_decision_json, started_at, completed_at
                    ) VALUES (
                        :run_id, :candidate_id, :tenant_id, :user_id, 'completed',
                        CAST(:params AS JSONB), CAST(:metrics AS JSONB),
                        CAST(:gate AS JSONB), NOW(), NOW()
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "tenant_id": tenant_id,
                    "user_id": owner_user_id,
                    "params": json.dumps({"validation_profile": "approval_smoke"}),
                    "metrics": json.dumps({"rank_ic_mean": 0.03, "coverage_days": 40}),
                    "gate": json.dumps({"eligible": True, "reasons": []}),
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO qm_factor_feature_promotions (
                        id, candidate_id, run_id, tenant_id, user_id, feature_key,
                        feature_id, version_id, status, materialization_status,
                        metadata_json
                    ) VALUES (
                        :promotion_id, :candidate_id, :run_id, :tenant_id, :user_id,
                        :feature_key, :feature_key, :version_id, 'materialized',
                        'materialized', CAST(:metadata AS JSONB)
                    )
                    """
                ),
                {
                    "promotion_id": promotion_id,
                    "candidate_id": candidate_id,
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "user_id": owner_user_id,
                    "feature_key": feature_key,
                    "version_id": version_id,
                    "metadata": json.dumps({"smoke_stamp": stamp}, ensure_ascii=False),
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO qm_factor_training_runs (
                        id, promotion_id, candidate_id, factor_run_id, tenant_id,
                        user_id, training_run_id, status, feature_key,
                        feature_set_version_id, request_payload_json, response_json,
                        metadata_json
                    ) VALUES (
                        :training_id, :promotion_id, :candidate_id, :run_id,
                        :tenant_id, :user_id, :training_run_id, 'completed',
                        :feature_key, :version_id, CAST(:request_payload AS JSONB),
                        CAST(:response AS JSONB), CAST(:metadata AS JSONB)
                    )
                    """
                ),
                {
                    "training_id": training_id,
                    "promotion_id": promotion_id,
                    "candidate_id": candidate_id,
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "user_id": owner_user_id,
                    "training_run_id": f"train-approval-smoke-{stamp}-{label}",
                    "feature_key": feature_key,
                    "version_id": version_id,
                    "request_payload": json.dumps({"factor_research": {}}),
                    "response": json.dumps(
                        {
                            "model_registration": {
                                "model_id": model_id,
                                "status": "ready",
                            },
                            "comparison": comparison,
                        },
                        ensure_ascii=False,
                    ),
                    "metadata": json.dumps({"smoke_stamp": stamp}, ensure_ascii=False),
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO qm_user_models (
                        tenant_id, user_id, model_id, source_run_id, status,
                        storage_path, model_file, metadata_json, metrics_json,
                        is_default
                    ) VALUES (
                        :tenant_id, :user_id, :model_id, :source_run_id, 'ready',
                        :storage_path, 'model.pkl', CAST(:metadata AS JSONB),
                        CAST(:metrics AS JSONB), FALSE
                    )
                    ON CONFLICT (tenant_id, user_id, model_id)
                    DO UPDATE SET status = 'ready',
                                  is_default = FALSE,
                                  updated_at = NOW()
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": owner_user_id,
                    "model_id": model_id,
                    "source_run_id": f"train-approval-smoke-{stamp}-{label}",
                    "storage_path": f"/tmp/quantmind/approval-smoke/{stamp}/{label}",
                    "metadata": json.dumps(
                        {
                            "smoke_stamp": stamp,
                            "factor_research": {
                                "candidate_id": candidate_id,
                                "promotion_id": promotion_id,
                                "training_id": training_id,
                            },
                        },
                        ensure_ascii=False,
                    ),
                    "metrics": json.dumps({"test_auc": 0.58, "test_rmse": 0.18}),
                },
            )
        return {
            "owner_user_id": owner_user_id,
            "training_id": training_id,
            "model_id": model_id,
        }

    async def cleanup_seeded_data() -> None:
        owner_prefix = f"factor-approval-owner-{stamp}%"
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    DELETE FROM qm_factor_approval_policies
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM notifications
                    WHERE tenant_id = :tenant_id
                      AND (user_id LIKE :owner_prefix OR user_id = :reviewer_user_id)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "owner_prefix": owner_prefix,
                    "reviewer_user_id": reviewer_user_id,
                },
            )
            await session.execute(
                text(
                    """
                    DELETE FROM qm_factor_approval_audit
                    WHERE tenant_id = :tenant_id
                      AND user_id LIKE :owner_prefix
                    """
                ),
                {"tenant_id": tenant_id, "owner_prefix": owner_prefix},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM users
                    WHERE tenant_id = :tenant_id
                      AND (user_id LIKE :owner_prefix OR user_id = :reviewer_user_id)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "owner_prefix": owner_prefix,
                    "reviewer_user_id": reviewer_user_id,
                },
            )

    async def count_approval_notifications() -> int:
        owner_prefix = f"factor-approval-owner-{stamp}%"
        async with get_session(read_only=True) as session:
            return int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM notifications
                            WHERE tenant_id = :tenant_id
                              AND (
                                    user_id LIKE :owner_prefix
                                 OR user_id = :reviewer_user_id
                              )
                            """
                        ),
                        {
                            "tenant_id": tenant_id,
                            "owner_prefix": owner_prefix,
                            "reviewer_user_id": reviewer_user_id,
                        },
                    )
                ).scalar_one()
                or 0
            )
            await session.execute(
                text(
                    """
                    DELETE FROM qm_factor_approval_requests
                    WHERE tenant_id = :tenant_id
                      AND user_id LIKE :owner_prefix
                    """
                ),
                {"tenant_id": tenant_id, "owner_prefix": owner_prefix},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM qm_user_models
                    WHERE tenant_id = :tenant_id
                      AND user_id LIKE :owner_prefix
                    """
                ),
                {"tenant_id": tenant_id, "owner_prefix": owner_prefix},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM qm_factor_candidates
                    WHERE tenant_id = :tenant_id
                      AND user_id LIKE :owner_prefix
                    """
                ),
                {"tenant_id": tenant_id, "owner_prefix": owner_prefix},
            )

    async def submit_request(seed: dict[str, str], *, label: str) -> dict[str, Any]:
        request = await create_factor_training_approval_request(
            tenant_id,
            seed["owner_user_id"],
            seed["training_id"],
            {
                "reason": f"approval_service_smoke_{label}",
                "metadata": {"smoke_stamp": stamp, "path": label},
                "requested_by": seed["owner_user_id"],
            },
        )
        _require(request.get("status") == "pending", f"{label} request was not pending")
        return request

    try:
        policy = await upsert_factor_approval_policy(
            tenant_id,
            {
                "allow_direct_approval": True,
                "allow_self_approval": True,
                "min_approvals": 1,
                "metadata": {"smoke_stamp": stamp},
            },
            updated_by=reviewer_user_id,
        )
        fetched_policy = await get_factor_approval_policy(tenant_id)
        _require(
            int(fetched_policy.get("minApprovals") or 0) == 1,
            "factor approval policy was not persisted",
        )
        await seed_user(reviewer_user_id, is_admin=True)
        approve_seed = await seed_record("approve")
        approve_request = await submit_request(approve_seed, label="approve")
        replay = await create_factor_training_approval_request(
            tenant_id,
            approve_seed["owner_user_id"],
            approve_seed["training_id"],
            {
                "reason": "approval_service_smoke_replay",
                "requested_by": approve_seed["owner_user_id"],
            },
        )
        _require(
            replay.get("id") == approve_request.get("id")
            and replay.get("idempotent") is True,
            "approval request replay was not idempotent",
        )
        pending = await list_factor_approval_requests(
            tenant_id,
            user_id=approve_seed["owner_user_id"],
            status="pending",
            limit=5,
        )
        _require(pending.get("total") == 1, "pending approval request was not queryable")

        approve_review = await review_factor_training_approval_request(
            tenant_id,
            str(approve_request["id"]),
            reviewer_user_id,
            {
                "approve": True,
                "decision": "approve",
                "reason": "approval_service_smoke_review",
                "reviewer_note": "approved_by_live_api_smoke",
                "metadata": {"smoke_stamp": stamp, "path": "approve"},
            },
        )
        approved_request = (
            approve_review.get("request") if isinstance(approve_review, dict) else {}
        )
        _require(
            approved_request.get("status") == "approved",
            "approval request review did not approve request",
        )
        approval_result = (
            approve_review.get("approvalResult")
            if isinstance(approve_review, dict)
            else {}
        )
        default_model = (
            approval_result.get("defaultModel")
            if isinstance(approval_result, dict)
            else {}
        )
        _require(
            str((default_model or {}).get("model_id") or "")
            == approve_seed["model_id"],
            "approval review did not set expected default model",
        )
        audits = await list_factor_approval_audits(
            tenant_id,
            approve_seed["owner_user_id"],
            training_id=approve_seed["training_id"],
            model_id=approve_seed["model_id"],
            status="approved",
            limit=5,
        )
        _require(audits.get("total") == 1, "approval audit was not written")

        reject_seed = await seed_record("reject")
        reject_request = await submit_request(reject_seed, label="reject")
        reject_review = await review_factor_training_approval_request(
            tenant_id,
            str(reject_request["id"]),
            reviewer_user_id,
            {
                "approve": False,
                "decision": "reject",
                "reason": "approval_service_smoke_reject",
                "reviewer_note": "rejected_by_live_api_smoke",
                "metadata": {"smoke_stamp": stamp, "path": "reject"},
            },
        )
        rejected_request = (
            reject_review.get("request") if isinstance(reject_review, dict) else {}
        )
        _require(
            rejected_request.get("status") == "rejected",
            "approval request review did not reject request",
        )
        _require(
            reject_review.get("approvalResult") is None,
            "rejected approval request should not return approval result",
        )
        rejected_audits = await list_factor_approval_audits(
            tenant_id,
            reject_seed["owner_user_id"],
            training_id=reject_seed["training_id"],
            model_id=reject_seed["model_id"],
            limit=5,
        )
        _require(
            rejected_audits.get("total") == 0,
            "rejected approval request should not write approval audit",
        )
        notification_count = await count_approval_notifications()
        _require(
            notification_count >= 6,
            f"approval notifications were not written: {notification_count}",
        )

        return {
            "request_status": str(approved_request.get("status") or ""),
            "review_status": str(approved_request.get("status") or ""),
            "reject_status": str(rejected_request.get("status") or ""),
            "default_model_id": approve_seed["model_id"],
            "notification_count": str(notification_count),
            "policy_min_approvals": str(policy.get("minApprovals") or ""),
        }
    finally:
        if not config.keep_approval_flow_data:
            await cleanup_seeded_data()


async def _run_factor_shadow_simulation_hosted_smoke(
    config: SmokeConfig,
    *,
    stamp: str,
    source_signal_run_id: str,
) -> dict[str, str]:
    await ensure_research_factor_tables()
    await model_inference_persistence.ensure_tables()
    ensure_strategy_storage_tables()
    await manual_execution_persistence.ensure_tables()

    tenant_id = f"{config.tenant_id}-shadow-sim-smoke-{stamp}"
    user_id = str(91000000 + (int(stamp[-6:]) % 900000))
    run_id = f"factor-shadow-sim-run-{stamp}"
    model_id = f"factor_shadow_sim_model_{stamp}"
    feature_version = f"shadow-sim-feature-{stamp}"
    data_trade_date = date.today() - timedelta(days=1)
    prediction_trade_date = date.today()
    redis_key = f"simulation:account:{tenant_id}:{user_id}"
    strategy_id: str | None = None
    authorized_task_id = f"hosted_factor_shadow_sim_{stamp}"

    async def seed_records() -> None:
        nonlocal strategy_id
        async with get_session() as session:
            strategy_id = str(
                (
                    await session.execute(
                        text(
                            """
                            INSERT INTO strategies (
                                user_id, name, description, strategy_type, status,
                                config, parameters, execution_config, code, tags,
                                is_public, is_verified, created_at, updated_at
                            ) VALUES (
                                :user_id, :name, 'factor shadow simulation smoke',
                                'CUSTOM', 'ACTIVE', '{}'::jsonb,
                                CAST(:parameters AS JSONB),
                                CAST(:execution_config AS JSONB),
                                :code, ARRAY['live_api_smoke']::TEXT[],
                                FALSE, TRUE, NOW(), NOW()
                            )
                            RETURNING id
                            """
                        ),
                        {
                            "user_id": user_id,
                            "name": f"Factor Shadow Simulation Smoke {stamp}",
                            "parameters": json.dumps(
                                {
                                    "strategy_type": "TopkDropout",
                                    "topk": 1,
                                    "signal": "<PRED>",
                                },
                                ensure_ascii=False,
                            ),
                            "execution_config": json.dumps(
                                {"max_buy_drop": -0.03, "stop_loss": -0.08},
                                ensure_ascii=False,
                            ),
                            "code": "# factor shadow simulation smoke\n",
                        },
                    )
                ).scalar_one()
            )
            await session.execute(
                text(
                    """
                    INSERT INTO qm_model_inference_runs (
                        run_id, tenant_id, user_id, model_id, data_trade_date,
                        prediction_trade_date, status, signals_count, fallback_used,
                        active_model_id, effective_model_id, model_source,
                        active_data_source, request_json, result_json,
                        created_at, updated_at
                    ) VALUES (
                        :run_id, :tenant_id, :user_id, :model_id, :data_trade_date,
                        :prediction_trade_date, 'completed', 1, FALSE,
                        :model_id, :model_id, 'user_default',
                        'factor_shadow', CAST(:request_json AS JSONB),
                        CAST(:result_json AS JSONB), NOW(), NOW()
                    )
                    ON CONFLICT (run_id)
                    DO UPDATE SET tenant_id = EXCLUDED.tenant_id,
                                  user_id = EXCLUDED.user_id,
                                  model_id = EXCLUDED.model_id,
                                  data_trade_date = EXCLUDED.data_trade_date,
                                  prediction_trade_date = EXCLUDED.prediction_trade_date,
                                  status = 'completed',
                                  signals_count = 1,
                                  fallback_used = FALSE,
                                  active_model_id = EXCLUDED.active_model_id,
                                  effective_model_id = EXCLUDED.effective_model_id,
                                  model_source = EXCLUDED.model_source,
                                  active_data_source = EXCLUDED.active_data_source,
                                  request_json = EXCLUDED.request_json,
                                  result_json = EXCLUDED.result_json,
                                  updated_at = NOW()
                    """
                ),
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "model_id": model_id,
                    "data_trade_date": data_trade_date,
                    "prediction_trade_date": prediction_trade_date,
                    "request_json": json.dumps(
                        {
                            "strategy_id": strategy_id,
                            "source": "factor_shadow_simulation_smoke",
                        },
                        ensure_ascii=False,
                    ),
                    "result_json": json.dumps(
                        {"signal_source": "factor_shadow", "source_signal_run_id": source_signal_run_id},
                        ensure_ascii=False,
                    ),
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO engine_signal_scores (
                        run_id, tenant_id, user_id, trade_date, symbol,
                        model_version, feature_version, light_score, tft_score,
                        fusion_score, risk_weight, regime, score_rank,
                        universe_tag, signal_side, expected_price, quality,
                        created_at
                    ) VALUES (
                        :run_id, :tenant_id, :user_id, :trade_date, 'SH600519',
                        'factor_shadow', :feature_version, 0.95, 0.95,
                        0.95, 1.0, 'smoke', 1,
                        'factor_shadow', 'BUY', 10.0,
                        CAST(:quality AS JSONB), NOW()
                    )
                    ON CONFLICT (
                        tenant_id, user_id, trade_date, symbol, model_version,
                        feature_version, run_id
                    )
                    DO UPDATE SET fusion_score = EXCLUDED.fusion_score,
                                  signal_side = EXCLUDED.signal_side,
                                  expected_price = EXCLUDED.expected_price,
                                  quality = EXCLUDED.quality
                    """
                ),
                {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "trade_date": data_trade_date,
                    "feature_version": feature_version,
                    "quality": json.dumps(
                        {
                            "signal_source": "factor_shadow",
                            "source_signal_run_id": source_signal_run_id,
                            "smoke_stamp": stamp,
                        },
                        ensure_ascii=False,
                    ),
                },
            )

        redis = get_trade_redis()
        _require(redis.client is not None, "trade Redis is unavailable for simulation smoke")
        redis.set(
            redis_key,
            {
                "cash": 100000.0,
                "available_balance": 100000.0,
                "total_asset": 100000.0,
                "market_value": 0.0,
                "positions": {},
            },
            ttl=600,
        )

    async def cleanup_records() -> None:
        get_trade_redis().delete(redis_key)
        async with get_session() as session:
            for statement in (
                "DELETE FROM simulation_cash_ledger WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_position_lots WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_fills WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_orders WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_account_daily WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_fund_snapshots WHERE tenant_id = :tenant_id AND user_id = :user_id",
                "DELETE FROM simulation_accounts WHERE tenant_id = :tenant_id AND user_id = :user_id",
            ):
                await session.execute(
                    text(statement),
                    {"tenant_id": tenant_id, "user_id": user_id},
                )
            await session.execute(
                text("DELETE FROM trade_manual_execution_tasks WHERE task_id = :task_id"),
                {"task_id": authorized_task_id},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM engine_signal_scores
                    WHERE tenant_id = :tenant_id AND user_id = :user_id AND run_id = :run_id
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "run_id": run_id},
            )
            await session.execute(
                text(
                    """
                    DELETE FROM qm_model_inference_runs
                    WHERE tenant_id = :tenant_id AND user_id = :user_id AND run_id = :run_id
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "run_id": run_id},
            )
            if strategy_id:
                await session.execute(
                    text("DELETE FROM strategies WHERE id = :strategy_id"),
                    {"strategy_id": int(strategy_id)},
                )

    try:
        await seed_records()
        _require(strategy_id is not None, "factor shadow simulation strategy was not seeded")
        unauthorized_status = ""
        try:
            await manual_execution_service.create_hosted_task(
                tenant_id=tenant_id,
                user_id=user_id,
                strategy_id=strategy_id,
                trading_mode="SIMULATION",
                execution_config={"trading_mode": "SIMULATION"},
                live_trade_config={"schedule_type": "manual_smoke"},
                trigger_context={
                    "source": "factor_shadow_simulation_smoke",
                    "runner_mode": "SIMULATION",
                },
                task_id=f"hosted_factor_shadow_unauthorized_{stamp}",
            )
        except HTTPException as exc:
            unauthorized_status = str(exc.status_code)
            _require(
                exc.status_code == 409
                and "allow_factor_shadow_signals" in str(exc.detail),
                "factor shadow simulation smoke did not reject unauthorized signals",
            )
        _require(unauthorized_status == "409", "unauthorized factor shadow path did not fail")

        authorized = await manual_execution_service.create_hosted_task(
            tenant_id=tenant_id,
            user_id=user_id,
            strategy_id=strategy_id,
            trading_mode="SIMULATION",
            execution_config={
                "trading_mode": "SIMULATION",
                "allow_factor_shadow_signals": True,
            },
            live_trade_config={"schedule_type": "manual_smoke"},
            trigger_context={
                "source": "factor_shadow_simulation_smoke",
                "runner_mode": "SIMULATION",
                "source_signal_run_id": source_signal_run_id,
            },
            task_id=authorized_task_id,
        )
        task = authorized.get("task") if isinstance(authorized, dict) else {}
        request_payload = (
            task.get("request_json") if isinstance(task, dict) else {}
        )
        signals = request_payload.get("signals") if isinstance(request_payload, dict) else []
        first_signal = signals[0] if signals and isinstance(signals[0], dict) else {}
        quality = first_signal.get("quality") if isinstance(first_signal, dict) else {}
        trigger_context = (
            request_payload.get("trigger_context")
            if isinstance(request_payload, dict)
            else {}
        )
        _require(
            str((task or {}).get("trading_mode") or "") == "SIMULATION",
            "authorized factor shadow hosted task was not SIMULATION",
        )
        _require(
            isinstance(quality, dict) and quality.get("signal_source") == "factor_shadow",
            "authorized factor shadow hosted task lost signal source metadata",
        )
        _require(
            isinstance(trigger_context, dict)
            and trigger_context.get("runner_mode") == "SIMULATION",
            "authorized factor shadow hosted task lost simulation trigger context",
        )

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE trade_manual_execution_tasks
                    SET status = 'validating',
                        stage = 'validating',
                        updated_at = NOW()
                    WHERE task_id = :task_id
                      AND status = 'queued'
                    """
                ),
                {"task_id": authorized_task_id},
            )
            await session.commit()

        from backend.services.trade.simulation.services import (  # noqa: PLC0415
            execution_engine as simulation_execution_engine,
        )

        original_is_trading_day = simulation_execution_engine.calendar_service.is_trading_day
        original_is_trading_time = simulation_execution_engine.calendar_service.is_trading_time
        original_latest_price = (
            simulation_execution_engine.SimulationExecutionEngine._latest_price
        )
        original_buy_cancel_timeout = os.environ.get(
            "MANUAL_TASK_BUY_CANCEL_TIMEOUT_SECONDS"
        )

        async def _smoke_is_trading_day(*args: Any, **kwargs: Any) -> bool:
            _ = (args, kwargs)
            return True

        async def _smoke_is_trading_time(*args: Any, **kwargs: Any) -> dict[str, Any]:
            _ = (args, kwargs)
            return {
                "is_trading_time": True,
                "market_phase": "OPEN",
                "matched_session": "AM",
            }

        async def _smoke_latest_price(
            self: Any,
            symbol: str,
            *,
            user_id: str,
            tenant_id: str,
        ) -> SimpleNamespace:
            _ = (self, symbol, user_id, tenant_id)
            return SimpleNamespace(
                price=9.0,
                price_source="factor_shadow_smoke_fixed",
                suspended=False,
                limit_up=False,
                limit_down=False,
            )

        try:
            simulation_execution_engine.calendar_service.is_trading_day = (
                _smoke_is_trading_day
            )
            simulation_execution_engine.calendar_service.is_trading_time = (
                _smoke_is_trading_time
            )
            simulation_execution_engine.SimulationExecutionEngine._latest_price = (
                _smoke_latest_price
            )
            os.environ["MANUAL_TASK_BUY_CANCEL_TIMEOUT_SECONDS"] = "0"
            await manual_execution_service.execute_task_by_id(authorized_task_id)
        finally:
            if original_buy_cancel_timeout is None:
                os.environ.pop("MANUAL_TASK_BUY_CANCEL_TIMEOUT_SECONDS", None)
            else:
                os.environ["MANUAL_TASK_BUY_CANCEL_TIMEOUT_SECONDS"] = (
                    original_buy_cancel_timeout
                )
            simulation_execution_engine.calendar_service.is_trading_day = (
                original_is_trading_day
            )
            simulation_execution_engine.calendar_service.is_trading_time = (
                original_is_trading_time
            )
            simulation_execution_engine.SimulationExecutionEngine._latest_price = (
                original_latest_price
            )

        async with get_session() as session:
            task_row = (
                await session.execute(
                    text(
                        """
                        SELECT status, stage, result_json
                        FROM trade_manual_execution_tasks
                        WHERE task_id = :task_id
                        """
                    ),
                    {"task_id": authorized_task_id},
                )
            ).mappings().one()
            order_count = int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM simulation_orders
                            WHERE tenant_id = :tenant_id AND user_id = :user_id
                            """
                        ),
                        {"tenant_id": tenant_id, "user_id": user_id},
                    )
                ).scalar()
                or 0
            )
            fill_count = int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM simulation_fills
                            WHERE tenant_id = :tenant_id AND user_id = :user_id
                            """
                        ),
                        {"tenant_id": tenant_id, "user_id": user_id},
                    )
                ).scalar()
                or 0
            )
            position_lot_count = int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM simulation_position_lots
                            WHERE tenant_id = :tenant_id AND user_id = :user_id
                              AND quantity_remaining > 0
                            """
                        ),
                        {"tenant_id": tenant_id, "user_id": user_id},
                    )
                ).scalar()
                or 0
            )
            cash_ledger_count = int(
                (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM simulation_cash_ledger
                            WHERE tenant_id = :tenant_id AND user_id = :user_id
                            """
                        ),
                        {"tenant_id": tenant_id, "user_id": user_id},
                    )
                ).scalar()
                or 0
            )
        result_json = task_row.get("result_json")
        _require(
            task_row.get("status") == "completed" and task_row.get("stage") == "completed",
            "executed factor shadow hosted task did not complete",
        )
        _require(
            isinstance(result_json, dict) and result_json.get("success") is True,
            "executed factor shadow hosted task did not persist success result: "
            f"{json.dumps(result_json, ensure_ascii=False, default=str)}",
        )
        _require(order_count > 0, "factor shadow hosted execution wrote no simulation order")
        _require(fill_count > 0, "factor shadow hosted execution wrote no simulation fill")
        _require(
            position_lot_count > 0,
            "factor shadow hosted execution wrote no simulation position lot",
        )
        _require(
            cash_ledger_count > 0,
            "factor shadow hosted execution wrote no simulation cash ledger",
        )
        return {
            "unauthorized_status": unauthorized_status,
            "authorized_task_status": str(authorized.get("status") or ""),
            "authorized_trading_mode": str((task or {}).get("trading_mode") or ""),
            "executed_task_status": str(task_row.get("status") or ""),
            "execution_order_count": str(order_count),
            "execution_fill_count": str(fill_count),
            "position_lot_count": str(position_lot_count),
            "cash_ledger_count": str(cash_ledger_count),
        }
    finally:
        await cleanup_records()


async def _check_strategy_list(
    client: httpx.AsyncClient,
    token: str,
) -> int:
    payload = _unwrap_api_data(
        await _request_json(
            client,
            "GET",
            "/api/v1/strategies",
            token=token,
            step="list_strategies",
        )
    )
    _require(isinstance(payload, dict), "list_strategies returned non-object payload")
    strategies = payload.get("strategies")
    _require(isinstance(strategies, list), "list_strategies missing strategies list")
    return int(payload.get("total") if payload.get("total") is not None else len(strategies))


async def _check_ai_ide_file_list(
    client: httpx.AsyncClient,
    token: str,
) -> int:
    payload = _unwrap_api_data(
        await _request_json(
            client,
            "GET",
            "/api/v1/ai-ide/files/list",
            token=token,
            step="list_ai_ide_files",
        )
    )
    _require(isinstance(payload, dict), "list_ai_ide_files returned non-object payload")
    items = payload.get("items")
    _require(isinstance(items, list), "list_ai_ide_files missing items list")
    _require("base" in payload, "list_ai_ide_files missing base path")
    return len(items)


async def run_live_api_smoke(
    config: SmokeConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> SmokeResult:
    stamp = str(int(time.time()))
    bootstrapped_window = await _bootstrap_stock_daily_latest_from_westock(config)
    window = await _discover_date_window(config)
    if bootstrapped_window and bootstrapped_window.coverage_days > window.coverage_days:
        window = bootstrapped_window
    steps: list[str] = []
    close_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
        )

    try:
        await _request_json(client, "GET", "/health", step="health")
        steps.append("health")

        token, auth_source, user_id = await _authenticate(client, config, stamp)
        steps.append(auth_source)

        strategy_total: int | None = None
        if config.check_strategy_list:
            strategy_total = await _check_strategy_list(client, token)
            steps.append("list_strategies")

        ai_ide_file_count: int | None = None
        if config.check_ai_ide_files:
            ai_ide_file_count = await _check_ai_ide_file_list(client, token)
            steps.append("list_ai_ide_files")

        candidate_data = _unwrap_api_data(
            await _request_json(
                client,
                "POST",
                "/api/v1/research/factors/candidates",
                token=token,
                step="create_candidate",
                json_body={
                    "name": f"Live API Smoke {stamp}",
                    "expression": config.expression,
                    "source": "live_api_smoke",
                    "family": "smoke",
                    "tags": ["live_api_smoke"],
                    "metadata": {"smoke_stamp": stamp},
                },
            )
        )
        candidate = candidate_data.get("candidate") if isinstance(candidate_data, dict) else {}
        candidate_id = str((candidate or {}).get("id") or "").strip()
        _require(bool(candidate_id), "create_candidate response missing candidate.id")
        steps.append("create_candidate")

        run_data = _unwrap_api_data(
            await _request_json(
                client,
                "POST",
                f"/api/v1/research/factors/candidates/{candidate_id}/evaluate",
                token=token,
                step="evaluate_candidate",
                json_body={
                    "universe": "all",
                    "start_date": window.start_date,
                    "end_date": window.end_date,
                    "n_groups": 5,
                    "holding_period": 5,
                    "neutralize_industry": False,
                    "neutralize_cap": False,
                    "validation_profile": "live_api_smoke",
                    "metadata": {"smoke_stamp": stamp},
                },
            )
        )
        run = run_data.get("run") if isinstance(run_data, dict) else {}
        run_id = str((run or {}).get("id") or "").strip()
        _require(bool(run_id), "evaluate_candidate response missing run.id")
        steps.append("evaluate_candidate")

        run_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                f"/api/v1/research/factors/runs/{run_id}",
                token=token,
                step="get_run",
            )
        )
        run = run_data.get("run") if isinstance(run_data, dict) else {}
        run_status = str((run or {}).get("status") or "").strip()
        metrics = (run or {}).get("metrics") if isinstance((run or {}).get("metrics"), dict) else {}
        _require(run_status == "completed", f"factor run did not complete: {run_status}")
        inserted_values = int(metrics.get("inserted_values") or 0)
        coverage_days = int(metrics.get("coverage_days") or 0)
        _require(inserted_values > 0, "factor run completed without inserted_values")
        _require(coverage_days > 0, "factor run completed without coverage_days")
        steps.append("get_run")

        values_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                f"/api/v1/research/factors/runs/{run_id}/values?limit=5",
                token=token,
                step="list_factor_run_values",
            )
        )
        values_summary = (
            values_data.get("summary") if isinstance(values_data, dict) else {}
        ) or {}
        value_items = values_data.get("items") if isinstance(values_data, dict) else []
        factor_value_total = int(values_summary.get("total") or 0)
        factor_value_sample_count = len(value_items or [])
        _require(
            factor_value_total == inserted_values,
            "factor run values total does not match inserted_values: "
            f"{factor_value_total} != {inserted_values}",
        )
        _require(factor_value_sample_count > 0, "factor run values returned no sample rows")
        _require(
            int(values_summary.get("tradeDateCount") or 0) > 0,
            "factor run values summary missing tradeDateCount",
        )
        _require(
            int(values_summary.get("symbolCount") or 0) > 0,
            "factor run values summary missing symbolCount",
        )
        _require(
            int(values_summary.get("invalidSymbolCount") or 0) == 0,
            "factor run values summary found invalid prefix-format symbols",
        )
        _require(
            int(values_summary.get("sourceCount") or 0) > 0,
            "factor run values summary missing sourceCount",
        )
        _require(
            isinstance(values_summary.get("sourceDistribution"), list),
            "factor run values summary missing sourceDistribution list",
        )
        _require(
            isinstance(values_summary.get("recentDateDistribution"), list),
            "factor run values summary missing recentDateDistribution list",
        )
        steps.append("list_factor_run_values")

        candidates_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                "/api/v1/research/factors/candidates?limit=10",
                token=token,
                step="list_candidates",
            )
        )
        candidate_ids = {
            str(item.get("id") or "")
            for item in (candidates_data.get("items") or [])
            if isinstance(item, dict)
        }
        _require(candidate_id in candidate_ids, "list_candidates did not include created candidate")
        steps.append("list_candidates")

        campaign_flow_id: str | None = None
        campaign_flow_total_candidates: int | None = None
        campaign_flow_completed_generations: int | None = None
        campaign_flow_item_count: int | None = None
        campaign_async_flow_id: str | None = None
        campaign_async_flow_status: str | None = None
        campaign_async_flow_item_count: int | None = None
        campaign_worker_flow_processed: int | None = None
        campaign_worker_flow_event_count: int | None = None
        meta_evolution_flow_id: str | None = None
        meta_evolution_flow_strategy: str | None = None
        meta_evolution_flow_item_count: int | None = None
        factor_value_backfill_job_id: str | None = None
        factor_value_backfill_status: str | None = None
        factor_value_backfill_processed_runs: int | None = None
        factor_value_backfill_event_count: int | None = None
        if config.include_campaign_flow:
            campaign_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "POST",
                    "/api/v1/research/factors/campaigns",
                    token=token,
                    step="create_factor_campaign",
                    json_body={
                        "name": f"live-smoke-campaign-{stamp}",
                        "strategy": "template_mutation",
                        "seed_expression": "rank(ts_delta(close, 5) / ts_shift(close, 5))",
                        "n_candidates": 2,
                        "max_generations": 2,
                        "universe": "all",
                        "start_date": window.start_date,
                        "end_date": window.end_date,
                        "n_groups": 5,
                        "holding_period": 5,
                        "neutralize_industry": False,
                        "neutralize_cap": False,
                        "validation_profile": "live_api_campaign_smoke",
                        "metadata": {"smoke_stamp": stamp},
                    },
                )
            )
            campaign = campaign_data.get("campaign") if isinstance(campaign_data, dict) else {}
            campaign_flow_id = str((campaign or {}).get("id") or "").strip()
            _require(bool(campaign_flow_id), "campaign response missing id")
            summary = (
                (campaign or {}).get("summary")
                if isinstance((campaign or {}).get("summary"), dict)
                else {}
            )
            campaign_flow_total_candidates = int(summary.get("totalCandidates") or 0)
            campaign_flow_completed_generations = int(summary.get("completedGenerations") or 0)
            campaign_items = (
                (campaign or {}).get("items")
                if isinstance((campaign or {}).get("items"), list)
                else []
            )
            campaign_flow_item_count = len(campaign_items)
            _require(
                campaign_flow_total_candidates >= 2,
                f"campaign totalCandidates too small: {campaign_flow_total_candidates}",
            )
            _require(
                campaign_flow_completed_generations >= 1,
                "campaign did not report completed generations",
            )
            _require(campaign_flow_item_count > 0, "campaign returned no items")
            _require(
                isinstance(summary.get("generationStats"), list)
                and len(summary.get("generationStats") or []) >= 1,
                "campaign summary missing generationStats",
            )
            campaign_detail_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "GET",
                    f"/api/v1/research/factors/campaigns/{campaign_flow_id}",
                    token=token,
                    step="get_factor_campaign",
                )
            )
            campaign_detail = (
                campaign_detail_data.get("campaign")
                if isinstance(campaign_detail_data, dict)
                else {}
            )
            campaign_detail_items = (
                campaign_detail.get("items")
                if isinstance(campaign_detail.get("items"), list)
                else []
            )
            _require(
                len(campaign_detail_items) == campaign_flow_item_count,
                "campaign detail item count does not match create response",
            )
            _require(
                any(int(item.get("generation") or 1) >= 2 for item in campaign_detail_items),
                "campaign detail missing second-generation item",
            )

            async_campaign_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "POST",
                    "/api/v1/research/factors/campaigns",
                    token=token,
                    step="create_factor_campaign_async",
                    json_body={
                        "name": f"live-smoke-async-campaign-{stamp}",
                        "run_async": True,
                        "strategy": "template_mutation",
                        "seed_expression": "rank(close / ts_mean(close, 20))",
                        "n_candidates": 1,
                        "max_generations": 1,
                        "universe": "all",
                        "start_date": window.start_date,
                        "end_date": window.end_date,
                        "n_groups": 5,
                        "holding_period": 5,
                        "neutralize_industry": False,
                        "neutralize_cap": False,
                        "validation_profile": "live_api_async_campaign_smoke",
                        "metadata": {"smoke_stamp": stamp, "mode": "async"},
                    },
                )
            )
            async_campaign = (
                async_campaign_data.get("campaign")
                if isinstance(async_campaign_data, dict)
                else {}
            )
            campaign_async_flow_id = str((async_campaign or {}).get("id") or "").strip()
            campaign_async_flow_status = str(
                (async_campaign or {}).get("status") or ""
            ).strip()
            _require(bool(campaign_async_flow_id), "async campaign response missing id")
            _require(
                campaign_async_flow_status in {"pending", "running", "completed"},
                f"async campaign unexpected initial status: {campaign_async_flow_status}",
            )
            deadline = time.monotonic() + config.timeout_seconds
            async_campaign_detail: dict[str, Any] = {}
            while time.monotonic() < deadline:
                async_detail_data = _unwrap_api_data(
                    await _request_json(
                        client,
                        "GET",
                        f"/api/v1/research/factors/campaigns/{campaign_async_flow_id}",
                        token=token,
                        step="get_factor_campaign_async",
                    )
                )
                async_campaign_detail = (
                    async_detail_data.get("campaign")
                    if isinstance(async_detail_data, dict)
                    else {}
                )
                campaign_async_flow_status = str(
                    async_campaign_detail.get("status") or ""
                ).strip()
                if campaign_async_flow_status in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.5)
            async_items = (
                async_campaign_detail.get("items")
                if isinstance(async_campaign_detail.get("items"), list)
                else []
            )
            campaign_async_flow_item_count = len(async_items)
            _require(
                campaign_async_flow_status == "completed",
                f"async campaign did not complete: {campaign_async_flow_status}",
            )
            _require(
                campaign_async_flow_item_count > 0,
                "async campaign completed without items",
            )
            steps.append("campaign_generation_flow")
            steps.append("campaign_async_flow")

            if config.include_campaign_worker_flow:
                worker_specs = [
                    {
                        "worker_id": f"live-smoke-worker-a-{stamp}",
                        "campaign_id": "",
                    },
                    {
                        "worker_id": f"live-smoke-worker-b-{stamp}",
                        "campaign_id": "",
                    },
                ]
                processed_total = 0
                for idx, worker_spec in enumerate(worker_specs):
                    worker_id = worker_spec["worker_id"]
                    worker_campaign_data = _unwrap_api_data(
                        await _request_json(
                            client,
                            "POST",
                            "/api/v1/research/factors/campaigns",
                            token=token,
                            step=f"create_factor_campaign_worker_{idx + 1}",
                            json_body={
                                "name": f"live-smoke-worker-campaign-{idx + 1}-{stamp}",
                                "run_async": True,
                                "strategy": "template_mutation",
                                "seed_expression": "rank(close / ts_mean(close, 20))",
                                "n_candidates": 1,
                                "max_generations": 1,
                                "universe": "all",
                                "start_date": window.start_date,
                                "end_date": window.end_date,
                                "n_groups": 5,
                                "holding_period": 5,
                                "neutralize_industry": False,
                                "neutralize_cap": False,
                                "validation_profile": "live_api_worker_campaign_smoke",
                                "worker_policy": {
                                    "external_worker": True,
                                    "worker_id": worker_id,
                                    "concurrency": 1,
                                    "max_claims": 1,
                                    "heartbeat_interval_seconds": 5,
                                },
                                "retry_policy": {
                                    "max_attempts": 1,
                                    "retry_failed_after_minutes": 5,
                                },
                                "execution_lease": {"lease_seconds": 300},
                                "metadata": {
                                    "smoke_stamp": stamp,
                                    "mode": "external_worker",
                                    "worker_id": worker_id,
                                },
                            },
                        )
                    )
                    worker_campaign = (
                        worker_campaign_data.get("campaign")
                        if isinstance(worker_campaign_data, dict)
                        else {}
                    )
                    worker_campaign_id = str(
                        (worker_campaign or {}).get("id") or ""
                    ).strip()
                    _require(
                        bool(worker_campaign_id),
                        "worker campaign response missing id",
                    )
                    _require(
                        str((worker_campaign or {}).get("status") or "") == "pending",
                        "external worker campaign should remain pending before worker run",
                    )
                    worker_spec["campaign_id"] = worker_campaign_id

                    round_processed_counts = await asyncio.gather(
                        *[
                            run_factor_campaign_worker(
                                once=False,
                                poll_interval=0.1,
                                idle_limit=1,
                                recover_stale_after_minutes=None,
                                worker_id=item["worker_id"],
                                max_claims=1,
                                concurrency=1,
                                heartbeat_interval=None,
                                lease_seconds=300,
                            )
                            for item in worker_specs
                        ]
                    )
                    _require(
                        sum(round_processed_counts) == 1,
                        "worker isolation round should process exactly one campaign",
                    )
                    processed_total += sum(round_processed_counts)
                    worker_detail_data = _unwrap_api_data(
                        await _request_json(
                            client,
                            "GET",
                            f"/api/v1/research/factors/campaigns/{worker_campaign_id}",
                            token=token,
                            step="get_factor_campaign_worker_detail",
                        )
                    )
                    worker_detail = (
                        worker_detail_data.get("campaign")
                        if isinstance(worker_detail_data, dict)
                        else {}
                    )
                    _require(
                        str(worker_detail.get("status") or "") == "completed",
                        f"worker campaign did not complete: {worker_campaign_id}",
                    )
                    _require(
                        len(worker_detail.get("items") or []) > 0,
                        f"worker campaign completed without items: {worker_campaign_id}",
                    )
                campaign_worker_flow_processed = processed_total
                _require(
                    campaign_worker_flow_processed == 2,
                    f"worker processed {campaign_worker_flow_processed}, expected 2",
                )

                campaign_worker_flow_event_count = 0
                processed_worker_ids: set[str] = set()
                for worker_spec in worker_specs:
                    worker_id = worker_spec["worker_id"]
                    worker_events_data = _unwrap_api_data(
                        await _request_json(
                            client,
                            "GET",
                            f"/api/v1/research/factors/campaign-worker-events?worker_id={worker_id}&limit=20",
                            token=token,
                            step="list_factor_campaign_worker_events",
                        )
                    )
                    worker_events = (
                        worker_events_data.get("items")
                        if isinstance(worker_events_data, dict)
                        else []
                    )
                    campaign_worker_flow_event_count += len(worker_events or [])
                    processed_worker_ids.update(
                        str(item.get("workerId") or "")
                        for item in worker_events or []
                        if isinstance(item, dict)
                        and item.get("eventType") == "processed"
                    )
                _require(
                    campaign_worker_flow_event_count >= 2,
                    "worker flow did not record processed worker events",
                )
                _require(
                    processed_worker_ids
                    == {worker_spec["worker_id"] for worker_spec in worker_specs},
                    "worker flow missing processed events for both worker ids",
                )
                steps.append("campaign_worker_flow")

        if config.include_meta_evolution_flow:
            meta_evolution_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "POST",
                    "/api/v1/research/factors/campaigns",
                    token=token,
                    step="create_factor_meta_evolution_campaign",
                    json_body={
                        "name": f"live-smoke-meta-evolution-{stamp}",
                        "strategy": "quantgpt_meta_evolution",
                        "seed_expressions": [
                            "rank(close / ts_mean(close, 20))",
                            "rank(ts_delta(close, 5) / ts_shift(close, 5))",
                        ],
                        "n_candidates": 2,
                        "max_generations": 2,
                        "universe": "all",
                        "start_date": window.start_date,
                        "end_date": window.end_date,
                        "n_groups": 5,
                        "holding_period": 5,
                        "neutralize_industry": False,
                        "neutralize_cap": False,
                        "validation_profile": "live_api_meta_evolution_smoke",
                        "metadata": {"smoke_stamp": stamp, "mode": "meta_evolution"},
                    },
                )
            )
            meta_campaign = (
                meta_evolution_data.get("campaign")
                if isinstance(meta_evolution_data, dict)
                else {}
            )
            meta_evolution_flow_id = str((meta_campaign or {}).get("id") or "").strip()
            meta_evolution_flow_strategy = str(
                (meta_campaign or {}).get("strategy") or ""
            ).strip()
            meta_items = (
                meta_campaign.get("items")
                if isinstance(meta_campaign.get("items"), list)
                else []
            )
            meta_summary = (
                meta_campaign.get("summary")
                if isinstance(meta_campaign.get("summary"), dict)
                else {}
            )
            meta_evolution_flow_item_count = len(meta_items)
            _require(bool(meta_evolution_flow_id), "meta-evolution campaign missing id")
            _require(
                str((meta_campaign or {}).get("status") or "") == "completed",
                "meta-evolution campaign did not complete",
            )
            _require(
                meta_evolution_flow_strategy == "quantgpt_meta_evolution",
                f"unexpected meta-evolution strategy: {meta_evolution_flow_strategy}",
            )
            _require(
                meta_evolution_flow_item_count > 0,
                "meta-evolution campaign returned no items",
            )
            _require(
                all(
                    "rank(" in str(item.get("expression") or "")
                    for item in meta_items
                    if isinstance(item, dict)
                ),
                "meta-evolution campaign returned invalid expression item",
            )
            _require(
                all(
                    isinstance(item.get("metadata"), dict)
                    and item["metadata"].get("operator")
                    for item in meta_items
                    if isinstance(item, dict)
                ),
                "meta-evolution campaign item missing operator metadata",
            )
            _require(
                any(
                    isinstance(item.get("metadata"), dict)
                    and item["metadata"].get("parentExpressions")
                    for item in meta_items
                    if isinstance(item, dict)
                ),
                "meta-evolution campaign item missing parent lineage metadata",
            )
            _require(
                isinstance(meta_summary.get("operatorStats"), list)
                and len(meta_summary.get("operatorStats") or []) > 0,
                "meta-evolution campaign summary missing operatorStats",
            )
            _require(
                isinstance(meta_summary.get("reasonStats"), list)
                and len(meta_summary.get("reasonStats") or []) > 0,
                "meta-evolution campaign summary missing reasonStats",
            )
            _require(
                isinstance(meta_summary.get("lineageEdges"), list)
                and len(meta_summary.get("lineageEdges") or []) > 0,
                "meta-evolution campaign summary missing lineageEdges",
            )
            steps.append("meta_evolution_flow")

        promotion_data = _unwrap_api_data(
            await _request_json(
                client,
                "POST",
                f"/api/v1/research/factors/candidates/{candidate_id}/promote",
                token=token,
                step="promote_candidate",
                json_body={
                    "run_id": run_id,
                    "feature_key": f"factor_live_smoke_{stamp}",
                    "feature_name": f"Live Smoke {stamp}",
                    "force_shadow": True,
                    "metadata": {"smoke_stamp": stamp},
                },
            )
        )
        promotion = promotion_data.get("promotion") if isinstance(promotion_data, dict) else {}
        promotion_id = str((promotion or {}).get("id") or "").strip()
        _require(bool(promotion_id), "promote_candidate response missing promotion.id")
        promotion_status = str((promotion or {}).get("status") or "unknown")
        materialization_status = str((promotion or {}).get("materializationStatus") or promotion_status)
        steps.append("promote_candidate")

        promotions_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                "/api/v1/research/factors/promotions?limit=10",
                token=token,
                step="list_promotions",
            )
        )
        promotion_ids = {
            str(item.get("id") or "")
            for item in (promotions_data.get("items") or [])
            if isinstance(item, dict)
        }
        _require(promotion_id in promotion_ids, "list_promotions did not include created promotion")
        steps.append("list_promotions")

        if config.include_materialize:
            materialized_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "POST",
                    f"/api/v1/research/factors/promotions/{promotion_id}/materialize",
                    token=token,
                    step="materialize_promotion",
                )
            )
            materialized = materialized_data.get("promotion") if isinstance(materialized_data, dict) else {}
            materialization_status = str(
                (materialized or {}).get("materializationStatus")
                or (materialized or {}).get("status")
                or materialization_status
            )
            _require(
                materialization_status == "materialized",
                f"promotion materialization did not complete: {materialization_status}",
            )
            steps.append("materialize_promotion")

        signal_data = _unwrap_api_data(
            await _request_json(
                client,
                "POST",
                f"/api/v1/research/factors/candidates/{candidate_id}/publish-shadow-signal",
                token=token,
                step="publish_shadow_signal",
                json_body={
                    "run_id": run_id,
                    "top_n": config.top_n,
                    "bottom_n": 0,
                    "long_short": False,
                    "quantity": 100,
                    "publish_stream": False,
                    "metadata": {"smoke_stamp": stamp},
                },
            )
        )
        signal_run = signal_data.get("signalRun") if isinstance(signal_data, dict) else {}
        signal_run_id = str((signal_run or {}).get("id") or "").strip()
        signal_count = int((signal_run or {}).get("signalCount") or 0)
        stream_published_count = int((signal_run or {}).get("streamPublishedCount") or 0)
        _require(bool(signal_run_id), "publish_shadow_signal response missing signalRun.id")
        _require(signal_count > 0, "publish_shadow_signal generated no signals")
        _require(stream_published_count == 0, "smoke should not publish shadow signal stream")
        steps.append("publish_shadow_signal")

        if config.include_factor_value_backfill_flow:
            backfill_worker_id = f"live-smoke-backfill-worker-{stamp}"
            backfill_job_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "POST",
                    "/api/v1/research/factors/value-backfills",
                    token=token,
                    step="create_factor_value_backfill_job",
                    json_body={
                        "run_ids": [run_id],
                        "start_date": window.start_date,
                        "end_date": window.end_date,
                        "universe": "all",
                        "holding_period": 5,
                        "dry_run": False,
                        "max_runs": 1,
                        "metadata": {
                            "smoke_stamp": stamp,
                            "mode": "worker_execute",
                        },
                    },
                )
            )
            backfill_job = (
                backfill_job_data.get("job")
                if isinstance(backfill_job_data, dict)
                else {}
            )
            factor_value_backfill_job_id = str(
                (backfill_job or {}).get("id") or ""
            ).strip()
            _require(
                bool(factor_value_backfill_job_id),
                "create_factor_value_backfill_job response missing job.id",
            )
            _require(
                str((backfill_job or {}).get("status") or "") == "pending",
                "factor value backfill job should start pending",
            )
            processed_backfills = await run_factor_value_backfill_worker(
                once=False,
                poll_interval=0.1,
                idle_limit=1,
                worker_id=backfill_worker_id,
                max_claims=1,
                heartbeat_interval=None,
                lease_seconds=300,
            )
            _require(
                processed_backfills == 1,
                f"backfill worker processed {processed_backfills}, expected 1",
            )
            backfill_jobs_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "GET",
                    "/api/v1/research/factors/value-backfills?limit=5",
                    token=token,
                    step="list_factor_value_backfills",
                )
            )
            backfill_items = (
                backfill_jobs_data.get("items")
                if isinstance(backfill_jobs_data, dict)
                else []
            )
            completed_backfill = next(
                (
                    item
                    for item in backfill_items or []
                    if isinstance(item, dict)
                    and str(item.get("id") or "") == factor_value_backfill_job_id
                ),
                None,
            )
            _require(
                isinstance(completed_backfill, dict),
                "list_factor_value_backfills did not include created job",
            )
            factor_value_backfill_status = str(
                completed_backfill.get("status") or ""
            ).strip()
            backfill_result = (
                completed_backfill.get("result")
                if isinstance(completed_backfill.get("result"), dict)
                else {}
            )
            factor_value_backfill_processed_runs = int(
                backfill_result.get("processedRuns") or 0
            )
            _require(
                factor_value_backfill_status == "completed",
                f"factor value backfill did not complete: {factor_value_backfill_status}",
            )
            _require(
                factor_value_backfill_processed_runs >= 1,
                "factor value backfill did not process any run",
            )
            backfill_events_data = _unwrap_api_data(
                await _request_json(
                    client,
                    "GET",
                    f"/api/v1/research/factors/value-backfill-events?job_id={factor_value_backfill_job_id}&limit=20",
                    token=token,
                    step="list_factor_value_backfill_events",
                )
            )
            backfill_events = (
                backfill_events_data.get("items")
                if isinstance(backfill_events_data, dict)
                else []
            )
            factor_value_backfill_event_count = len(backfill_events or [])
            _require(
                any(
                    isinstance(item, dict) and item.get("eventType") == "completed"
                    for item in backfill_events or []
                ),
                "factor value backfill flow did not record completed event",
            )
            steps.append("factor_value_backfill_flow")

        approval_audit_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                "/api/v1/research/factors/approvals?limit=10",
                token=token,
                step="list_approval_audits",
            )
        )
        approval_audit_total = int((approval_audit_data or {}).get("total") or 0)
        _require(
            isinstance((approval_audit_data or {}).get("items"), list),
            "list_approval_audits did not return items list",
        )
        steps.append("list_approval_audits")

        approval_request_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                "/api/v1/research/factors/approval-requests?limit=10",
                token=token,
                step="list_approval_requests",
            )
        )
        approval_request_total = int((approval_request_data or {}).get("total") or 0)
        _require(
            isinstance((approval_request_data or {}).get("items"), list),
            "list_approval_requests did not return items list",
        )
        steps.append("list_approval_requests")

        health_data = _unwrap_api_data(
            await _request_json(
                client,
                "GET",
                "/api/v1/research/factors/health?window_hours=24",
                token=token,
                step="factor_research_health",
            )
        )
        health = health_data.get("health") if isinstance(health_data, dict) else {}
        factor_health_status = str((health or {}).get("status") or "").strip()
        factor_health_alerts = (health or {}).get("alerts")
        factor_slo_status: str | None = None
        factor_slo_breach_count: int | None = None
        _require(
            factor_health_status in {"healthy", "warning", "critical"},
            f"factor_research_health returned invalid status: {factor_health_status}",
        )
        _require(
            isinstance(factor_health_alerts, list),
            "factor_research_health did not return alerts list",
        )
        if config.include_slo_health_flow:
            slo = health.get("slo") if isinstance(health.get("slo"), dict) else {}
            slo_metrics = (
                slo.get("metrics") if isinstance(slo.get("metrics"), dict) else {}
            )
            slo_breaches = (
                slo.get("breaches") if isinstance(slo.get("breaches"), list) else []
            )
            factor_slo_status = str(slo.get("status") or "").strip()
            factor_slo_breach_count = len(slo_breaches)
            _require(
                factor_slo_status in {"met", "breached"},
                f"factor_research_health returned invalid SLO status: {factor_slo_status}",
            )
            for key in [
                "runSuccessRate",
                "campaignSuccessRate",
                "campaignP95DurationSeconds",
                "pendingCampaigns",
                "staleRunningCampaigns",
                "backfillFailedJobs",
            ]:
                _require(key in slo_metrics, f"SLO metrics missing {key}")
            steps.append("slo_health_flow")
        steps.append("factor_research_health")

        approval_flow_result: dict[str, str] = {}
        if config.include_approval_flow:
            approval_flow_result = await _run_factor_approval_service_smoke(
                config,
                stamp=stamp,
            )
            steps.append("approval_service_flow")
        shadow_simulation_result: dict[str, str] = {}
        if config.include_shadow_simulation_flow:
            shadow_simulation_result = await _run_factor_shadow_simulation_hosted_smoke(
                config,
                stamp=stamp,
                source_signal_run_id=signal_run_id,
            )
            steps.append("shadow_simulation_hosted_flow")

        return SmokeResult(
            status="passed",
            base_url=config.base_url,
            auth_source=auth_source,
            tenant_id=config.tenant_id,
            user_id=user_id,
            date_window=window,
            expression=config.expression,
            candidate_id=candidate_id,
            run_id=run_id,
            run_status=run_status,
            inserted_values=inserted_values,
            coverage_days=coverage_days,
            factor_value_total=factor_value_total,
            factor_value_sample_count=factor_value_sample_count,
            promotion_id=promotion_id,
            promotion_status=promotion_status,
            materialization_status=materialization_status,
            signal_run_id=signal_run_id,
            signal_count=signal_count,
            stream_published_count=stream_published_count,
            strategy_total=strategy_total,
            ai_ide_file_count=ai_ide_file_count,
            approval_audit_total=approval_audit_total,
            approval_request_total=approval_request_total,
            factor_health_status=factor_health_status,
            factor_health_alert_count=len(factor_health_alerts),
            factor_slo_status=factor_slo_status,
            factor_slo_breach_count=factor_slo_breach_count,
            campaign_flow_id=campaign_flow_id,
            campaign_flow_total_candidates=campaign_flow_total_candidates,
            campaign_flow_completed_generations=campaign_flow_completed_generations,
            campaign_flow_item_count=campaign_flow_item_count,
            campaign_async_flow_id=campaign_async_flow_id,
            campaign_async_flow_status=campaign_async_flow_status,
            campaign_async_flow_item_count=campaign_async_flow_item_count,
            campaign_worker_flow_processed=campaign_worker_flow_processed,
            campaign_worker_flow_event_count=campaign_worker_flow_event_count,
            meta_evolution_flow_id=meta_evolution_flow_id,
            meta_evolution_flow_strategy=meta_evolution_flow_strategy,
            meta_evolution_flow_item_count=meta_evolution_flow_item_count,
            factor_value_backfill_job_id=factor_value_backfill_job_id,
            factor_value_backfill_status=factor_value_backfill_status,
            factor_value_backfill_processed_runs=factor_value_backfill_processed_runs,
            factor_value_backfill_event_count=factor_value_backfill_event_count,
            approval_flow_request_status=approval_flow_result.get("request_status"),
            approval_flow_review_status=approval_flow_result.get("review_status"),
            approval_flow_reject_status=approval_flow_result.get("reject_status"),
            approval_flow_default_model_id=approval_flow_result.get("default_model_id"),
            approval_flow_notification_count=(
                int(approval_flow_result["notification_count"])
                if approval_flow_result.get("notification_count") is not None
                else None
            ),
            approval_flow_policy_min_approvals=(
                int(approval_flow_result["policy_min_approvals"])
                if approval_flow_result.get("policy_min_approvals") is not None
                else None
            ),
            shadow_simulation_unauthorized_status=(
                int(shadow_simulation_result["unauthorized_status"])
                if shadow_simulation_result.get("unauthorized_status") is not None
                else None
            ),
            shadow_simulation_authorized_task_status=shadow_simulation_result.get(
                "authorized_task_status"
            ),
            shadow_simulation_authorized_trading_mode=shadow_simulation_result.get(
                "authorized_trading_mode"
            ),
            shadow_simulation_executed_task_status=shadow_simulation_result.get(
                "executed_task_status"
            ),
            shadow_simulation_execution_order_count=(
                int(shadow_simulation_result["execution_order_count"])
                if shadow_simulation_result.get("execution_order_count") is not None
                else None
            ),
            shadow_simulation_execution_fill_count=(
                int(shadow_simulation_result["execution_fill_count"])
                if shadow_simulation_result.get("execution_fill_count") is not None
                else None
            ),
            shadow_simulation_position_lot_count=(
                int(shadow_simulation_result["position_lot_count"])
                if shadow_simulation_result.get("position_lot_count") is not None
                else None
            ),
            shadow_simulation_cash_ledger_count=(
                int(shadow_simulation_result["cash_ledger_count"])
                if shadow_simulation_result.get("cash_ledger_count") is not None
                else None
            ),
            steps=steps,
        )
    finally:
        if close_client:
            await client.aclose()


def _parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(
        description="Live QuantMind factor research API smoke test with local real data."
    )
    parser.add_argument("--base-url", default=os.getenv("QUANTMIND_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("QUANTMIND_API_TOKEN"))
    parser.add_argument("--tenant-id", default=os.getenv("QUANTMIND_TENANT_ID", "default"))
    parser.add_argument("--username", default=os.getenv("QUANTMIND_API_USERNAME"))
    parser.add_argument("--password", default=os.getenv("QUANTMIND_API_PASSWORD"))
    parser.add_argument("--email", default=os.getenv("QUANTMIND_API_EMAIL"))
    parser.add_argument("--expression", default="rank(close / ts_mean(close, 20))")
    parser.add_argument("--start-date", default=os.getenv("FACTOR_SMOKE_START_DATE"))
    parser.add_argument("--end-date", default=os.getenv("FACTOR_SMOKE_END_DATE"))
    parser.add_argument(
        "--data-table",
        default=os.getenv("FACTOR_RESEARCH_DATA_TABLE", "stock_daily_latest"),
    )
    parser.add_argument("--lookback-days", type=int, default=80)
    parser.add_argument("--min-symbols-per-day", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--bootstrap-from-westock",
        action="store_true",
        help="Create/fill local stock_daily_latest with public westock-data K-line rows before API checks.",
    )
    parser.add_argument(
        "--bootstrap-symbols",
        default=(
            "SH600519,SZ000001,SH600000,SH601318,SZ000858,SH600036,"
            "SH601166,SH601899,SH601398,SH600030,SZ002594,SZ300750,"
            "SH600276,SH600887,SH600309,SZ000333,SZ002415,SZ000651,"
            "SH601888,SH600900,SZ300059,SH601012,SH601288,SH600028,SH600104"
        ),
    )
    parser.add_argument("--bootstrap-limit", type=int, default=100)
    parser.add_argument(
        "--full-profile",
        action="store_true",
        help=(
            "Run the standard full factor-research acceptance profile: materialize, "
            "bounded campaign, approval flow, and shadow simulation gate checks."
        ),
    )
    parser.add_argument("--include-materialize", action="store_true")
    parser.add_argument(
        "--include-campaign-flow",
        action="store_true",
        help=(
            "Create a bounded multi-generation factor campaign through the live API "
            "and verify campaign detail generation history."
        ),
    )
    parser.add_argument(
        "--include-campaign-worker-flow",
        action="store_true",
        help=(
            "Create external-worker pending campaigns, run the local campaign worker, "
            "and verify campaign completion plus worker event audit rows."
        ),
    )
    parser.add_argument(
        "--include-meta-evolution-flow",
        action="store_true",
        help=(
            "Create a bounded QuantGPT meta-evolution campaign and verify it "
            "produces executable factor research items."
        ),
    )
    parser.add_argument(
        "--include-slo-health-flow",
        action="store_true",
        help=(
            "Verify factor research health includes SLO status, objective metrics, "
            "and breach summaries."
        ),
    )
    parser.add_argument(
        "--include-factor-value-backfill-flow",
        action="store_true",
        help=(
            "Create a factor value backfill job, run the backfill worker once, "
            "and verify completed job/event results."
        ),
    )
    parser.add_argument(
        "--include-approval-flow",
        action="store_true",
        help=(
            "Seed a minimal completed factor training/model record in the local DB "
            "and verify approval request submission, idempotent replay, admin review, "
            "default model setting, and approval audit writes."
        ),
    )
    parser.add_argument(
        "--keep-approval-flow-data",
        action="store_true",
        help="Keep seeded approval-flow smoke rows for debugging instead of cleaning them up.",
    )
    parser.add_argument(
        "--include-shadow-simulation-flow",
        action="store_true",
        help=(
            "Seed a factor_shadow inference/signal and simulation account, then verify "
            "hosted execution rejects unauthorized factor_shadow signals and accepts "
            "explicitly authorized SIMULATION tasks with audit context."
        ),
    )
    parser.add_argument("--skip-strategy-list", action="store_true")
    parser.add_argument("--skip-ai-ide-files", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    include_materialize = args.include_materialize or args.full_profile
    include_campaign_worker_flow = args.include_campaign_worker_flow or args.full_profile
    include_campaign_flow = (
        args.include_campaign_flow or include_campaign_worker_flow or args.full_profile
    )
    include_meta_evolution_flow = (
        args.include_meta_evolution_flow or args.full_profile
    )
    include_slo_health_flow = args.include_slo_health_flow or args.full_profile
    include_factor_value_backfill_flow = (
        args.include_factor_value_backfill_flow or args.full_profile
    )
    include_approval_flow = args.include_approval_flow or args.full_profile
    include_shadow_simulation_flow = (
        args.include_shadow_simulation_flow or args.full_profile
    )
    return SmokeConfig(
        base_url=args.base_url,
        token=args.token,
        tenant_id=args.tenant_id,
        username=args.username,
        password=args.password,
        email=args.email,
        expression=args.expression,
        start_date=args.start_date,
        end_date=args.end_date,
        data_table=args.data_table,
        lookback_days=args.lookback_days,
        min_symbols_per_day=args.min_symbols_per_day,
        top_n=args.top_n,
        bootstrap_from_westock=args.bootstrap_from_westock,
        bootstrap_symbols=[
            item.strip() for item in args.bootstrap_symbols.split(",") if item.strip()
        ],
        bootstrap_limit=args.bootstrap_limit,
        include_materialize=include_materialize,
        include_campaign_flow=include_campaign_flow,
        include_campaign_worker_flow=include_campaign_worker_flow,
        include_meta_evolution_flow=include_meta_evolution_flow,
        include_slo_health_flow=include_slo_health_flow,
        include_factor_value_backfill_flow=include_factor_value_backfill_flow,
        include_approval_flow=include_approval_flow,
        include_shadow_simulation_flow=include_shadow_simulation_flow,
        keep_approval_flow_data=args.keep_approval_flow_data,
        check_strategy_list=not args.skip_strategy_list,
        check_ai_ide_files=not args.skip_ai_ide_files,
        timeout_seconds=args.timeout_seconds,
    )


async def _main_async() -> int:
    config = _parse_args()
    try:
        result = await run_live_api_smoke(config)
    except Exception as exc:
        payload = {"status": "failed", "error": str(exc), "errorType": type(exc).__name__}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    finally:
        await close_database()

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
