"""Factor research candidate persistence and API service helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from backend.services.api.routers.research_factor_market_data import (
    build_factor_values_cte as build_local_factor_values_cte,
    local_market_data_contract,
    prefix_symbol_sql,
    safe_local_market_table_name,
)
from backend.services.engine.research.factor_promotion import (
    evaluate_promotion_eligibility,
)
from backend.services.engine.research.factor_signal_adapter import (
    build_factor_signal_events,
)
from backend.services.engine.research.factor_value_store import (
    upsert_factor_values,
    upsert_factor_values_from_select,
)
from backend.services.engine.research.quantgpt_evolution_adapter import (
    generate_quantgpt_evolution_candidates,
)
from backend.services.engine.research.quantgpt_expression_guard import (
    parse_supported_factor_expression,
)
from backend.services.engine.research.schemas import (
    FactorSignalConfig,
    FactorValueRow,
    QuantGPTCandidateMetrics,
)
from backend.shared.model_registry import model_registry_service
from backend.shared.notification_publisher import publish_notification_async
from backend.shared.factor_research_metrics import update_factor_research_metrics
from backend.shared.stock_utils import StockCodeUtil

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FEATURE_CATALOG_FALLBACK = (
    _PROJECT_ROOT / "config" / "features" / "model_training_feature_catalog_v1.json"
)
_FEATURE_SNAPSHOT_DIR = Path(
    os.getenv(
        "TRAINING_LOCAL_DATA_PATH", str(_PROJECT_ROOT / "db" / "feature_snapshots")
    )
)
_FACTOR_RESEARCH_CATEGORY_ID = "factor_research"
_FACTOR_APPROVAL_PERMISSION = "factor.approve"
_FACTOR_CAMPAIGN_MAX_CANDIDATES_ENV = "QUANTMIND_FACTOR_CAMPAIGN_MAX_CANDIDATES"
_FACTOR_CAMPAIGN_MAX_ACTIVE_ENV = "QUANTMIND_FACTOR_CAMPAIGN_MAX_ACTIVE_PER_USER"
_FACTOR_CAMPAIGN_DAILY_CANDIDATES_ENV = (
    "QUANTMIND_FACTOR_CAMPAIGN_DAILY_CANDIDATE_BUDGET"
)
_FACTOR_CAMPAIGN_STALE_RUNNING_MINUTES_ENV = (
    "QUANTMIND_FACTOR_CAMPAIGN_STALE_RUNNING_MINUTES"
)
_FACTOR_CAMPAIGN_MAX_WORKER_CONCURRENCY_ENV = (
    "QUANTMIND_FACTOR_CAMPAIGN_MAX_WORKER_CONCURRENCY"
)
_FACTOR_CAMPAIGN_MAX_WORKER_CLAIMS_ENV = "QUANTMIND_FACTOR_CAMPAIGN_MAX_WORKER_CLAIMS"
_FACTOR_CAMPAIGN_MAX_LEASE_SECONDS_ENV = "QUANTMIND_FACTOR_CAMPAIGN_MAX_LEASE_SECONDS"
_FACTOR_CAMPAIGN_MAX_RETRY_ATTEMPTS_ENV = (
    "QUANTMIND_FACTOR_CAMPAIGN_MAX_RETRY_ATTEMPTS"
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactorCampaignQuotaPolicy:
    max_candidates_per_campaign: int
    max_active_campaigns_per_user: int
    daily_candidate_budget_per_user: int


def get_session(*args, **kwargs):
    from backend.shared.database_manager_v2 import get_session as _get_session

    return _get_session(*args, **kwargs)


FACTOR_TABLE_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS qm_factor_candidates (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        expression TEXT NOT NULL,
        expression_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        source TEXT NOT NULL DEFAULT 'manual',
        family TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_qm_factor_candidates_scope_expr
    ON qm_factor_candidates (tenant_id, user_id, expression_hash)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_candidates_scope_status
    ON qm_factor_candidates (tenant_id, user_id, status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_candidate_runs (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL REFERENCES qm_factor_candidates(id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        metrics_json JSONB,
        gate_decision_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        report_url TEXT,
        error_message TEXT,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_candidate_runs_candidate_created
    ON qm_factor_candidate_runs (candidate_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_candidate_runs_scope_status
    ON qm_factor_candidate_runs (tenant_id, user_id, status, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_values (
        candidate_id TEXT NOT NULL REFERENCES qm_factor_candidates(id) ON DELETE CASCADE,
        run_id TEXT NOT NULL REFERENCES qm_factor_candidate_runs(id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        trade_date DATE NOT NULL,
        symbol TEXT NOT NULL,
        factor_value DOUBLE PRECISION NOT NULL,
        source TEXT NOT NULL DEFAULT 'local_stock_daily_latest',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (run_id, trade_date, symbol)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_values_candidate_date
    ON qm_factor_values (candidate_id, trade_date DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_value_backfill_jobs (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        target_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        result_json JSONB,
        error_message TEXT,
        worker_id TEXT,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_value_backfill_jobs_scope_status
    ON qm_factor_value_backfill_jobs (tenant_id, user_id, status, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_value_backfill_events (
        id TEXT PRIMARY KEY,
        job_id TEXT REFERENCES qm_factor_value_backfill_jobs(id) ON DELETE SET NULL,
        tenant_id TEXT,
        user_id TEXT,
        worker_id TEXT,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ok',
        details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_value_backfill_events_scope_created
    ON qm_factor_value_backfill_events (tenant_id, user_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_feature_promotions (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL REFERENCES qm_factor_candidates(id) ON DELETE CASCADE,
        run_id TEXT NOT NULL REFERENCES qm_factor_candidate_runs(id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        feature_key TEXT NOT NULL,
        feature_id TEXT NOT NULL,
        version_id TEXT,
        status TEXT NOT NULL,
        materialization_status TEXT NOT NULL DEFAULT 'pending_materialization',
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (run_id, feature_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_feature_promotions_scope_status
    ON qm_factor_feature_promotions (tenant_id, user_id, status, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_feature_category (
        category_id TEXT PRIMARY KEY,
        category_name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_feature_definition (
        feature_id TEXT PRIMARY KEY,
        feature_key TEXT NOT NULL UNIQUE,
        feature_name TEXT NOT NULL,
        formula TEXT,
        source_table_fields TEXT,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_feature_set_version (
        version_id TEXT PRIMARY KEY,
        version_name TEXT NOT NULL,
        feature_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'draft',
        effective_at TIMESTAMPTZ,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_feature_set_version_status
    ON qm_feature_set_version (status, effective_at DESC, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_feature_set_item (
        version_id TEXT NOT NULL REFERENCES qm_feature_set_version(version_id) ON DELETE CASCADE,
        feature_key TEXT NOT NULL REFERENCES qm_feature_definition(feature_key) ON DELETE CASCADE,
        category_id TEXT NOT NULL REFERENCES qm_feature_category(category_id),
        order_no INTEGER NOT NULL DEFAULT 0,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (version_id, feature_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engine_feature_runs (
        run_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        trade_date DATE NOT NULL,
        model_name TEXT,
        model_version TEXT,
        feature_version TEXT,
        feature_dim INTEGER,
        window_start DATE,
        window_end DATE,
        status TEXT NOT NULL,
        expected_symbols INTEGER,
        ready_symbols INTEGER,
        missing_symbols INTEGER,
        source TEXT,
        checksum TEXT,
        quality JSONB NOT NULL DEFAULT '{}'::jsonb,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engine_signal_scores (
        run_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        trade_date DATE NOT NULL,
        symbol TEXT NOT NULL,
        model_version TEXT NOT NULL,
        feature_version TEXT NOT NULL,
        light_score DOUBLE PRECISION,
        tft_score DOUBLE PRECISION,
        fusion_score DOUBLE PRECISION,
        risk_weight DOUBLE PRECISION,
        regime TEXT,
        score_rank INTEGER,
        universe_tag TEXT,
        signal_side TEXT,
        expected_price DOUBLE PRECISION,
        quality JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (tenant_id, user_id, trade_date, symbol, model_version, feature_version, run_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_engine_signal_scores_run
    ON engine_signal_scores (tenant_id, user_id, run_id, fusion_score DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_signal_runs (
        id TEXT PRIMARY KEY,
        candidate_id TEXT NOT NULL REFERENCES qm_factor_candidates(id) ON DELETE CASCADE,
        factor_run_id TEXT NOT NULL REFERENCES qm_factor_candidate_runs(id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        trade_date DATE NOT NULL,
        status TEXT NOT NULL,
        top_n INTEGER NOT NULL DEFAULT 20,
        bottom_n INTEGER NOT NULL DEFAULT 0,
        long_short BOOLEAN NOT NULL DEFAULT FALSE,
        publish_stream BOOLEAN NOT NULL DEFAULT FALSE,
        signal_count INTEGER NOT NULL DEFAULT 0,
        stream_published_count INTEGER NOT NULL DEFAULT 0,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_signal_runs_scope_created
    ON qm_factor_signal_runs (tenant_id, user_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_campaigns (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        strategy TEXT NOT NULL DEFAULT 'template_mutation',
        status TEXT NOT NULL DEFAULT 'pending',
        seed_expression TEXT,
        params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_campaigns_scope_created
    ON qm_factor_campaigns (tenant_id, user_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_campaign_worker_events (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        campaign_id TEXT REFERENCES qm_factor_campaigns(id) ON DELETE SET NULL,
        tenant_id TEXT,
        user_id TEXT,
        worker_id TEXT,
        attempt_no INTEGER,
        duration_ms INTEGER,
        heartbeat_at TIMESTAMPTZ,
        status TEXT NOT NULL DEFAULT 'ok',
        details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    ALTER TABLE qm_factor_campaign_worker_events
    ADD COLUMN IF NOT EXISTS worker_id TEXT
    """,
    """
    ALTER TABLE qm_factor_campaign_worker_events
    ADD COLUMN IF NOT EXISTS attempt_no INTEGER
    """,
    """
    ALTER TABLE qm_factor_campaign_worker_events
    ADD COLUMN IF NOT EXISTS duration_ms INTEGER
    """,
    """
    ALTER TABLE qm_factor_campaign_worker_events
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_campaign_worker_events_scope_created
    ON qm_factor_campaign_worker_events (tenant_id, user_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_campaign_worker_events_worker_created
    ON qm_factor_campaign_worker_events (worker_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_campaign_worker_events_type_created
    ON qm_factor_campaign_worker_events (event_type, status, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_campaign_items (
        campaign_id TEXT NOT NULL REFERENCES qm_factor_campaigns(id) ON DELETE CASCADE,
        candidate_id TEXT REFERENCES qm_factor_candidates(id) ON DELETE SET NULL,
        run_id TEXT REFERENCES qm_factor_candidate_runs(id) ON DELETE SET NULL,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        generation INTEGER NOT NULL DEFAULT 1,
        rank_no INTEGER NOT NULL,
        expression TEXT NOT NULL,
        status TEXT NOT NULL,
        score DOUBLE PRECISION,
        reason TEXT,
        metrics_json JSONB,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (campaign_id, rank_no)
    )
    """,
    """
    ALTER TABLE qm_factor_campaign_items
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_campaign_items_campaign_score
    ON qm_factor_campaign_items (campaign_id, score DESC NULLS LAST, rank_no ASC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_training_runs (
        id TEXT PRIMARY KEY,
        promotion_id TEXT NOT NULL REFERENCES qm_factor_feature_promotions(id) ON DELETE CASCADE,
        candidate_id TEXT NOT NULL REFERENCES qm_factor_candidates(id) ON DELETE CASCADE,
        factor_run_id TEXT NOT NULL REFERENCES qm_factor_candidate_runs(id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        training_run_id TEXT,
        status TEXT NOT NULL,
        feature_key TEXT NOT NULL,
        feature_set_version_id TEXT,
        request_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_training_runs_scope_created
    ON qm_factor_training_runs (tenant_id, user_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_approval_audit (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        training_id TEXT NOT NULL,
        factor_run_id TEXT,
        promotion_id TEXT,
        candidate_id TEXT,
        model_id TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        reason TEXT,
        idempotent BOOLEAN NOT NULL DEFAULT FALSE,
        request_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        approval_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        default_model_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        gate_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_approval_audit_training_created
    ON qm_factor_approval_audit (tenant_id, user_id, training_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_approval_audit_model_created
    ON qm_factor_approval_audit (tenant_id, user_id, model_id, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_approval_requests (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        training_id TEXT NOT NULL,
        model_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_by TEXT NOT NULL,
        request_reason TEXT,
        request_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        reviewer_user_id TEXT,
        reviewer_note TEXT,
        decision_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        reviewed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_qm_factor_approval_requests_pending
    ON qm_factor_approval_requests (tenant_id, user_id, training_id)
    WHERE status = 'pending'
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_qm_factor_approval_requests_scope_status
    ON qm_factor_approval_requests (tenant_id, status, created_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS qm_factor_approval_policies (
        tenant_id TEXT PRIMARY KEY,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        allow_direct_approval BOOLEAN NOT NULL DEFAULT TRUE,
        allow_self_approval BOOLEAN NOT NULL DEFAULT TRUE,
        min_approvals INTEGER NOT NULL DEFAULT 1,
        reviewer_permission TEXT NOT NULL DEFAULT 'factor.approve',
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_by TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
)


def normalize_factor_expression(expression: str) -> str:
    return " ".join(str(expression or "").strip().split())


def factor_expression_hash(expression: str) -> str:
    return hashlib.sha256(
        normalize_factor_expression(expression).encode("utf-8")
    ).hexdigest()


def factor_expression_key(expression: str) -> str:
    return re.sub(r"\s+", "", normalize_factor_expression(expression).lower())


def _json(value: Any) -> str:
    return json.dumps(
        value if value is not None else {}, ensure_ascii=False, separators=(",", ":")
    )


def _json_array(value: Any) -> str:
    return json.dumps(
        value if isinstance(value, list) else [],
        ensure_ascii=False,
        separators=(",", ":"),
    )


async def _list_factor_approval_reviewer_user_ids(
    tenant_id: str,
    *,
    exclude_user_id: str | None = None,
    limit: int = 50,
) -> list[str]:
    """Return active tenant users who can review factor approval requests."""
    try:
        async with get_session(read_only=True) as session:
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT u.user_id
                    FROM users u
                    LEFT JOIN user_roles ur ON ur.user_id = u.user_id
                    LEFT JOIN role_permissions rp ON rp.role_id = ur.role_id
                    LEFT JOIN permissions p
                        ON p.id = rp.permission_id
                       AND p.code = :permission_code
                       AND COALESCE(p.is_active, TRUE) = TRUE
                    WHERE u.tenant_id = :tenant_id
                      AND COALESCE(u.is_active, TRUE) = TRUE
                      AND COALESCE(u.is_deleted, FALSE) = FALSE
                      AND (
                            COALESCE(u.is_admin, FALSE) = TRUE
                         OR p.id IS NOT NULL
                      )
                      AND (:exclude_user_id = '' OR u.user_id <> :exclude_user_id)
                    ORDER BY u.user_id
                    LIMIT :limit
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "permission_code": _FACTOR_APPROVAL_PERMISSION,
                    "exclude_user_id": str(exclude_user_id or ""),
                    "limit": max(1, min(int(limit or 50), 200)),
                },
            )
            return [str(row[0]) for row in result.all()]
    except Exception as exc:  # pragma: no cover - notification best effort
        logger.warning(
            "factor approval reviewer lookup failed: tenant_id=%s error=%s",
            tenant_id,
            exc,
        )
        return []


async def _publish_factor_notification(
    *,
    tenant_id: str,
    user_id: str | None,
    title: str,
    content: str,
    level: str = "info",
) -> bool:
    if not user_id:
        return False
    try:
        return await publish_notification_async(
            tenant_id=tenant_id,
            user_id=str(user_id),
            title=title,
            content=content,
            type="system",
            level=level,
            action_url="/factor-research",
            expire_days=14,
        )
    except Exception as exc:  # pragma: no cover - publisher is best effort
        logger.warning(
            "factor approval notification failed: tenant_id=%s user_id=%s error=%s",
            tenant_id,
            user_id,
            exc,
        )
        return False


async def _notify_factor_approval_request_created(
    tenant_id: str,
    request: dict[str, Any],
) -> dict[str, int]:
    requester_id = str(request.get("userId") or "")
    model_id = str(request.get("modelId") or "-")
    training_id = str(request.get("trainingId") or "-")
    sent = 0

    if await _publish_factor_notification(
        tenant_id=tenant_id,
        user_id=requester_id,
        title="因子模型审批请求已提交",
        content=f"模型 {model_id} 的默认模型审批请求已进入待审队列。",
        level="info",
    ):
        sent += 1

    reviewer_ids = await _list_factor_approval_reviewer_user_ids(
        tenant_id,
        exclude_user_id=requester_id,
    )
    for reviewer_id in reviewer_ids:
        if await _publish_factor_notification(
            tenant_id=tenant_id,
            user_id=reviewer_id,
            title="新的因子模型审批请求",
            content=(
                f"用户 {requester_id} 提交了模型 {model_id} 的默认模型审批请求，"
                f"训练记录 {training_id}。"
            ),
            level="warning",
        ):
            sent += 1
    return {"reviewerCount": len(reviewer_ids), "sent": sent}


async def _notify_factor_approval_request_reviewed(
    tenant_id: str,
    request: dict[str, Any],
) -> bool:
    status = str(request.get("status") or "")
    approved = status == "approved"
    model_id = str(request.get("modelId") or "-")
    reviewer_id = str(request.get("reviewerUserId") or "-")
    title = "因子模型审批已通过" if approved else "因子模型审批已拒绝"
    level = "success" if approved else "warning"
    content = (
        f"模型 {model_id} 的默认模型审批已{'通过' if approved else '拒绝'}，"
        f"审核人 {reviewer_id}。"
    )
    return await _publish_factor_notification(
        tenant_id=tenant_id,
        user_id=str(request.get("userId") or ""),
        title=title,
        content=content,
        level=level,
    )


def _row_to_candidate(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "name": data["name"],
        "expression": data["expression"],
        "expressionHash": data["expression_hash"],
        "description": data.get("description"),
        "source": data.get("source") or "manual",
        "family": data.get("family"),
        "status": data.get("status") or "draft",
        "tags": data.get("tags") or [],
        "metadata": data.get("metadata_json") or {},
        "latestRun": _row_to_run(data, prefix="run_") if data.get("run_id") else None,
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_run(row: Any, *, prefix: str = "") -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data[f"{prefix}id"],
        "candidateId": data[f"{prefix}candidate_id"],
        "status": data.get(f"{prefix}status") or "pending",
        "params": data.get(f"{prefix}params_json") or {},
        "metrics": data.get(f"{prefix}metrics_json"),
        "gateDecision": data.get(f"{prefix}gate_decision_json") or {},
        "reportUrl": data.get(f"{prefix}report_url"),
        "errorMessage": data.get(f"{prefix}error_message"),
        "startedAt": _iso(data.get(f"{prefix}started_at")),
        "completedAt": _iso(data.get(f"{prefix}completed_at")),
        "createdAt": _iso(data.get(f"{prefix}created_at")),
        "updatedAt": _iso(data.get(f"{prefix}updated_at")),
    }


def _row_to_factor_value(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "candidateId": data["candidate_id"],
        "runId": data["run_id"],
        "tradeDate": _iso(data.get("trade_date")),
        "symbol": data["symbol"],
        "factorValue": _float_or_none(data.get("factor_value")),
        "source": data.get("source") or "unknown",
        "createdAt": _iso(data.get("created_at")),
    }


def _row_to_promotion(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "candidateId": data["candidate_id"],
        "runId": data["run_id"],
        "featureKey": data["feature_key"],
        "featureId": data["feature_id"],
        "versionId": data.get("version_id"),
        "status": data.get("status") or "pending_materialization",
        "materializationStatus": data.get("materialization_status")
        or "pending_materialization",
        "metadata": data.get("metadata_json") or {},
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_signal_run(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "candidateId": data["candidate_id"],
        "factorRunId": data["factor_run_id"],
        "tradeDate": str(data["trade_date"])
        if data.get("trade_date") is not None
        else None,
        "status": data.get("status") or "created",
        "topN": int(data.get("top_n") or 0),
        "bottomN": int(data.get("bottom_n") or 0),
        "longShort": bool(data.get("long_short")),
        "publishStream": bool(data.get("publish_stream")),
        "signalCount": int(data.get("signal_count") or 0),
        "streamPublishedCount": int(data.get("stream_published_count") or 0),
        "metadata": data.get("metadata_json") or {},
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_approval_audit(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "tenantId": data["tenant_id"],
        "userId": data["user_id"],
        "trainingId": data["training_id"],
        "factorRunId": data.get("factor_run_id"),
        "promotionId": data.get("promotion_id"),
        "candidateId": data.get("candidate_id"),
        "modelId": data["model_id"],
        "action": data.get("action") or "approve_default_model",
        "status": data.get("status") or "approved",
        "reason": data.get("reason"),
        "idempotent": bool(data.get("idempotent")),
        "requestMetadata": data.get("request_metadata") or {},
        "approval": data.get("approval_json") or {},
        "defaultModel": data.get("default_model_json") or {},
        "gate": data.get("gate_json") or {},
        "createdAt": _iso(data.get("created_at")),
    }


def _row_to_approval_request(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "tenantId": data["tenant_id"],
        "userId": data["user_id"],
        "trainingId": data["training_id"],
        "modelId": data["model_id"],
        "status": data.get("status") or "pending",
        "requestedBy": data.get("requested_by"),
        "requestReason": data.get("request_reason"),
        "requestMetadata": data.get("request_metadata") or {},
        "reviewerUserId": data.get("reviewer_user_id"),
        "reviewerNote": data.get("reviewer_note"),
        "decision": data.get("decision_json") or {},
        "reviewedAt": _iso(data.get("reviewed_at")),
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _default_factor_approval_policy(tenant_id: str) -> dict[str, Any]:
    return {
        "tenantId": tenant_id,
        "enabled": True,
        "allowDirectApproval": True,
        "allowSelfApproval": True,
        "minApprovals": 1,
        "reviewerPermission": _FACTOR_APPROVAL_PERMISSION,
        "metadata": {},
        "updatedBy": None,
        "createdAt": None,
        "updatedAt": None,
        "source": "default",
    }


def _row_to_approval_policy(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "tenantId": data["tenant_id"],
        "enabled": bool(data.get("enabled")),
        "allowDirectApproval": bool(data.get("allow_direct_approval")),
        "allowSelfApproval": bool(data.get("allow_self_approval")),
        "minApprovals": max(1, int(data.get("min_approvals") or 1)),
        "reviewerPermission": data.get("reviewer_permission")
        or _FACTOR_APPROVAL_PERMISSION,
        "metadata": data.get("metadata_json") or {},
        "updatedBy": data.get("updated_by"),
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
        "source": "stored",
    }


def _row_to_campaign(
    row: Any, *, items: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "name": data["name"],
        "strategy": data.get("strategy") or "template_mutation",
        "status": data.get("status") or "pending",
        "seedExpression": data.get("seed_expression"),
        "params": data.get("params_json") or {},
        "summary": data.get("summary_json") or {},
        "metadata": data.get("metadata_json") or {},
        "items": items or [],
        "startedAt": _iso(data.get("started_at")),
        "completedAt": _iso(data.get("completed_at")),
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_campaign_item(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "campaignId": data["campaign_id"],
        "candidateId": data.get("candidate_id"),
        "runId": data.get("run_id"),
        "generation": int(data.get("generation") or 1),
        "rankNo": int(data.get("rank_no") or 0),
        "expression": data.get("expression"),
        "status": data.get("status") or "pending",
        "score": _float_or_none(data.get("score")),
        "reason": data.get("reason"),
        "metrics": data.get("metrics_json"),
        "metadata": data.get("metadata_json") or {},
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_campaign_worker_event(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "eventType": data.get("event_type") or "unknown",
        "campaignId": data.get("campaign_id"),
        "tenantId": data.get("tenant_id"),
        "userId": data.get("user_id"),
        "workerId": data.get("worker_id"),
        "attemptNo": data.get("attempt_no"),
        "durationMs": data.get("duration_ms"),
        "heartbeatAt": _iso(data.get("heartbeat_at")),
        "status": data.get("status") or "ok",
        "details": data.get("details_json") or {},
        "createdAt": _iso(data.get("created_at")),
    }


def _status_counts(rows: list[Any]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        data = dict(row)
        entity = str(data.get("entity") or "unknown")
        status = str(data.get("status") or "unknown")
        counts.setdefault(entity, {})[status] = int(data.get("count") or 0)
    return counts


def _build_factor_health_alerts(
    indicators: dict[str, Any],
    *,
    quota_policy: FactorCampaignQuotaPolicy,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    stale_runs = int(indicators.get("stale_runs") or 0)
    if stale_runs > 0:
        alerts.append(
            {
                "level": "critical",
                "code": "stale_factor_runs",
                "message": "Factor evaluation runs are stale",
                "value": stale_runs,
                "threshold": 0,
            }
        )

    recent_failed_runs = int(indicators.get("recent_failed_runs") or 0)
    if recent_failed_runs > 0:
        alerts.append(
            {
                "level": "warning",
                "code": "recent_failed_factor_runs",
                "message": "Recent factor evaluation runs failed",
                "value": recent_failed_runs,
                "threshold": 0,
            }
        )

    worker_recent_failures = int(indicators.get("worker_recent_failures") or 0)
    if worker_recent_failures > 0:
        alerts.append(
            {
                "level": "warning",
                "code": "factor_campaign_worker_failures",
                "message": "Recent factor campaign worker events failed",
                "value": worker_recent_failures,
                "threshold": 0,
            }
        )

    stale_campaigns = int(indicators.get("stale_campaigns") or 0)
    if stale_campaigns > 0:
        alerts.append(
            {
                "level": "warning",
                "code": "stale_factor_campaigns",
                "message": "Factor campaigns are stale and should be requeued",
                "value": stale_campaigns,
                "threshold": 0,
            }
        )

    active_campaigns = int(indicators.get("active_campaigns") or 0)
    if active_campaigns >= quota_policy.max_active_campaigns_per_user:
        alerts.append(
            {
                "level": "warning",
                "code": "campaign_active_quota_used",
                "message": "Active factor campaign quota is fully used",
                "value": active_campaigns,
                "threshold": quota_policy.max_active_campaigns_per_user,
            }
        )

    today_campaign_candidates = int(indicators.get("today_campaign_candidates") or 0)
    daily_budget = quota_policy.daily_candidate_budget_per_user
    daily_budget_warning_threshold = max(1, int(daily_budget * 0.9))
    if today_campaign_candidates >= daily_budget:
        alerts.append(
            {
                "level": "critical",
                "code": "campaign_daily_candidate_quota_used",
                "message": "Daily factor campaign candidate budget is fully used",
                "value": today_campaign_candidates,
                "threshold": daily_budget,
            }
        )
    elif today_campaign_candidates >= daily_budget_warning_threshold:
        alerts.append(
            {
                "level": "warning",
                "code": "campaign_daily_candidate_quota_near_limit",
                "message": "Daily factor campaign candidate budget is near limit",
                "value": today_campaign_candidates,
                "threshold": daily_budget_warning_threshold,
            }
        )

    pending_materializations = int(indicators.get("pending_materializations") or 0)
    if pending_materializations > 0:
        alerts.append(
            {
                "level": "warning",
                "code": "pending_feature_materializations",
                "message": "Promoted factors are waiting for feature materialization",
                "value": pending_materializations,
                "threshold": 0,
            }
        )

    shadow_stream_published = int(indicators.get("shadow_stream_published") or 0)
    if shadow_stream_published > 0:
        alerts.append(
            {
                "level": "critical",
                "code": "shadow_signal_stream_published",
                "message": "Shadow factor signals were published to Redis stream",
                "value": shadow_stream_published,
                "threshold": 0,
            }
        )

    return alerts


def _factor_health_status(alerts: list[dict[str, Any]]) -> str:
    if any(alert.get("level") == "critical" for alert in alerts):
        return "critical"
    if alerts:
        return "warning"
    return "healthy"


async def get_factor_research_health(
    tenant_id: str,
    user_id: str,
    *,
    window_hours: int = 24,
) -> dict[str, Any]:
    window_hours = max(1, min(int(window_hours or 24), 168))
    quota_policy = _campaign_quota_policy()
    stale_campaign_minutes = _campaign_stale_running_minutes()
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "window_hours": window_hours,
        "stale_campaign_minutes": stale_campaign_minutes,
    }
    async with get_session(read_only=True) as session:
        status_rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT 'candidate' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_candidates
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'run' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_candidate_runs
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'promotion' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_feature_promotions
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'campaign' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_campaigns
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'training' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_training_runs
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'signal' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_signal_runs
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        UNION ALL
                        SELECT 'approval_request' AS entity, status, COUNT(*) AS count
                        FROM qm_factor_approval_requests
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        GROUP BY status
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        indicator_row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_candidate_runs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status IN ('failed', 'rejected')
                                  AND updated_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS recent_failed_runs,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_candidate_runs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status IN ('pending', 'running', 'evaluating')
                                  AND created_at < NOW() - INTERVAL '2 hours'
                            ) AS stale_runs,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_feature_promotions
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND materialization_status = 'pending_materialization'
                            ) AS pending_materializations,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status IN ('pending', 'running')
                            ) AS active_campaigns,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'running'
                                  AND updated_at < NOW() - (
                                      :stale_campaign_minutes * INTERVAL '1 minute'
                                  )
                            ) AS stale_campaigns,
                            (
                                SELECT COALESCE(
                                    SUM(
                                        COALESCE((params_json->>'n_candidates')::int, 0)
                                        * GREATEST(
                                            COALESCE((params_json->>'max_generations')::int, 1),
                                            1
                                        )
                                    ),
                                    0
                                )
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND created_at >= date_trunc('day', NOW())
                            ) AS today_campaign_candidates,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaign_worker_events
                                WHERE (tenant_id = :tenant_id OR tenant_id IS NULL)
                                  AND (user_id = :user_id OR user_id IS NULL)
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS worker_recent_events,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaign_worker_events
                                WHERE (tenant_id = :tenant_id OR tenant_id IS NULL)
                                  AND (user_id = :user_id OR user_id IS NULL)
                                  AND (status IN ('failed', 'error') OR event_type = 'failed')
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS worker_recent_failures,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_approval_requests
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'pending'
                            ) AS pending_approval_requests,
                            (
                                SELECT COALESCE(SUM(stream_published_count), 0)
                                FROM qm_factor_signal_runs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS shadow_stream_published,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_candidate_runs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS window_run_total,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_candidate_runs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'completed'
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS window_run_completed,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS window_campaign_total,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'completed'
                                  AND created_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS window_campaign_completed,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'pending'
                            ) AS pending_campaigns,
                            (
                                SELECT COALESCE(
                                    percentile_cont(0.95) WITHIN GROUP (
                                        ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
                                    ),
                                    0
                                )
                                FROM qm_factor_campaigns
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'completed'
                                  AND started_at IS NOT NULL
                                  AND completed_at IS NOT NULL
                                  AND completed_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS campaign_p95_duration_seconds,
                            (
                                SELECT COUNT(*)
                                FROM qm_factor_value_backfill_jobs
                                WHERE tenant_id = :tenant_id
                                  AND user_id = :user_id
                                  AND status = 'failed'
                                  AND updated_at >= NOW() - (:window_hours * INTERVAL '1 hour')
                            ) AS backfill_failed_jobs
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )

    status_counts = _status_counts(list(status_rows))
    indicators = dict(indicator_row)
    alerts = _build_factor_health_alerts(indicators, quota_policy=quota_policy)
    window_run_total = int(indicators.get("window_run_total") or 0)
    window_campaign_total = int(indicators.get("window_campaign_total") or 0)
    run_success_rate = (
        round(int(indicators.get("window_run_completed") or 0) / window_run_total, 6)
        if window_run_total
        else None
    )
    campaign_success_rate = (
        round(
            int(indicators.get("window_campaign_completed") or 0)
            / window_campaign_total,
            6,
        )
        if window_campaign_total
        else None
    )
    campaign_p95_seconds = round(
        float(indicators.get("campaign_p95_duration_seconds") or 0.0), 3
    )
    slo = {
        "windowHours": window_hours,
        "objectives": {
            "runSuccessRate": 0.9,
            "campaignSuccessRate": 0.9,
            "campaignP95DurationSeconds": 900,
            "pendingCampaigns": 5,
            "staleRunningCampaigns": 0,
            "backfillFailedJobs": 0,
        },
        "metrics": {
            "runSuccessRate": run_success_rate,
            "campaignSuccessRate": campaign_success_rate,
            "campaignP95DurationSeconds": campaign_p95_seconds,
            "pendingCampaigns": int(indicators.get("pending_campaigns") or 0),
            "staleRunningCampaigns": int(indicators.get("stale_campaigns") or 0),
            "backfillFailedJobs": int(indicators.get("backfill_failed_jobs") or 0),
        },
    }
    slo_breaches = []
    if run_success_rate is not None and run_success_rate < 0.9:
        slo_breaches.append("run_success_rate")
    if campaign_success_rate is not None and campaign_success_rate < 0.9:
        slo_breaches.append("campaign_success_rate")
    if campaign_p95_seconds > 900:
        slo_breaches.append("campaign_p95_duration")
    if int(indicators.get("pending_campaigns") or 0) > 5:
        slo_breaches.append("pending_campaigns")
    if int(indicators.get("stale_campaigns") or 0) > 0:
        slo_breaches.append("stale_running_campaigns")
    if int(indicators.get("backfill_failed_jobs") or 0) > 0:
        slo_breaches.append("backfill_failed_jobs")
    slo["breaches"] = slo_breaches
    slo["status"] = "breached" if slo_breaches else "met"
    health = {
        "status": _factor_health_status(alerts),
        "tenantId": tenant_id,
        "userId": user_id,
        "windowHours": window_hours,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "statusCounts": status_counts,
        "indicators": {key: int(value or 0) for key, value in indicators.items()},
        "slo": slo,
        "quotaPolicy": {
            "maxCandidatesPerCampaign": quota_policy.max_candidates_per_campaign,
            "maxActiveCampaignsPerUser": quota_policy.max_active_campaigns_per_user,
            "dailyCandidateBudgetPerUser": quota_policy.daily_candidate_budget_per_user,
        },
        "alerts": alerts,
    }
    try:
        update_factor_research_metrics(health)
    except Exception:
        logger.debug("Failed to update factor research metrics", exc_info=True)
    return health


def _row_to_factor_training_run(row: Any) -> dict[str, Any]:
    data = dict(row)
    training_snapshot = _training_job_snapshot_from_row(data)
    response = dict(data.get("response_json") or {})
    if training_snapshot:
        response["trainingJob"] = training_snapshot

    training_status = (
        (training_snapshot or {}).get("status") or data.get("status") or "created"
    )
    training_progress = (training_snapshot or {}).get("progress")
    training_result = (training_snapshot or {}).get("result") or {}
    training_comparison = (
        training_result.get("comparison") if isinstance(training_result, dict) else None
    )
    if not isinstance(training_comparison, dict):
        training_comparison = (
            response.get("comparison")
            if isinstance(response.get("comparison"), dict)
            else {}
        )
    training_gate = _factor_training_gate_decision(training_comparison)

    return {
        "id": data["id"],
        "promotionId": data["promotion_id"],
        "candidateId": data["candidate_id"],
        "factorRunId": data["factor_run_id"],
        "trainingRunId": data.get("training_run_id"),
        "status": training_status,
        "trainingStatus": training_status,
        "trainingProgress": training_progress,
        "trainingResult": training_result,
        "trainingComparison": training_comparison,
        "trainingGate": training_gate,
        "featureKey": data.get("feature_key"),
        "featureSetVersionId": data.get("feature_set_version_id"),
        "requestPayload": data.get("request_payload_json") or {},
        "response": response,
        "metadata": data.get("metadata_json") or {},
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _training_job_snapshot_from_row(data: dict[str, Any]) -> dict[str, Any] | None:
    training_run_id = str(data.get("training_run_id") or "").strip()
    if not training_run_id or data.get("training_job_status") is None:
        return None

    status = str(data.get("training_job_status") or data.get("status") or "pending")
    request_payload = data.get("training_job_request_payload")
    if not isinstance(request_payload, dict):
        request_payload = (
            data.get("request_payload_json")
            if isinstance(data.get("request_payload_json"), dict)
            else {}
        )
    raw_result = (
        data.get("training_job_result")
        if isinstance(data.get("training_job_result"), dict)
        else {}
    )

    normalized_result, normalize_error = _normalize_factor_training_result_payload(
        raw_result,
        request_payload,
        training_run_id,
        status,
    )
    effective_status = status
    if effective_status == "completed" and normalize_error:
        effective_status = "failed"
        normalized_result["error"] = normalize_error

    comparison = _build_factor_training_comparison(
        promoted_result=normalized_result,
        request_payload=request_payload,
        row=data,
    )
    normalized_result["comparison"] = comparison

    try:
        progress = int(data.get("training_job_progress") or 0)
    except Exception:
        progress = 0

    return {
        "runId": training_run_id,
        "status": effective_status,
        "progress": max(0, min(progress, 100)),
        "result": normalized_result,
        "comparison": comparison,
        "logs": str(data.get("training_job_logs") or ""),
        "isCompleted": effective_status in {"completed", "failed"},
        "updatedAt": _iso(data.get("training_job_updated_at")),
    }


def _factor_training_response_for_storage(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item.get("response") or {})
    if isinstance(item.get("trainingComparison"), dict):
        response["comparison"] = item["trainingComparison"]
    response["syncedAt"] = datetime.now(timezone.utc).isoformat()
    return response


def _normalize_factor_training_result_payload(
    result: dict[str, Any],
    request_payload: dict[str, Any],
    run_id: str,
    status: str,
) -> tuple[dict[str, Any], str | None]:
    raw = result if isinstance(result, dict) else {}
    summary_raw = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    metrics = _normalize_factor_training_metrics(raw)
    artifacts = _normalize_factor_training_artifacts(
        raw.get("artifacts") or raw.get("files")
    )
    error_text = str(raw.get("error") or "").strip()
    validation_error: str | None = None

    if status == "completed" and (metrics is None or not artifacts):
        missing = []
        if metrics is None:
            missing.append("metrics")
        if not artifacts:
            missing.append("artifacts")
        validation_error = f"Training result incomplete: missing {', '.join(missing)}"
        error_text = validation_error

    if status == "failed" and not error_text:
        error_text = "训练任务失败"

    default_summary_status = (
        "训练完成"
        if status == "completed"
        else "训练失败"
        if status == "failed"
        else "进行中"
    )
    default_summary_message = (
        "训练流程执行完成"
        if status == "completed"
        else "训练任务失败"
        if status == "failed"
        else "训练任务执行中。"
    )
    return {
        "metrics": metrics,
        "artifacts": artifacts,
        "summary": {
            "status": str(summary_raw.get("status") or default_summary_status),
            "message": str(
                summary_raw.get("message")
                or summary_raw.get("notes")
                or raw.get("message")
                or default_summary_message
            ),
        },
        "metadata": raw.get("metadata")
        if isinstance(raw.get("metadata"), dict)
        else {"run_id": run_id, "request_payload": request_payload},
        "model_registration": raw.get("model_registration")
        if isinstance(raw.get("model_registration"), dict)
        else {},
        "error": error_text or None,
        "logs": str(raw.get("logs") or ""),
    }, validation_error


def _normalize_factor_training_metrics(
    raw: dict[str, Any],
) -> dict[str, dict[str, float]] | None:
    metrics = raw.get("metrics")
    if isinstance(metrics, dict):
        normalized: dict[str, dict[str, float]] = {}
        for stage in ("train", "val", "test"):
            stage_metrics = metrics.get(stage)
            if not isinstance(stage_metrics, dict):
                return None
            rmse = _float_or_none(stage_metrics.get("rmse"))
            auc = _float_or_none(stage_metrics.get("auc"))
            if rmse is None or auc is None:
                return None
            normalized[stage] = {"rmse": rmse, "auc": auc}
        return normalized
    train_rmse = _float_or_none(raw.get("train_rmse", raw.get("rmse")))
    train_auc = _float_or_none(raw.get("train_auc", raw.get("auc")))
    val_rmse = _float_or_none(raw.get("val_rmse"))
    val_auc = _float_or_none(raw.get("val_auc"))
    test_rmse = _float_or_none(raw.get("test_rmse"))
    test_auc = _float_or_none(raw.get("test_auc"))
    if None in (train_rmse, train_auc, val_rmse, val_auc, test_rmse, test_auc):
        return None
    return {
        "train": {"rmse": float(train_rmse), "auc": float(train_auc)},
        "val": {"rmse": float(val_rmse), "auc": float(val_auc)},
        "test": {"rmse": float(test_rmse), "auc": float(test_auc)},
    }


def _normalize_factor_training_artifacts(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("files") or []
    if not isinstance(raw, list):
        return []
    artifacts: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if name:
                artifacts.append({"name": name})
            continue
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("name") or item.get("filename") or item.get("file") or ""
        ).strip()
        if not name:
            continue
        artifact: dict[str, str] = {"name": name}
        url = str(item.get("url") or "").strip()
        key = str(item.get("key") or item.get("cos_key") or "").strip()
        if url:
            artifact["url"] = url
        if key:
            artifact["key"] = key
        artifacts.append(artifact)
    return artifacts


def _build_factor_training_comparison(
    *,
    promoted_result: dict[str, Any],
    request_payload: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    factor_research = request_payload.get("factor_research")
    if not isinstance(factor_research, dict):
        factor_research = {}

    baseline_run_id = str(
        factor_research.get("baseline_training_run_id")
        or request_payload.get("baseline_training_run_id")
        or ""
    ).strip()
    baseline_metrics = _extract_factor_baseline_metrics(
        factor_research.get("baseline_metrics")
        or request_payload.get("baseline_metrics")
    )
    baseline_source = "request"

    baseline_job_result = row.get("baseline_training_job_result")
    if isinstance(baseline_job_result, dict):
        baseline_result, _ = _normalize_factor_training_result_payload(
            baseline_job_result,
            row.get("baseline_training_job_request_payload")
            if isinstance(row.get("baseline_training_job_request_payload"), dict)
            else {},
            baseline_run_id or str(row.get("baseline_training_run_id") or ""),
            str(row.get("baseline_training_job_status") or "completed"),
        )
        baseline_metrics = (
            baseline_result.get("metrics")
            if isinstance(baseline_result.get("metrics"), dict)
            else baseline_metrics
        )
        baseline_source = "training_run"

    promoted_metrics = (
        promoted_result.get("metrics")
        if isinstance(promoted_result.get("metrics"), dict)
        else None
    )
    if not promoted_metrics:
        return {
            "status": "promoted_metrics_missing",
            "summary": "训练结果缺少 promoted metrics，无法对比。",
            "baselineRunId": baseline_run_id or None,
            "baselineSource": baseline_source if baseline_metrics else None,
            "gate": _factor_training_gate_decision(
                {"status": "promoted_metrics_missing"}
            ),
        }
    if not baseline_metrics:
        return {
            "status": "baseline_missing",
            "summary": "未提供 baseline 训练结果，暂不能判断该因子是否提升模型。",
            "baselineRunId": baseline_run_id or None,
            "promoted": promoted_metrics,
            "gate": _factor_training_gate_decision({"status": "baseline_missing"}),
        }

    promoted_test = (
        promoted_metrics.get("test")
        if isinstance(promoted_metrics.get("test"), dict)
        else {}
    )
    baseline_test = (
        baseline_metrics.get("test")
        if isinstance(baseline_metrics.get("test"), dict)
        else {}
    )
    auc_delta = _metric_delta(promoted_test.get("auc"), baseline_test.get("auc"))
    rmse_delta = _metric_delta(promoted_test.get("rmse"), baseline_test.get("rmse"))

    auc_improved = auc_delta is not None and auc_delta > 0
    auc_regressed = auc_delta is not None and auc_delta < 0
    rmse_regressed = rmse_delta is not None and rmse_delta > 0
    if auc_improved and not rmse_regressed:
        status = "improved"
    elif auc_regressed and rmse_regressed:
        status = "regressed"
    else:
        status = "mixed"

    comparison = {
        "status": status,
        "summary": _factor_training_comparison_summary(status, auc_delta, rmse_delta),
        "baselineRunId": baseline_run_id or None,
        "baselineSource": baseline_source,
        "promoted": promoted_metrics,
        "baseline": baseline_metrics,
        "delta": {
            "test_auc": auc_delta,
            "test_rmse": rmse_delta,
        },
    }
    comparison["gate"] = _factor_training_gate_decision(comparison)
    return comparison


def _extract_factor_baseline_metrics(raw: Any) -> dict[str, dict[str, float]] | None:
    if not isinstance(raw, dict):
        return None
    if isinstance(raw.get("metrics"), dict):
        return _normalize_factor_training_metrics(raw)
    return _normalize_factor_training_metrics(
        {"metrics": raw}
    ) or _normalize_factor_training_metrics(raw)


def _metric_delta(promoted: Any, baseline: Any) -> float | None:
    promoted_value = _float_or_none(promoted)
    baseline_value = _float_or_none(baseline)
    if promoted_value is None or baseline_value is None:
        return None
    return promoted_value - baseline_value


def _factor_training_comparison_summary(
    status: str, auc_delta: float | None, rmse_delta: float | None
) -> str:
    auc_text = "AUC -" if auc_delta is None else f"AUC {auc_delta:+.4f}"
    rmse_text = "RMSE -" if rmse_delta is None else f"RMSE {rmse_delta:+.4f}"
    if status == "improved":
        return f"Promoted 模型优于 baseline：{auc_text} / {rmse_text}。"
    if status == "regressed":
        return f"Promoted 模型弱于 baseline：{auc_text} / {rmse_text}。"
    return f"Promoted 与 baseline 表现混合：{auc_text} / {rmse_text}。"


def _factor_training_gate_decision(comparison: dict[str, Any] | None) -> dict[str, Any]:
    comparison = comparison if isinstance(comparison, dict) else {}
    status = str(comparison.get("status") or "").strip()
    delta = comparison.get("delta") if isinstance(comparison.get("delta"), dict) else {}
    auc_delta = _float_or_none(delta.get("test_auc"))
    rmse_delta = _float_or_none(delta.get("test_rmse"))

    if status == "improved":
        confidence = (
            "strong"
            if (auc_delta or 0) >= 0.01 and (rmse_delta or 0) <= 0
            else "medium"
        )
        return {
            "decision": "approve_model_candidate",
            "severity": "success",
            "confidence": confidence,
            "requiresApproval": True,
            "allowDefaultModelPromotion": True,
            "allowShadowSignalPromotion": True,
            "reasons": ["promoted_model_outperformed_baseline"],
            "summary": "Promoted 模型优于 baseline，可进入模型注册/默认模型审批。",
        }
    if status == "regressed":
        return {
            "decision": "rollback_recommended",
            "severity": "error",
            "confidence": "strong",
            "requiresApproval": True,
            "allowDefaultModelPromotion": False,
            "allowShadowSignalPromotion": False,
            "reasons": ["promoted_model_regressed_vs_baseline"],
            "summary": "Promoted 模型弱于 baseline，建议保留研究记录并回滚该因子。",
        }
    if status == "mixed":
        return {
            "decision": "observe",
            "severity": "warning",
            "confidence": "medium",
            "requiresApproval": True,
            "allowDefaultModelPromotion": False,
            "allowShadowSignalPromotion": False,
            "reasons": ["promoted_model_mixed_vs_baseline"],
            "summary": "Promoted 与 baseline 表现混合，建议进入观察或补充验证。",
        }
    if status in {"baseline_missing", "promoted_metrics_missing"}:
        return {
            "decision": "blocked",
            "severity": "default",
            "confidence": "low",
            "requiresApproval": False,
            "allowDefaultModelPromotion": False,
            "allowShadowSignalPromotion": False,
            "reasons": [status],
            "summary": "训练对比证据不足，暂不能进入模型晋升。",
        }
    return {
        "decision": "pending_comparison",
        "severity": "default",
        "confidence": "low",
        "requiresApproval": False,
        "allowDefaultModelPromotion": False,
        "allowShadowSignalPromotion": False,
        "reasons": ["comparison_pending"],
        "summary": "等待训练结果和 baseline 对比。",
    }


def _factor_training_gate_allows_default_promotion(item: dict[str, Any]) -> bool:
    gate = (
        item.get("trainingGate") if isinstance(item.get("trainingGate"), dict) else {}
    )
    if str(item.get("trainingStatus") or item.get("status") or "") != "completed":
        return False
    return (
        str(gate.get("decision") or "") == "approve_model_candidate"
        and gate.get("allowDefaultModelPromotion") is True
    )


def _extract_registered_model_id_from_training_item(item: dict[str, Any]) -> str:
    result = (
        item.get("trainingResult")
        if isinstance(item.get("trainingResult"), dict)
        else {}
    )
    response = item.get("response") if isinstance(item.get("response"), dict) else {}
    candidates: list[Any] = []
    for container in (result, response):
        registration = (
            container.get("model_registration")
            if isinstance(container.get("model_registration"), dict)
            else {}
        )
        if registration:
            status = str(registration.get("status") or "").strip()
            if status and status != "ready":
                continue
            candidates.extend(
                [
                    registration.get("model_id"),
                    registration.get("registered_model_id"),
                ]
            )
        candidates.extend(
            [
                container.get("registered_model_id"),
                container.get("model_id"),
            ]
        )
    for candidate in candidates:
        model_id = str(candidate or "").strip()
        if model_id:
            return model_id
    return ""


def _factor_training_existing_default_approval(
    item: dict[str, Any],
    model_id: str,
) -> dict[str, Any] | None:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    approval = (
        metadata.get("approval") if isinstance(metadata.get("approval"), dict) else None
    )
    if not approval:
        return None
    if approval.get("default_model_set") is not True:
        return None
    if str(approval.get("model_id") or "").strip() != model_id:
        return None
    return approval


async def _record_factor_training_approval_audit(
    session: Any,
    *,
    tenant_id: str,
    user_id: str,
    training_id: str,
    item: dict[str, Any],
    model_id: str,
    approval: dict[str, Any],
    default_model: dict[str, Any],
    request_payload: dict[str, Any],
    idempotent: bool,
) -> None:
    request_metadata = (
        approval.get("request_metadata")
        if isinstance(approval.get("request_metadata"), dict)
        else request_payload.get("metadata")
        if isinstance(request_payload.get("metadata"), dict)
        else {}
    )
    gate = (
        approval.get("gate")
        if isinstance(approval.get("gate"), dict)
        else item.get("trainingGate")
        if isinstance(item.get("trainingGate"), dict)
        else {}
    )
    await session.execute(
        text(
            """
            INSERT INTO qm_factor_approval_audit (
                id,
                tenant_id,
                user_id,
                training_id,
                factor_run_id,
                promotion_id,
                candidate_id,
                model_id,
                action,
                status,
                reason,
                idempotent,
                request_metadata,
                approval_json,
                default_model_json,
                gate_json
            ) VALUES (
                :audit_id,
                :tenant_id,
                :user_id,
                :training_id,
                :factor_run_id,
                :promotion_id,
                :candidate_id,
                :model_id,
                :action,
                :status,
                :reason,
                :idempotent,
                CAST(:request_metadata AS JSONB),
                CAST(:approval_json AS JSONB),
                CAST(:default_model_json AS JSONB),
                CAST(:gate_json AS JSONB)
            )
            """
        ),
        {
            "audit_id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "training_id": training_id,
            "factor_run_id": item.get("factorRunId"),
            "promotion_id": item.get("promotionId"),
            "candidate_id": item.get("candidateId"),
            "model_id": model_id,
            "action": "approve_default_model",
            "status": "idempotent_replay" if idempotent else "approved",
            "reason": str(
                approval.get("reason")
                or request_payload.get("reason")
                or "factor_research_gate_approved"
            ),
            "idempotent": idempotent,
            "request_metadata": _json(request_metadata),
            "approval_json": _json(approval),
            "default_model_json": _json(default_model),
            "gate_json": _json(gate),
        },
    )


def _resolve_shadow_stream_publish(payload: dict[str, Any]) -> bool:
    publish_stream = bool(payload.get("publish_stream", False))
    allow_shadow_stream = bool(payload.get("allow_shadow_stream", False))
    if publish_stream and not allow_shadow_stream:
        raise ValueError(
            "publish_stream requires allow_shadow_stream=true for shadow signal release"
        )
    return publish_stream


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


async def ensure_research_factor_tables() -> None:
    async with get_session() as session:
        for statement in FACTOR_TABLE_DDL:
            await session.execute(text(statement))


async def create_factor_candidate(
    tenant_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    expression = normalize_factor_expression(str(payload.get("expression") or ""))
    if not expression:
        raise ValueError("factor expression is required")

    candidate_id = str(uuid.uuid4())
    expression_hash = factor_expression_hash(expression)
    name = str(payload.get("name") or "").strip() or expression[:64]
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []

    sql = text(
        """
        INSERT INTO qm_factor_candidates (
            id, tenant_id, user_id, expression, expression_hash, name, description,
            source, family, status, tags, metadata_json, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :user_id, :expression, :expression_hash, :name, :description,
            :source, :family, 'draft', CAST(:tags_json AS JSONB), CAST(:metadata_json AS JSONB), NOW(), NOW()
        )
        ON CONFLICT (tenant_id, user_id, expression_hash)
        DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            source = EXCLUDED.source,
            family = EXCLUDED.family,
            tags = EXCLUDED.tags,
            metadata_json = qm_factor_candidates.metadata_json || EXCLUDED.metadata_json,
            updated_at = NOW()
        RETURNING *
        """
    )
    async with get_session() as session:
        result = await session.execute(
            sql,
            {
                "id": candidate_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "expression": expression,
                "expression_hash": expression_hash,
                "name": name,
                "description": payload.get("description"),
                "source": payload.get("source") or "manual",
                "family": payload.get("family"),
                "tags_json": _json_array(tags),
                "metadata_json": _json(payload.get("metadata") or {}),
            },
        )
        row = result.mappings().one()
    return _row_to_candidate(row)


async def list_factor_candidates(
    tenant_id: str,
    user_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    where = ["c.tenant_id = :tenant_id", "c.user_id = :user_id"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    if status:
        where.append("c.status = :status")
        params["status"] = status
    where_sql = " AND ".join(where)

    list_sql = text(
        f"""
        SELECT
            c.*,
            r.id AS run_id,
            r.candidate_id AS run_candidate_id,
            r.status AS run_status,
            r.params_json AS run_params_json,
            r.metrics_json AS run_metrics_json,
            r.gate_decision_json AS run_gate_decision_json,
            r.report_url AS run_report_url,
            r.error_message AS run_error_message,
            r.started_at AS run_started_at,
            r.completed_at AS run_completed_at,
            r.created_at AS run_created_at,
            r.updated_at AS run_updated_at
        FROM qm_factor_candidates c
        LEFT JOIN LATERAL (
            SELECT *
            FROM qm_factor_candidate_runs r0
            WHERE r0.candidate_id = c.id
            ORDER BY r0.created_at DESC
            LIMIT 1
        ) r ON TRUE
        WHERE {where_sql}
        ORDER BY c.updated_at DESC
        LIMIT :limit OFFSET :offset
        """
    )
    count_sql = text(f"SELECT COUNT(*) FROM qm_factor_candidates c WHERE {where_sql}")

    async with get_session(read_only=True) as session:
        rows = (await session.execute(list_sql, params)).mappings().all()
        total = int((await session.execute(count_sql, params)).scalar_one() or 0)

    return {
        "items": [_row_to_candidate(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def create_factor_evaluation_run(
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    params = {
        "universe": payload.get("universe") or "hs300",
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "n_groups": int(payload.get("n_groups") or 5),
        "holding_period": int(payload.get("holding_period") or 5),
        "neutralize_industry": bool(payload.get("neutralize_industry", True)),
        "neutralize_cap": bool(payload.get("neutralize_cap", True)),
        "validation_profile": payload.get("validation_profile") or "default",
        "metadata": payload.get("metadata") or {},
    }
    gate_decision = {
        "eligible": False,
        "reasons": ["evaluation_pending"],
        "policy": "default",
    }

    async with get_session() as session:
        candidate = (
            await session.execute(
                text(
                    """
                    SELECT id
                    FROM qm_factor_candidates
                    WHERE id = :candidate_id AND tenant_id = :tenant_id AND user_id = :user_id
                    """
                ),
                {
                    "candidate_id": candidate_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                },
            )
        ).first()
        if not candidate:
            raise LookupError("factor candidate not found")

        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_candidate_runs (
                    id, candidate_id, tenant_id, user_id, status, params_json,
                    gate_decision_json, created_at, updated_at
                )
                VALUES (
                    :id, :candidate_id, :tenant_id, :user_id, 'pending',
                    CAST(:params_json AS JSONB), CAST(:gate_decision_json AS JSONB), NOW(), NOW()
                )
                RETURNING *
                """
            ),
            {
                "id": run_id,
                "candidate_id": candidate_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "params_json": _json(params),
                "gate_decision_json": _json(gate_decision),
            },
        )
        await session.execute(
            text(
                """
                UPDATE qm_factor_candidates
                SET status = 'evaluating', updated_at = NOW()
                WHERE id = :candidate_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"candidate_id": candidate_id, "tenant_id": tenant_id, "user_id": user_id},
        )
        row = result.mappings().one()
    run = _row_to_run(row)
    if os.getenv("FACTOR_RESEARCH_SYNC_EVAL", "true").lower() != "false":
        return await evaluate_factor_run_locally(tenant_id, user_id, run_id)
    return run


async def get_factor_evaluation_run(
    tenant_id: str, user_id: str, run_id: str
) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        result = await session.execute(
            text(
                """
                SELECT *
                FROM qm_factor_candidate_runs
                WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"run_id": run_id, "tenant_id": tenant_id, "user_id": user_id},
        )
        row = result.mappings().first()
    if not row:
        raise LookupError("factor evaluation run not found")
    return _row_to_run(row)


async def list_factor_run_values(
    tenant_id: str,
    user_id: str,
    run_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Compatibility wrapper for engine-side factor value store."""
    from backend.services.engine.research.factor_value_store import (
        list_factor_run_values as _engine_list_factor_run_values,
    )

    return await _engine_list_factor_run_values(
        tenant_id,
        user_id,
        run_id,
        limit=limit,
        offset=offset,
    )


async def promote_factor_candidate(
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    async with get_session() as session:
        candidate_row = await _get_candidate_and_run_for_promotion(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            candidate_id=candidate_id,
            run_id=payload.get("run_id"),
        )
        if not candidate_row:
            raise LookupError("factor candidate or completed run not found")

        if str(candidate_row["run_status"]) != "completed":
            raise ValueError("only completed factor evaluation runs can be promoted")

        gate_decision = candidate_row.get("run_gate_decision_json") or {}
        force_shadow = bool(payload.get("force_shadow", True))
        if not gate_decision.get("eligible") and not force_shadow:
            raise ValueError("factor run has not passed promotion gate")

        value_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        """
                    ),
                    {
                        "run_id": candidate_row["run_id"],
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            ).scalar_one()
            or 0
        )
        if value_count <= 0:
            raise ValueError("factor values are required before feature promotion")

        expression_hash = str(candidate_row["expression_hash"])
        feature_key = _safe_feature_key(
            payload.get("feature_key") or f"factor_{expression_hash[:16]}"
        )
        feature_id = _factor_feature_id(feature_key)
        materialization = _check_feature_snapshot_materialization(feature_key)
        materialized = materialization["status"] == "materialized"
        feature_name = str(
            payload.get("feature_name") or candidate_row["name"] or feature_key
        ).strip()
        if not feature_name:
            feature_name = feature_key

        version_id = await _create_factor_shadow_feature_set(
            session,
            feature_key=feature_key,
            feature_id=feature_id,
            feature_name=feature_name,
            formula=str(candidate_row["expression"]),
            run_id=str(candidate_row["run_id"]),
            candidate_id=candidate_id,
            materialized=materialized,
        )

        promotion_status = "materialized" if materialized else "pending_materialization"
        metadata = {
            "source": "factor_research",
            "candidate_id": candidate_id,
            "run_id": str(candidate_row["run_id"]),
            "gate_decision": gate_decision,
            "metrics": candidate_row.get("run_metrics_json") or {},
            "factor_value_count": value_count,
            "materialization": materialization,
            "force_shadow": force_shadow,
        }
        promotion_id = str(uuid.uuid4())
        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_feature_promotions (
                    id, candidate_id, run_id, tenant_id, user_id, feature_key, feature_id,
                    version_id, status, materialization_status, metadata_json, created_at, updated_at
                )
                VALUES (
                    :id, :candidate_id, :run_id, :tenant_id, :user_id, :feature_key, :feature_id,
                    :version_id, :status, :materialization_status, CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                ON CONFLICT (run_id, feature_key)
                DO UPDATE SET
                    version_id = EXCLUDED.version_id,
                    status = EXCLUDED.status,
                    materialization_status = EXCLUDED.materialization_status,
                    metadata_json = qm_factor_feature_promotions.metadata_json || EXCLUDED.metadata_json,
                    updated_at = NOW()
                RETURNING *
                """
            ),
            {
                "id": promotion_id,
                "candidate_id": candidate_id,
                "run_id": str(candidate_row["run_id"]),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "feature_key": feature_key,
                "feature_id": feature_id,
                "version_id": version_id,
                "status": promotion_status,
                "materialization_status": promotion_status,
                "metadata_json": _json(metadata),
            },
        )
        await session.execute(
            text(
                """
                UPDATE qm_factor_candidates
                SET status = 'promoted', updated_at = NOW()
                WHERE id = :candidate_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"candidate_id": candidate_id, "tenant_id": tenant_id, "user_id": user_id},
        )
        row = result.mappings().one()
    return _row_to_promotion(row)


async def list_factor_feature_promotions(
    tenant_id: str,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    async with get_session(read_only=True) as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_feature_promotions
                    WHERE tenant_id = :tenant_id AND user_id = :user_id
                    ORDER BY updated_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM qm_factor_feature_promotions
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_promotion(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def materialize_factor_feature_promotion(
    tenant_id: str,
    user_id: str,
    promotion_id: str,
) -> dict[str, Any]:
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_feature_promotions
                    WHERE id = :promotion_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                    ),
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise LookupError("factor feature promotion not found")

        values = (
            (
                await session.execute(
                    text(
                        """
                    SELECT trade_date, symbol, factor_value
                    FROM qm_factor_values
                    WHERE run_id = :run_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    ORDER BY trade_date ASC, symbol ASC
                    """
                    ),
                    {
                        "run_id": row["run_id"],
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .all()
        )
        if not values:
            raise ValueError("factor values are required before materialization")

        value_rows = [dict(item) for item in values]
        base_data = await _load_local_snapshot_base_rows_for_factor_values(
            session, value_rows
        )
        materialization = _materialize_feature_values_to_snapshots(
            feature_key=str(row["feature_key"]),
            values=value_rows,
            base_rows=base_data.get("rows") or None,
        )
        materialization["base_data"] = {
            key: value for key, value in base_data.items() if key != "rows"
        }
        materialized = materialization["status"] == "materialized"
        status = "materialized" if materialized else "pending_materialization"
        metadata = dict(row.get("metadata_json") or {})
        metadata["materialization"] = materialization

        await session.execute(
            text(
                """
                UPDATE qm_factor_feature_promotions
                SET status = :status,
                    materialization_status = :status,
                    metadata_json = CAST(:metadata_json AS JSONB),
                    updated_at = NOW()
                WHERE id = :promotion_id
                  AND tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {
                "promotion_id": promotion_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "status": status,
                "metadata_json": _json(metadata),
            },
        )
        if materialized:
            await _activate_materialized_feature_set(
                session,
                version_id=str(row["version_id"] or ""),
                feature_key=str(row["feature_key"]),
            )
        refreshed = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_feature_promotions
                    WHERE id = :promotion_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                    ),
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
    return _row_to_promotion(refreshed)


async def rollback_factor_feature_promotion(
    tenant_id: str,
    user_id: str,
    promotion_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    reason = (
        str(payload.get("reason") or "manual_rollback").strip() or "manual_rollback"
    )
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_feature_promotions
                    WHERE id = :promotion_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                    ),
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not row:
            raise LookupError("factor feature promotion not found")

        feature_key = str(row["feature_key"])
        active_items = await _load_active_feature_catalog_items(session)
        rollback_version_id: str | None = None
        if any(
            item.get("feature_key") == feature_key and item.get("enabled", True)
            for item in active_items
        ):
            rollback_version_id = await _activate_feature_set_without_feature(
                session,
                feature_key=feature_key,
                promotion_id=promotion_id,
                reason=reason,
                base_items=active_items,
            )

        metadata = dict(row.get("metadata_json") or {})
        metadata["rollback"] = {
            "status": "rolled_back",
            "reason": reason,
            "previous_version_id": row.get("version_id"),
            "rollback_version_id": rollback_version_id,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        }
        await session.execute(
            text(
                """
                UPDATE qm_factor_feature_promotions
                SET status = 'rolled_back',
                    materialization_status = 'rolled_back',
                    metadata_json = CAST(:metadata_json AS JSONB),
                    updated_at = NOW()
                WHERE id = :promotion_id
                  AND tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {
                "promotion_id": promotion_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "metadata_json": _json(metadata),
            },
        )
        refreshed = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_feature_promotions
                    WHERE id = :promotion_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                    ),
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
    return _row_to_promotion(refreshed)


async def launch_factor_promotion_training(
    tenant_id: str,
    user_id: str,
    promotion_id: str,
    payload: dict[str, Any] | None,
    *,
    background_tasks: Any,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    payload = payload or {}
    async with get_session() as session:
        promotion_row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        p.*,
                        c.name AS candidate_name,
                        c.expression,
                        r.params_json AS run_params_json
                    FROM qm_factor_feature_promotions p
                    JOIN qm_factor_candidates c ON c.id = p.candidate_id
                    JOIN qm_factor_candidate_runs r ON r.id = p.run_id
                    WHERE p.id = :promotion_id
                      AND p.tenant_id = :tenant_id
                      AND p.user_id = :user_id
                    """
                    ),
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not promotion_row:
            raise LookupError("factor feature promotion not found")
        if str(promotion_row["materialization_status"]) != "materialized":
            raise ValueError("factor feature must be materialized before training")

        active_items = await _load_active_feature_catalog_items(session)
        active_features = [
            item["feature_key"] for item in active_items if item.get("enabled", True)
        ]
        feature_key = str(promotion_row["feature_key"])
        if feature_key not in active_features:
            raise ValueError("factor feature is not active in training feature catalog")

    from backend.services.api.routers.admin.admin_training import submit_training_job

    baseline_training_run_id = str(payload.get("baseline_training_run_id") or "")
    auto_baseline_requested = _should_launch_auto_baseline_training(payload)
    baseline_metadata: dict[str, Any] | None = None
    if auto_baseline_requested and any(
        feature != feature_key for feature in active_features
    ):
        baseline_payload = _build_factor_training_payload(
            dict(promotion_row), active_features, payload, include_factor=False
        )
        baseline_response = await submit_training_job(
            baseline_payload, background_tasks, current_user
        )
        baseline_training_run_id = str(baseline_response.get("runId") or "")
        if not baseline_training_run_id:
            raise ValueError("baseline training service did not return runId")
        baseline_metadata = _factor_training_record_metadata(
            feature_key=feature_key,
            pipeline_stage="factor_baseline_training",
            payload=payload,
            extra={"auto_baseline_for_promotion": promotion_id},
        )
        await _insert_factor_training_run_record(
            promotion_row=dict(promotion_row),
            tenant_id=tenant_id,
            user_id=user_id,
            promotion_id=promotion_id,
            training_run_id=baseline_training_run_id,
            training_response=baseline_response,
            training_payload=baseline_payload,
            metadata=baseline_metadata,
        )
    elif auto_baseline_requested:
        payload = {
            **payload,
            "metadata": {
                **(
                    payload.get("metadata")
                    if isinstance(payload.get("metadata"), dict)
                    else {}
                ),
                "auto_baseline_skipped_reason": "no_non_factor_features",
            },
        }

    training_payload = _build_factor_training_payload(
        dict(promotion_row),
        active_features,
        payload,
        baseline_training_run_id=baseline_training_run_id or None,
    )

    training_response = await submit_training_job(
        training_payload, background_tasks, current_user
    )
    training_run_id = str(training_response.get("runId") or "")
    if not training_run_id:
        raise ValueError("training service did not return runId")

    metadata = _factor_training_record_metadata(
        feature_key=feature_key,
        pipeline_stage="factor_shadow_training",
        payload=payload,
        extra={
            "auto_baseline_training_run_id": baseline_training_run_id or None,
            "auto_baseline_submitted": bool(baseline_metadata),
        },
    )
    row = await _insert_factor_training_run_record(
        promotion_row=dict(promotion_row),
        tenant_id=tenant_id,
        user_id=user_id,
        promotion_id=promotion_id,
        training_run_id=training_run_id,
        training_response=training_response,
        training_payload=training_payload,
        metadata=metadata,
    )
    return _row_to_factor_training_run(row)


def _should_launch_auto_baseline_training(payload: dict[str, Any]) -> bool:
    if payload.get("auto_baseline") is False:
        return False
    if str(payload.get("baseline_training_run_id") or "").strip():
        return False
    return not isinstance(payload.get("baseline_metrics"), dict)


def _factor_training_record_metadata(
    *,
    feature_key: str,
    pipeline_stage: str,
    payload: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": "factor_research",
        "pipeline_stage": pipeline_stage,
        "feature_key": feature_key,
        **(
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        ),
        **(extra or {}),
    }


async def _insert_factor_training_run_record(
    *,
    promotion_row: dict[str, Any],
    tenant_id: str,
    user_id: str,
    promotion_id: str,
    training_run_id: str,
    training_response: dict[str, Any],
    training_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> Any:
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_training_runs (
                    id, promotion_id, candidate_id, factor_run_id, tenant_id, user_id,
                    training_run_id, status, feature_key, feature_set_version_id,
                    request_payload_json, response_json, metadata_json, created_at, updated_at
                )
                VALUES (
                    :id, :promotion_id, :candidate_id, :factor_run_id, :tenant_id, :user_id,
                    :training_run_id, :status, :feature_key, :feature_set_version_id,
                    CAST(:request_payload_json AS JSONB), CAST(:response_json AS JSONB),
                    CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                RETURNING *
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "promotion_id": promotion_id,
                "candidate_id": str(promotion_row["candidate_id"]),
                "factor_run_id": str(promotion_row["run_id"]),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "training_run_id": training_run_id,
                "status": str(training_response.get("status") or "pending"),
                "feature_key": str(promotion_row["feature_key"]),
                "feature_set_version_id": promotion_row.get("version_id"),
                "request_payload_json": _json(training_payload),
                "response_json": _json(training_response),
                "metadata_json": _json(metadata),
            },
        )
        return result.mappings().one()


async def list_factor_training_runs(
    tenant_id: str,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        f.*,
                        j.status AS training_job_status,
                        j.progress AS training_job_progress,
                        j.result AS training_job_result,
                        j.logs AS training_job_logs,
                        j.request_payload AS training_job_request_payload,
                        j.updated_at AS training_job_updated_at,
                        b.id AS baseline_training_run_id,
                        b.status AS baseline_training_job_status,
                        b.result AS baseline_training_job_result,
                        b.request_payload AS baseline_training_job_request_payload
                    FROM qm_factor_training_runs f
                    LEFT JOIN admin_training_jobs j
                      ON j.id = f.training_run_id
                     AND j.tenant_id = f.tenant_id
                     AND j.user_id = f.user_id
                    LEFT JOIN admin_training_jobs b
                      ON b.id = COALESCE(
                            f.request_payload_json->'factor_research'->>'baseline_training_run_id',
                            f.request_payload_json->>'baseline_training_run_id'
                         )
                     AND b.tenant_id = f.tenant_id
                     AND b.user_id = f.user_id
                    WHERE f.tenant_id = :tenant_id AND f.user_id = :user_id
                    ORDER BY f.created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM qm_factor_training_runs
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
        items = [_row_to_factor_training_run(row) for row in rows]
        for item in items:
            if not item.get("trainingRunId"):
                continue
            await session.execute(
                text(
                    """
                    UPDATE qm_factor_training_runs
                    SET status = :status,
                        response_json = CAST(:response_json AS JSONB),
                        updated_at = NOW()
                    WHERE id = :id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND (
                        status IS DISTINCT FROM :status
                        OR response_json IS DISTINCT FROM CAST(:response_json AS JSONB)
                      )
                    """
                ),
                {
                    "id": item["id"],
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "status": item["status"],
                    "response_json": _json(_factor_training_response_for_storage(item)),
                },
            )
    return {
        "items": items,
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def list_factor_approval_audits(
    tenant_id: str,
    user_id: str,
    *,
    training_id: str | None = None,
    model_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    where = ["tenant_id = :tenant_id", "user_id = :user_id"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    if training_id:
        where.append("training_id = :training_id")
        params["training_id"] = str(training_id)
    if model_id:
        where.append("model_id = :model_id")
        params["model_id"] = str(model_id)
    if status:
        where.append("status = :status")
        params["status"] = str(status)
    where_sql = " AND ".join(where)

    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM qm_factor_approval_audit
                        WHERE {where_sql}
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM qm_factor_approval_audit
                        WHERE {where_sql}
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_approval_audit(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def get_factor_approval_policy(tenant_id: str) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_approval_policies
                        WHERE tenant_id = :tenant_id
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        return _default_factor_approval_policy(tenant_id)
    return _row_to_approval_policy(row)


async def upsert_factor_approval_policy(
    tenant_id: str,
    payload: dict[str, Any] | None = None,
    *,
    updated_by: str | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    current = await get_factor_approval_policy(tenant_id)

    def pick_bool(key: str, current_key: str) -> bool:
        value = payload.get(key)
        return bool(current[current_key] if value is None else value)

    min_approvals = max(
        1,
        min(
            10,
            int(payload.get("min_approvals") or current.get("minApprovals") or 1),
        ),
    )
    reviewer_permission = (
        str(
            payload.get("reviewer_permission")
            or current.get("reviewerPermission")
            or _FACTOR_APPROVAL_PERMISSION
        ).strip()
        or _FACTOR_APPROVAL_PERMISSION
    )
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = (
            current.get("metadata") if isinstance(current.get("metadata"), dict) else {}
        )

    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_factor_approval_policies (
                            tenant_id,
                            enabled,
                            allow_direct_approval,
                            allow_self_approval,
                            min_approvals,
                            reviewer_permission,
                            metadata_json,
                            updated_by,
                            created_at,
                            updated_at
                        ) VALUES (
                            :tenant_id,
                            :enabled,
                            :allow_direct_approval,
                            :allow_self_approval,
                            :min_approvals,
                            :reviewer_permission,
                            CAST(:metadata_json AS JSONB),
                            :updated_by,
                            NOW(),
                            NOW()
                        )
                        ON CONFLICT (tenant_id)
                        DO UPDATE SET enabled = EXCLUDED.enabled,
                                      allow_direct_approval = EXCLUDED.allow_direct_approval,
                                      allow_self_approval = EXCLUDED.allow_self_approval,
                                      min_approvals = EXCLUDED.min_approvals,
                                      reviewer_permission = EXCLUDED.reviewer_permission,
                                      metadata_json = EXCLUDED.metadata_json,
                                      updated_by = EXCLUDED.updated_by,
                                      updated_at = NOW()
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "enabled": pick_bool("enabled", "enabled"),
                        "allow_direct_approval": pick_bool(
                            "allow_direct_approval", "allowDirectApproval"
                        ),
                        "allow_self_approval": pick_bool(
                            "allow_self_approval", "allowSelfApproval"
                        ),
                        "min_approvals": min_approvals,
                        "reviewer_permission": reviewer_permission,
                        "metadata_json": _json(metadata),
                        "updated_by": updated_by,
                    },
                )
            )
            .mappings()
            .one()
        )
    return _row_to_approval_policy(row)


async def create_factor_training_approval_request(
    tenant_id: str,
    user_id: str,
    training_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    notify_created = False
    policy = await get_factor_approval_policy(tenant_id)
    async with get_session() as session:
        row = await _get_factor_training_run_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            training_id=training_id,
        )
        if row is None:
            raise LookupError("factor training run not found")
        item = _row_to_factor_training_run(row)
        if not _factor_training_gate_allows_default_promotion(item):
            raise ValueError(
                "factor training gate does not allow default model promotion"
            )
        model_id = _extract_registered_model_id_from_training_item(item)
        if not model_id:
            raise ValueError("registered model id is missing from the training result")

        existing = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_approval_requests
                        WHERE tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND training_id = :training_id
                          AND status = 'pending'
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "training_id": training_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            request = _row_to_approval_request(existing)
            request["idempotent"] = True
            return request
        request_metadata = (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        )
        request_metadata = {
            **request_metadata,
            "approval_policy": {
                "enabled": policy.get("enabled"),
                "allowDirectApproval": policy.get("allowDirectApproval"),
                "allowSelfApproval": policy.get("allowSelfApproval"),
                "minApprovals": policy.get("minApprovals"),
                "reviewerPermission": policy.get("reviewerPermission"),
            },
        }

        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_approval_requests (
                    id,
                    tenant_id,
                    user_id,
                    training_id,
                    model_id,
                    status,
                    requested_by,
                    request_reason,
                    request_metadata,
                    decision_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    :user_id,
                    :training_id,
                    :model_id,
                    'pending',
                    :requested_by,
                    :request_reason,
                    CAST(:request_metadata AS JSONB),
                    '{}'::jsonb,
                    NOW(),
                    NOW()
                )
                RETURNING *
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "training_id": training_id,
                "model_id": model_id,
                "requested_by": str(payload.get("requested_by") or user_id),
                "request_reason": str(
                    payload.get("reason") or "factor_research_default_model_request"
                ),
                "request_metadata": _json(request_metadata),
            },
        )
        request = _row_to_approval_request(result.mappings().one())
        request["idempotent"] = False
        notify_created = True
    if notify_created:
        notification = await _notify_factor_approval_request_created(
            tenant_id,
            request,
        )
        request["notification"] = notification
    return request


async def list_factor_approval_requests(
    tenant_id: str,
    *,
    user_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    where = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "limit": limit,
        "offset": offset,
    }
    if user_id:
        where.append("user_id = :user_id")
        params["user_id"] = str(user_id)
    if status:
        where.append("status = :status")
        params["status"] = str(status)
    where_sql = " AND ".join(where)

    async with get_session() as session:
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM qm_factor_approval_requests
                        WHERE {where_sql}
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM qm_factor_approval_requests
                        WHERE {where_sql}
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_approval_request(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def review_factor_training_approval_request(
    tenant_id: str,
    request_id: str,
    reviewer_user_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    approve = payload.get("approve") is True or payload.get("decision") == "approve"
    policy = await get_factor_approval_policy(tenant_id)
    min_approvals = max(1, int(policy.get("minApprovals") or 1))
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_approval_requests
                        WHERE tenant_id = :tenant_id
                          AND id = :request_id
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "request_id": request_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise LookupError("factor approval request not found")
        request = _row_to_approval_request(row)
        if request["status"] != "pending":
            raise ValueError("factor approval request is not pending")
        if (
            policy.get("enabled") is True
            and policy.get("allowSelfApproval") is False
            and str(reviewer_user_id) == str(request.get("userId"))
        ):
            raise ValueError("factor approval policy rejects self approval")

    approval_result: dict[str, Any] | None = None
    previous_decision = (
        request.get("decision") if isinstance(request.get("decision"), dict) else {}
    )
    approvals = (
        previous_decision.get("approvals")
        if isinstance(previous_decision.get("approvals"), list)
        else []
    )
    normalized_approvals = [
        item for item in approvals if isinstance(item, dict) and item.get("reviewed_by")
    ]
    already_approved = any(
        str(item.get("reviewed_by")) == str(reviewer_user_id)
        for item in normalized_approvals
    )
    if approve and already_approved:
        raise ValueError("factor approval request already reviewed by this user")
    if approve:
        normalized_approvals = [
            *normalized_approvals,
            {
                "reviewed_by": reviewer_user_id,
                "reviewer_note": payload.get("reviewer_note"),
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    status = "rejected"
    if approve:
        status = "approved" if len(normalized_approvals) >= min_approvals else "pending"

    if status == "approved":
        approval_result = await approve_factor_training_run(
            tenant_id,
            str(request["userId"]),
            str(request["trainingId"]),
            {
                "set_default_model": True,
                "reason": payload.get("reason") or request.get("requestReason"),
                "metadata": {
                    **(
                        request.get("requestMetadata")
                        if isinstance(request.get("requestMetadata"), dict)
                        else {}
                    ),
                    **(
                        payload.get("metadata")
                        if isinstance(payload.get("metadata"), dict)
                        else {}
                    ),
                    "approval_request_id": request_id,
                    "reviewer_user_id": reviewer_user_id,
                },
            },
            approver_user_id=reviewer_user_id,
        )

    decision = {
        "status": status,
        "approve": approve,
        "reviewed_by": reviewer_user_id,
        "reviewer_note": payload.get("reviewer_note"),
        "approvals": normalized_approvals,
        "requiredApprovals": min_approvals,
        "approvalPolicy": {
            "allowDirectApproval": policy.get("allowDirectApproval"),
            "allowSelfApproval": policy.get("allowSelfApproval"),
            "minApprovals": min_approvals,
            "reviewerPermission": policy.get("reviewerPermission"),
        },
        "approval": approval_result.get("approval") if approval_result else None,
        "defaultModel": approval_result.get("defaultModel")
        if approval_result
        else None,
    }
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                UPDATE qm_factor_approval_requests
                SET status = :status,
                    reviewer_user_id = :reviewer_user_id,
                    reviewer_note = :reviewer_note,
                    decision_json = CAST(:decision_json AS JSONB),
                    reviewed_at = NOW(),
                    updated_at = NOW()
                WHERE tenant_id = :tenant_id
                  AND id = :request_id
                RETURNING *
                """
            ),
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "status": status,
                "reviewer_user_id": reviewer_user_id,
                "reviewer_note": payload.get("reviewer_note"),
                "decision_json": _json(decision),
            },
        )
        updated = _row_to_approval_request(result.mappings().one())
    if status != "pending":
        await _notify_factor_approval_request_reviewed(tenant_id, updated)
    return {"request": updated, "approvalResult": approval_result}


async def _get_factor_training_run_row(
    session: Any,
    *,
    tenant_id: str,
    user_id: str,
    training_id: str,
) -> Any | None:
    result = await session.execute(
        text(
            """
            SELECT
                f.*,
                j.status AS training_job_status,
                j.progress AS training_job_progress,
                j.result AS training_job_result,
                j.logs AS training_job_logs,
                j.request_payload AS training_job_request_payload,
                j.updated_at AS training_job_updated_at,
                b.id AS baseline_training_run_id,
                b.status AS baseline_training_job_status,
                b.result AS baseline_training_job_result,
                b.request_payload AS baseline_training_job_request_payload
            FROM qm_factor_training_runs f
            LEFT JOIN admin_training_jobs j
              ON j.id = f.training_run_id
             AND j.tenant_id = f.tenant_id
             AND j.user_id = f.user_id
            LEFT JOIN admin_training_jobs b
              ON b.id = COALESCE(
                    f.request_payload_json->'factor_research'->>'baseline_training_run_id',
                    f.request_payload_json->>'baseline_training_run_id'
                 )
             AND b.tenant_id = f.tenant_id
             AND b.user_id = f.user_id
            WHERE f.tenant_id = :tenant_id
              AND f.user_id = :user_id
              AND f.id = :training_id
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "user_id": user_id, "training_id": training_id},
    )
    return result.mappings().first()


async def approve_factor_training_run(
    tenant_id: str,
    user_id: str,
    training_id: str,
    payload: dict[str, Any] | None = None,
    *,
    approver_user_id: str | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    set_default_model = (
        payload.get("set_default_model") is True
        or payload.get("approve_default_model") is True
    )
    if not set_default_model:
        raise ValueError(
            "set_default_model=true is required to approve a model promotion"
        )
    policy = await get_factor_approval_policy(tenant_id)
    request_metadata = (
        payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    )
    from_approval_request = bool(request_metadata.get("approval_request_id"))
    effective_approver = str(approver_user_id or user_id)
    if policy.get("enabled") is True:
        if policy.get("allowDirectApproval") is False and not from_approval_request:
            raise ValueError("factor approval policy requires approval request review")
        if policy.get("allowSelfApproval") is False and effective_approver == str(
            user_id
        ):
            raise ValueError("factor approval policy rejects self approval")

    async with get_session() as session:
        row = await _get_factor_training_run_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            training_id=training_id,
        )
        if row is None:
            raise LookupError("factor training run not found")
        item = _row_to_factor_training_run(row)

    if not _factor_training_gate_allows_default_promotion(item):
        raise ValueError("factor training gate does not allow default model promotion")

    model_id = _extract_registered_model_id_from_training_item(item)
    if not model_id:
        raise ValueError("registered model id is missing from the training result")

    existing_approval = _factor_training_existing_default_approval(item, model_id)
    if existing_approval:
        current_default_model = await model_registry_service.get_default_model(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if (
            isinstance(current_default_model, dict)
            and str(current_default_model.get("model_id") or "").strip() == model_id
        ):
            async with get_session() as session:
                await _record_factor_training_approval_audit(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    training_id=training_id,
                    item=item,
                    model_id=model_id,
                    approval=existing_approval,
                    default_model=current_default_model,
                    request_payload=payload,
                    idempotent=True,
                )
            return {
                "training": item,
                "approval": existing_approval,
                "defaultModel": current_default_model,
                "idempotent": True,
            }

    default_model = await model_registry_service.set_default_model(
        tenant_id=tenant_id,
        user_id=user_id,
        model_id=model_id,
    )
    approval = {
        "status": "approved",
        "set_default_model": True,
        "model_id": model_id,
        "default_model_set": True,
        "approved_by": effective_approver,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "reason": str(payload.get("reason") or "factor_research_gate_approved"),
        "gate": item.get("trainingGate") or {},
        "training_run_id": item.get("trainingRunId"),
        "request_metadata": (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        ),
    }
    metadata = {
        **(item.get("metadata") if isinstance(item.get("metadata"), dict) else {}),
        "approval": approval,
    }
    response = {
        **_factor_training_response_for_storage(item),
        "approval": approval,
    }

    async with get_session() as session:
        await session.execute(
            text(
                """
                UPDATE qm_factor_training_runs
                SET metadata_json = CAST(:metadata_json AS JSONB),
                    response_json = CAST(:response_json AS JSONB),
                    updated_at = NOW()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                  AND user_id = :user_id
                """
            ),
            {
                "id": training_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "metadata_json": _json(metadata),
                "response_json": _json(response),
            },
        )
        await _record_factor_training_approval_audit(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            training_id=training_id,
            item=item,
            model_id=model_id,
            approval=approval,
            default_model=default_model,
            request_payload=payload,
            idempotent=False,
        )
        row = await _get_factor_training_run_row(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            training_id=training_id,
        )

    training = _row_to_factor_training_run(row) if row is not None else item
    training["metadata"] = metadata
    training["response"] = response
    return {"training": training, "approval": approval, "defaultModel": default_model}


async def publish_factor_shadow_signal(
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    async with get_session() as session:
        candidate_row = await _get_candidate_and_run_for_promotion(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            candidate_id=candidate_id,
            run_id=payload.get("run_id"),
        )
        if not candidate_row:
            raise LookupError("factor candidate or completed run not found")
        if str(candidate_row["run_status"]) != "completed":
            raise ValueError(
                "only completed factor evaluation runs can publish shadow signals"
            )

        requested_date = _date_or_none(payload.get("trade_date"))
        if requested_date is None:
            requested_date = (
                await session.execute(
                    text(
                        """
                        SELECT MAX(trade_date)
                        FROM qm_factor_values
                        WHERE run_id = :run_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        """
                    ),
                    {
                        "run_id": candidate_row["run_id"],
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            ).scalar_one()
        if requested_date is None:
            raise ValueError(
                "factor values are required before shadow signal publishing"
            )

        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT trade_date, symbol, factor_value
                    FROM qm_factor_values
                    WHERE run_id = :run_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND trade_date = :trade_date
                    ORDER BY factor_value DESC NULLS LAST, symbol ASC
                    """
                    ),
                    {
                        "run_id": candidate_row["run_id"],
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "trade_date": requested_date,
                    },
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            raise ValueError("no factor values found for requested trade date")

        signal_run_id = str(uuid.uuid4())
        top_n = max(1, min(int(payload.get("top_n") or 20), 200))
        bottom_n = max(0, min(int(payload.get("bottom_n") or 0), 200))
        long_short = bool(payload.get("long_short", False))
        publish_stream = _resolve_shadow_stream_publish(payload)
        allow_shadow_stream = bool(payload.get("allow_shadow_stream", False))
        quantity = max(1, int(payload.get("quantity") or 100))
        factor_rows = [
            FactorValueRow(
                trade_date=row["trade_date"],
                symbol=str(row["symbol"]),
                factor_value=float(row["factor_value"]),
            )
            for row in rows
        ]
        signals = build_factor_signal_events(
            factor_rows,
            FactorSignalConfig(
                tenant_id=tenant_id,
                user_id=user_id,
                run_id=signal_run_id,
                top_n=top_n,
                bottom_n=bottom_n,
                long_short=long_short,
                quantity=quantity,
                signal_source="factor_shadow",
            ),
            trade_date=requested_date,
        )
        if not signals:
            raise ValueError("no shadow signals generated")

        metadata = {
            "source": "factor_research",
            "signal_source": "factor_shadow",
            "candidate_id": candidate_id,
            "factor_run_id": str(candidate_row["run_id"]),
            "candidate_name": str(candidate_row["name"] or ""),
            "expression": str(candidate_row["expression"] or ""),
            "trade_date": requested_date.isoformat(),
            "publish_stream": publish_stream,
            "allow_shadow_stream": allow_shadow_stream,
        }
        await _upsert_factor_shadow_signal_scores(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            signal_run_id=signal_run_id,
            factor_run_id=str(candidate_row["run_id"]),
            trade_date=requested_date,
            candidate_id=candidate_id,
            signals=signals,
            metadata=metadata,
        )
        stream_published = _publish_factor_shadow_signal_stream(
            tenant_id=tenant_id,
            user_id=user_id,
            signal_run_id=signal_run_id,
            signals=signals,
            enabled=publish_stream,
        )
        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_signal_runs (
                    id, candidate_id, factor_run_id, tenant_id, user_id, trade_date,
                    status, top_n, bottom_n, long_short, publish_stream,
                    signal_count, stream_published_count, metadata_json, created_at, updated_at
                )
                VALUES (
                    :id, :candidate_id, :factor_run_id, :tenant_id, :user_id, :trade_date,
                    'published', :top_n, :bottom_n, :long_short, :publish_stream,
                    :signal_count, :stream_published_count, CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                RETURNING *
                """
            ),
            {
                "id": signal_run_id,
                "candidate_id": candidate_id,
                "factor_run_id": str(candidate_row["run_id"]),
                "tenant_id": tenant_id,
                "user_id": user_id,
                "trade_date": requested_date,
                "top_n": top_n,
                "bottom_n": bottom_n,
                "long_short": long_short,
                "publish_stream": publish_stream,
                "signal_count": len(signals),
                "stream_published_count": stream_published,
                "metadata_json": _json({**metadata, "signals_preview": signals[:5]}),
            },
        )
        row = result.mappings().one()
    return _row_to_signal_run(row)


async def list_factor_signal_runs(
    tenant_id: str,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    async with get_session(read_only=True) as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_signal_runs
                    WHERE tenant_id = :tenant_id AND user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM qm_factor_signal_runs
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_signal_run(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def create_factor_campaign(
    tenant_id: str,
    user_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    campaign_id = str(uuid.uuid4())
    seed_expression = normalize_factor_expression(
        str(payload.get("seed_expression") or "")
    )
    quota_policy = _campaign_quota_policy()
    requested_total = _validate_campaign_requested_candidates(payload, quota_policy)
    candidates_per_generation = _campaign_requested_candidate_count(payload)
    max_generations = _campaign_generation_count(payload)
    initial_specs = _generate_campaign_expression_specs(
        payload,
        max_candidates=candidates_per_generation,
    )
    expressions = [str(spec.get("expression") or "") for spec in initial_specs]
    if not expressions:
        raise ValueError("campaign requires at least one supported seed expression")

    params = _campaign_evaluation_params(payload)
    if (
        _date_or_none(params.get("start_date")) is None
        or _date_or_none(params.get("end_date")) is None
    ):
        raise ValueError("campaign requires valid start_date and end_date")
    name = (
        str(payload.get("name") or "").strip()
        or f"因子挖掘 {datetime.now(timezone.utc).strftime('%m%d%H%M')}"
    )
    strategy = _campaign_strategy(payload)
    generator_name = (
        "quantmind_mutation_crossover"
        if strategy == "mutation_crossover"
        else "quantmind_template_mutation"
    )
    generation_strategy = (
        "local_iterative_mutation_crossover"
        if strategy == "mutation_crossover"
        else "local_iterative_template_mutation"
    )
    worker_policy = _campaign_worker_policy(payload)
    retry_policy = _campaign_retry_policy(payload)
    execution_lease = _campaign_execution_lease(payload)
    metadata = {
        "source": "factor_research",
        "pipeline_stage": "factor_campaign",
        "generator": generator_name,
        "generationStrategy": generation_strategy,
        **(
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        ),
        "workerPolicy": worker_policy,
        "retryPolicy": retry_policy,
        "executionLease": execution_lease,
    }
    run_async = _campaign_run_async_requested(payload)
    if run_async:
        metadata["executionMode"] = "async"
        metadata["worker"] = (
            "external_factor_campaign_worker"
            if worker_policy.get("externalWorkerRequired")
            else "factor_campaign_executor"
        )
    created_at = datetime.now(timezone.utc)
    campaign_params = {
        **params,
        "n_candidates": requested_total,
        "candidates_per_generation": candidates_per_generation,
        "max_generations": max_generations,
        "worker_policy": worker_policy,
        "retry_policy": retry_policy,
        "execution_lease": execution_lease,
    }
    initial_status = "pending" if run_async else "running"
    started_at = None if run_async else created_at
    async with get_session() as session:
        quota_usage = await _enforce_factor_campaign_quota(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            requested_candidates=requested_total,
            policy=quota_policy,
        )
        metadata["quota"] = quota_usage
        await session.execute(
            text(
                """
                INSERT INTO qm_factor_campaigns (
                    id, tenant_id, user_id, name, strategy, status, seed_expression,
                    params_json, summary_json, metadata_json, started_at, created_at, updated_at
                )
                VALUES (
                    :id, :tenant_id, :user_id, :name, :strategy, :status, :seed_expression,
                    CAST(:params_json AS JSONB), '{}'::jsonb, CAST(:metadata_json AS JSONB),
                    :started_at, :created_at, :updated_at
                )
                """
            ),
            {
                "id": campaign_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "name": name,
                "strategy": strategy,
                "status": initial_status,
                "seed_expression": seed_expression or expressions[0],
                "params_json": _json(campaign_params),
                "metadata_json": _json(metadata),
                "started_at": started_at,
                "created_at": created_at,
                "updated_at": created_at,
            },
        )

    created_campaign = {
        "id": campaign_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "name": name,
        "strategy": strategy,
        "status": initial_status,
        "seed_expression": seed_expression or expressions[0],
        "params_json": campaign_params,
        "summary_json": {},
        "metadata_json": metadata,
        "started_at": started_at,
        "completed_at": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    if run_async:
        if not worker_policy.get("externalWorkerRequired"):
            _schedule_factor_campaign_execution(
                tenant_id=tenant_id,
                user_id=user_id,
                campaign_id=campaign_id,
            )
        return _row_to_campaign(created_campaign, items=[])

    return await _execute_factor_campaign_from_payload(
        tenant_id=tenant_id,
        user_id=user_id,
        campaign_id=campaign_id,
        payload=payload,
        params=params,
        candidates_per_generation=candidates_per_generation,
        max_generations=max_generations,
        initial_expressions=expressions,
        initial_expression_specs=initial_specs,
    )


def _campaign_run_async_requested(payload: dict[str, Any]) -> bool:
    raw = payload.get("run_async", payload.get("async_execution", False))
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(raw)


def _schedule_factor_campaign_execution(
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
) -> None:
    async def _runner() -> None:
        try:
            await execute_factor_campaign(
                tenant_id=tenant_id,
                user_id=user_id,
                campaign_id=campaign_id,
            )
        except Exception:
            logger.exception("factor campaign async execution failed: %s", campaign_id)

    try:
        asyncio.get_running_loop().create_task(
            _runner(),
            name=f"factor-campaign-{campaign_id}",
        )
    except RuntimeError:
        logger.warning(
            "no running event loop; factor campaign %s left pending", campaign_id
        )


def _campaign_payload_from_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    params = data.get("params_json") or {}
    metadata = (
        params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
    )
    return {
        **params,
        "strategy": data.get("strategy") or "template_mutation",
        "seed_expression": data.get("seed_expression"),
        "seed_expressions": [],
        "n_candidates": int(
            params.get("candidates_per_generation") or params.get("n_candidates") or 1
        ),
        "max_generations": int(params.get("max_generations") or 1),
        "metadata": metadata,
    }


async def execute_factor_campaign(
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    """Compatibility wrapper for engine-side campaign execution."""
    from backend.services.engine.research.factor_campaign_service import (
        execute_factor_campaign as _engine_execute_campaign,
    )

    return await _engine_execute_campaign(
        tenant_id=tenant_id,
        user_id=user_id,
        campaign_id=campaign_id,
    )


async def _execute_claimed_factor_campaign(
    campaign: Any,
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    """Compatibility wrapper for engine-side campaign execution."""
    from backend.services.engine.research.factor_campaign_service import (
        execute_claimed_factor_campaign as _engine_execute_claimed_campaign,
    )

    return await _engine_execute_claimed_campaign(
        campaign,
        tenant_id=tenant_id,
        user_id=user_id,
        campaign_id=campaign_id,
    )


async def claim_next_pending_factor_campaign(
    *,
    worker_id: str | None = None,
    lease_seconds: int | None = None,
) -> dict[str, Any] | None:
    """Compatibility wrapper for engine-side campaign workers."""
    from backend.services.engine.research.factor_campaign_service import (
        claim_next_pending_factor_campaign as _engine_claim_next_pending,
    )

    return await _engine_claim_next_pending(
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )


async def recover_stale_running_factor_campaigns(
    *,
    stale_after_minutes: int | None = None,
    worker_id: str | None = None,
) -> int:
    """Compatibility wrapper for engine-side campaign workers."""
    from backend.services.engine.research.factor_campaign_service import (
        recover_stale_running_factor_campaigns as _engine_recover_stale,
    )

    return await _engine_recover_stale(
        stale_after_minutes=stale_after_minutes,
        worker_id=worker_id,
    )


async def record_factor_campaign_worker_event(
    *,
    event_type: str,
    campaign_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    worker_id: str | None = None,
    attempt_no: int | None = None,
    duration_ms: int | None = None,
    heartbeat_at: datetime | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> str:
    """Compatibility wrapper for engine-side campaign workers."""
    from backend.services.engine.research.factor_campaign_service import (
        record_factor_campaign_worker_event as _engine_record_event,
    )

    return await _engine_record_event(
        event_type=event_type,
        campaign_id=campaign_id,
        tenant_id=tenant_id,
        user_id=user_id,
        worker_id=worker_id,
        attempt_no=attempt_no,
        duration_ms=duration_ms,
        heartbeat_at=heartbeat_at,
        status=status,
        details=details,
    )


async def list_factor_campaign_worker_events(
    tenant_id: str,
    user_id: str,
    *,
    campaign_id: str | None = None,
    worker_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Compatibility wrapper for engine-side campaign workers."""
    from backend.services.engine.research.factor_campaign_service import (
        list_factor_campaign_worker_events as _engine_list_events,
    )

    return await _engine_list_events(
        tenant_id,
        user_id,
        campaign_id=campaign_id,
        worker_id=worker_id,
        event_type=event_type,
        status=status,
        limit=limit,
        offset=offset,
    )


async def _execute_factor_campaign_from_payload(
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
    payload: dict[str, Any],
    params: dict[str, Any],
    candidates_per_generation: int,
    max_generations: int,
    initial_expressions: list[str],
    initial_expression_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for engine-side campaign execution."""
    from backend.services.engine.research.factor_campaign_service import (
        execute_factor_campaign_from_payload as _engine_execute_from_payload,
    )

    return await _engine_execute_from_payload(
        tenant_id=tenant_id,
        user_id=user_id,
        campaign_id=campaign_id,
        payload=payload,
        params=params,
        candidates_per_generation=candidates_per_generation,
        max_generations=max_generations,
        initial_expressions=initial_expressions,
        initial_expression_specs=initial_expression_specs,
    )


async def list_factor_campaigns(
    tenant_id: str,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    async with get_session(read_only=True) as session:
        rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_campaigns
                    WHERE tenant_id = :tenant_id AND user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        total = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM qm_factor_campaigns
                        WHERE tenant_id = :tenant_id AND user_id = :user_id
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_campaign(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def get_factor_campaign(
    tenant_id: str, user_id: str, campaign_id: str
) -> dict[str, Any]:
    async with get_session(read_only=True) as session:
        campaign = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_campaigns
                    WHERE id = :campaign_id AND tenant_id = :tenant_id AND user_id = :user_id
                    """
                    ),
                    {
                        "campaign_id": campaign_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not campaign:
            raise LookupError("factor campaign not found")
        item_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT *
                    FROM qm_factor_campaign_items
                    WHERE campaign_id = :campaign_id AND tenant_id = :tenant_id AND user_id = :user_id
                    ORDER BY rank_no ASC
                    """
                    ),
                    {
                        "campaign_id": campaign_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .all()
        )
    return _row_to_campaign(
        campaign, items=[_row_to_campaign_item(row) for row in item_rows]
    )


async def cancel_factor_campaign(
    tenant_id: str,
    user_id: str,
    campaign_id: str,
    *,
    reason: str = "manual_cancel",
) -> dict[str, Any]:
    reason = str(reason or "manual_cancel").strip()[:240] or "manual_cancel"
    cancelled_at = datetime.now(timezone.utc).isoformat()
    cancellation = {
        "cancelled": True,
        "cancelReason": reason,
        "cancelledAt": cancelled_at,
        "cancelledBy": user_id,
    }
    async with get_session() as session:
        current = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_campaigns
                        WHERE id = :campaign_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        FOR UPDATE
                        """
                    ),
                    {
                        "campaign_id": campaign_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not current:
            raise LookupError("factor campaign not found")
        status = str(current.get("status") or "")
        if status == "cancelled":
            campaign = current
        elif status not in {"pending", "running", "evaluating"}:
            raise ValueError("factor campaign is not active")
        else:
            result = await session.execute(
                text(
                    """
                    UPDATE qm_factor_campaigns
                    SET status = 'cancelled',
                        summary_json = COALESCE(summary_json, '{}'::jsonb)
                            || CAST(:summary_json AS JSONB),
                        metadata_json = COALESCE(metadata_json, '{}'::jsonb)
                            || CAST(:metadata_json AS JSONB),
                        completed_at = COALESCE(completed_at, NOW()),
                        updated_at = NOW()
                    WHERE id = :campaign_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    RETURNING *
                    """
                ),
                {
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "summary_json": _json(cancellation),
                    "metadata_json": _json({"cancellation": cancellation}),
                },
            )
            campaign = result.mappings().one()
            await session.execute(
                text(
                    """
                    UPDATE qm_factor_campaign_items
                    SET status = 'cancelled',
                        reason = COALESCE(reason, :reason),
                        updated_at = NOW()
                    WHERE campaign_id = :campaign_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND status IN ('pending', 'running', 'evaluating')
                    """
                ),
                {
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "reason": reason,
                },
            )
        item_rows = (
            (
                await session.execute(
                    text(
                        """
                        SELECT *
                        FROM qm_factor_campaign_items
                        WHERE campaign_id = :campaign_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        ORDER BY rank_no ASC
                        """
                    ),
                    {
                        "campaign_id": campaign_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .all()
        )
    return _row_to_campaign(
        campaign, items=[_row_to_campaign_item(row) for row in item_rows]
    )


async def _run_campaign_expression(
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
    generation: int,
    rank_no: int,
    expression: str,
    params: dict[str, Any],
    item_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_id: str | None = None
    run_id: str | None = None
    status = "failed"
    reason: str | None = None
    metrics: dict[str, Any] | None = None
    score: float | None = None
    metadata = {
        "campaign_id": campaign_id,
        "generation": generation,
        "rank_no": rank_no,
        **(item_metadata if isinstance(item_metadata, dict) else {}),
    }
    try:
        candidate = await create_factor_candidate(
            tenant_id,
            user_id,
            {
                "name": f"Campaign G{generation}.{rank_no}: {expression[:40]}",
                "expression": expression,
                "source": "campaign",
                "family": "campaign",
                "tags": ["campaign"],
                "metadata": metadata,
            },
        )
        candidate_id = candidate["id"]
        run = await create_factor_evaluation_run(
            tenant_id, user_id, candidate_id, params
        )
        run_id = run["id"]
        status = str(run.get("status") or "failed")
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else None
        reason = run.get("errorMessage") or " / ".join(
            run.get("gateDecision", {}).get("reasons") or []
        )
        score = _score_campaign_run(metrics, run.get("gateDecision") or {})
        metadata["evaluation"] = {
            "status": status,
            "score": score,
            "reason": reason,
        }
    except Exception as exc:
        reason = str(exc)
        metadata["evaluation"] = {
            "status": status,
            "score": score,
            "reason": reason,
        }

    async with get_session() as session:
        result = await session.execute(
            text(
                """
                INSERT INTO qm_factor_campaign_items (
                    campaign_id, candidate_id, run_id, tenant_id, user_id,
                    generation, rank_no, expression, status, score, reason,
                    metrics_json, metadata_json, created_at, updated_at
                )
                VALUES (
                    :campaign_id, :candidate_id, :run_id, :tenant_id, :user_id,
                    :generation, :rank_no, :expression, :status, :score, :reason,
                    CAST(:metrics_json AS JSONB), CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                ON CONFLICT (campaign_id, rank_no)
                DO UPDATE SET
                    candidate_id = EXCLUDED.candidate_id,
                    run_id = EXCLUDED.run_id,
                    expression = EXCLUDED.expression,
                    status = EXCLUDED.status,
                    score = EXCLUDED.score,
                    reason = EXCLUDED.reason,
                    metrics_json = EXCLUDED.metrics_json,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = NOW()
                RETURNING *
                """
            ),
            {
                "campaign_id": campaign_id,
                "candidate_id": candidate_id,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "generation": generation,
                "rank_no": rank_no,
                "expression": expression,
                "status": status,
                "score": score,
                "reason": reason,
                "metrics_json": _json(metrics),
                "metadata_json": _json(metadata),
            },
        )
        row = result.mappings().one()
    return _row_to_campaign_item(row)


def _campaign_evaluation_params(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "universe": payload.get("universe") or "hs300",
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "n_groups": int(payload.get("n_groups") or 5),
        "holding_period": int(payload.get("holding_period") or 5),
        "neutralize_industry": bool(payload.get("neutralize_industry", True)),
        "neutralize_cap": bool(payload.get("neutralize_cap", True)),
        "validation_profile": payload.get("validation_profile") or "campaign",
        "metadata": {
            "pipeline_stage": "factor_campaign",
            **(
                payload.get("metadata")
                if isinstance(payload.get("metadata"), dict)
                else {}
            ),
        },
    }


def _campaign_policy_dict(payload: dict[str, Any], snake_key: str, camel_key: str) -> dict:
    raw = payload.get(snake_key)
    if not isinstance(raw, dict):
        raw = payload.get(camel_key)
    return raw if isinstance(raw, dict) else {}


def _bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(minimum, parsed), max(minimum, maximum))


def _campaign_worker_policy(payload: dict[str, Any]) -> dict[str, Any]:
    policy = _campaign_policy_dict(payload, "worker_policy", "workerPolicy")
    max_concurrency = _positive_int_env(
        _FACTOR_CAMPAIGN_MAX_WORKER_CONCURRENCY_ENV,
        4,
    )
    max_claims = _positive_int_env(_FACTOR_CAMPAIGN_MAX_WORKER_CLAIMS_ENV, 20)
    return {
        "workerId": str(policy.get("worker_id") or policy.get("workerId") or "").strip()
        or None,
        "externalWorkerRequired": bool(
            policy.get("external_worker") or policy.get("externalWorkerRequired")
        ),
        "concurrency": _bounded_int(
            policy.get("concurrency"),
            default=1,
            minimum=1,
            maximum=max_concurrency,
        ),
        "maxClaims": _bounded_int(
            policy.get("max_claims") or policy.get("maxClaims"),
            default=1,
            minimum=1,
            maximum=max_claims,
        ),
        "heartbeatIntervalSeconds": _bounded_int(
            policy.get("heartbeat_interval_seconds")
            or policy.get("heartbeatIntervalSeconds"),
            default=30,
            minimum=5,
            maximum=300,
        ),
    }


def _campaign_retry_policy(payload: dict[str, Any]) -> dict[str, Any]:
    policy = _campaign_policy_dict(payload, "retry_policy", "retryPolicy")
    max_attempts = _positive_int_env(_FACTOR_CAMPAIGN_MAX_RETRY_ATTEMPTS_ENV, 3)
    return {
        "maxAttempts": _bounded_int(
            policy.get("max_attempts") or policy.get("maxAttempts"),
            default=1,
            minimum=1,
            maximum=max_attempts,
        ),
        "retryFailedAfterMinutes": _bounded_int(
            policy.get("retry_failed_after_minutes")
            or policy.get("retryFailedAfterMinutes"),
            default=_campaign_stale_running_minutes(),
            minimum=1,
            maximum=24 * 60,
        ),
    }


def _campaign_execution_lease(payload: dict[str, Any]) -> dict[str, Any]:
    policy = _campaign_policy_dict(payload, "execution_lease", "executionLease")
    max_lease_seconds = _positive_int_env(_FACTOR_CAMPAIGN_MAX_LEASE_SECONDS_ENV, 7200)
    return {
        "leaseSeconds": _bounded_int(
            policy.get("lease_seconds") or policy.get("leaseSeconds"),
            default=min(1800, max_lease_seconds),
            minimum=60,
            maximum=max_lease_seconds,
        ),
    }


def _positive_int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _campaign_quota_policy() -> FactorCampaignQuotaPolicy:
    max_candidates = _positive_int_env(
        _FACTOR_CAMPAIGN_MAX_CANDIDATES_ENV,
        20,
    )
    daily_budget = _positive_int_env(
        _FACTOR_CAMPAIGN_DAILY_CANDIDATES_ENV,
        max(100, max_candidates),
    )
    return FactorCampaignQuotaPolicy(
        max_candidates_per_campaign=max_candidates,
        max_active_campaigns_per_user=_positive_int_env(
            _FACTOR_CAMPAIGN_MAX_ACTIVE_ENV,
            1,
        ),
        daily_candidate_budget_per_user=max(daily_budget, max_candidates),
    )


def _campaign_stale_running_minutes() -> int:
    return _positive_int_env(_FACTOR_CAMPAIGN_STALE_RUNNING_MINUTES_ENV, 30)


def _campaign_requested_candidate_count(payload: dict[str, Any]) -> int:
    try:
        requested = int(payload.get("n_candidates") or 5)
    except (TypeError, ValueError) as exc:
        raise ValueError("campaign n_candidates must be a positive integer") from exc
    if requested < 1:
        raise ValueError("campaign n_candidates must be a positive integer")
    return requested


def _campaign_generation_count(payload: dict[str, Any]) -> int:
    try:
        requested = int(payload.get("max_generations") or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("campaign max_generations must be a positive integer") from exc
    if requested < 1:
        raise ValueError("campaign max_generations must be a positive integer")
    return min(requested, 5)


def _validate_campaign_requested_candidates(
    payload: dict[str, Any],
    policy: FactorCampaignQuotaPolicy,
) -> int:
    requested_per_generation = _campaign_requested_candidate_count(payload)
    generation_count = _campaign_generation_count(payload)
    requested_total = requested_per_generation * generation_count
    if requested_total > policy.max_candidates_per_campaign:
        raise ValueError(
            "campaign candidate quota exceeded: "
            f"requested={requested_total}, "
            f"max_per_campaign={policy.max_candidates_per_campaign}"
        )
    return requested_total


async def _enforce_factor_campaign_quota(
    session: Any,
    *,
    tenant_id: str,
    user_id: str,
    requested_candidates: int,
    policy: FactorCampaignQuotaPolicy,
) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE status IN ('pending', 'running')
                        ) AS active_campaigns,
                        COALESCE(
                            SUM(
                                COALESCE((params_json->>'n_candidates')::int, 0)
                                * GREATEST(
                                    COALESCE((params_json->>'max_generations')::int, 1),
                                    1
                                )
                            ) FILTER (
                                WHERE created_at >= date_trunc('day', NOW())
                            ),
                            0
                        ) AS today_candidates
                    FROM qm_factor_campaigns
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id},
            )
        )
        .mappings()
        .first()
    )
    active_campaigns = int((row or {}).get("active_campaigns") or 0)
    today_candidates = int((row or {}).get("today_candidates") or 0)
    if active_campaigns >= policy.max_active_campaigns_per_user:
        raise ValueError(
            "campaign active quota exceeded: "
            f"active={active_campaigns}, "
            f"max_active_per_user={policy.max_active_campaigns_per_user}"
        )

    projected_daily_candidates = today_candidates + requested_candidates
    if projected_daily_candidates > policy.daily_candidate_budget_per_user:
        raise ValueError(
            "campaign daily candidate quota exceeded: "
            f"today={today_candidates}, requested={requested_candidates}, "
            f"daily_budget={policy.daily_candidate_budget_per_user}"
        )

    return {
        "activeCampaigns": active_campaigns,
        "todayCandidates": today_candidates,
        "requestedCandidates": requested_candidates,
        "projectedDailyCandidates": projected_daily_candidates,
        "policy": {
            "maxCandidatesPerCampaign": policy.max_candidates_per_campaign,
            "maxActiveCampaignsPerUser": policy.max_active_campaigns_per_user,
            "dailyCandidateBudgetPerUser": policy.daily_candidate_budget_per_user,
        },
    }


def _campaign_item_spec(
    expression: str,
    *,
    strategy: str,
    operator: str,
    parent_expressions: list[str] | None = None,
    reason: str | None = None,
    quantgpt_strategy: str | None = None,
    evolution_score: float | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "strategy": strategy,
        "operator": operator,
        "parentExpressions": parent_expressions or [],
    }
    if reason:
        metadata["evolutionReason"] = reason
    if quantgpt_strategy:
        metadata["quantgptStrategy"] = quantgpt_strategy
    if evolution_score is not None:
        metadata["evolutionScore"] = evolution_score
    return {
        "expression": normalize_factor_expression(expression),
        "metadata": metadata,
    }


def _best_iteration_score(items: list[dict[str, Any]]) -> float | None:
    scores: list[float] = []
    for item in items:
        try:
            scores.append(float(item.get("score") or 0.0))
        except (TypeError, ValueError):
            continue
    return max(scores) if scores else None


def _generate_campaign_expression_specs(
    payload: dict[str, Any],
    *,
    max_candidates: int = 20,
    exclude_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    requested = min(
        _campaign_requested_candidate_count(payload), max(1, max_candidates)
    )
    exclude_keys = exclude_keys or set()
    strategy = _campaign_strategy(payload)
    seeds = [
        normalize_factor_expression(expr)
        for expr in (payload.get("seed_expressions") or [])
        if normalize_factor_expression(expr)
    ]
    seed_expression = normalize_factor_expression(
        str(payload.get("seed_expression") or "")
    )
    if seed_expression:
        seeds.insert(0, seed_expression)
    if not seeds:
        seeds = [
            "rank(close / ts_mean(close, 20))",
            "rank(ts_delta(close, 5) / ts_shift(close, 5))",
        ]

    if strategy in {"quantgpt_meta_evolution", "quantgpt_crossover_only"}:
        iteration_history = payload.get("iteration_history") or []
        result = generate_quantgpt_evolution_candidates(
            seed_expressions=seeds,
            max_candidates=requested,
            strategy=strategy,
            exclude_keys=exclude_keys,
            iteration_history=iteration_history,
        )
        evolution_score = _best_iteration_score(
            iteration_history if isinstance(iteration_history, list) else []
        )
        return [
            _campaign_item_spec(
                candidate.expression,
                strategy=strategy,
                operator=candidate.source_strategy,
                parent_expressions=seeds[:5],
                reason=candidate.reason,
                quantgpt_strategy=result.quantgpt_strategy,
                evolution_score=evolution_score,
            )
            for candidate in result.candidates
        ]

    candidates: list[dict[str, Any]] = []
    for seed in seeds:
        candidates.append(
            _campaign_item_spec(
                seed,
                strategy=strategy,
                operator="seed",
                parent_expressions=[],
                reason="seed expression",
            )
        )
    if strategy == "mutation_crossover":
        candidates.extend(
            _campaign_item_spec(
                expression,
                strategy=strategy,
                operator="crossover",
                parent_expressions=seeds[:5],
                reason="local crossover from supported seed expressions",
            )
            for expression in _crossover_supported_expressions(seeds)
        )
    for seed in seeds:
        candidates.extend(
            _campaign_item_spec(
                expression,
                strategy=strategy,
                operator="mutation",
                parent_expressions=[seed],
                reason="local window/operator mutation",
            )
            for expression in _mutate_supported_expression(seed)
        )
    fallback_candidates = [
        "rank(close / ts_mean(close, 20))",
        "rank(close / ts_mean(close, 40))",
        "rank(ts_delta(close, 5) / ts_shift(close, 5))",
        "rank(ts_delta(close, 10) / ts_shift(close, 10))",
    ]
    if strategy == "mutation_crossover":
        fallback_candidates.append(
            "rank((close / ts_mean(close, 20)) * (ts_delta(close, 5) / ts_shift(close, 5)))"
        )
    candidates.extend(
        _campaign_item_spec(
            expression,
            strategy=strategy,
            operator="fallback",
            parent_expressions=[],
            reason="default supported fallback expression",
        )
        for expression in fallback_candidates
    )

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for spec in candidates:
        expression = str(spec.get("expression") or "")
        key = factor_expression_key(expression)
        if (
            key in seen
            or key in exclude_keys
            or _factor_raw_value_sql(expression) is None
        ):
            continue
        seen.add(key)
        unique.append(spec)
        if len(unique) >= requested:
            break
    return unique


def _generate_campaign_expressions(
    payload: dict[str, Any],
    *,
    max_candidates: int = 20,
    exclude_keys: set[str] | None = None,
) -> list[str]:
    return [
        str(spec.get("expression") or "")
        for spec in _generate_campaign_expression_specs(
            payload,
            max_candidates=max_candidates,
            exclude_keys=exclude_keys,
        )
    ]


def _campaign_strategy(payload: dict[str, Any]) -> str:
    strategy = str(payload.get("strategy") or "mutation_crossover").strip()
    if strategy in {
        "template_mutation",
        "mutation_crossover",
        "quantgpt_meta_evolution",
        "quantgpt_crossover_only",
    }:
        return strategy
    raise ValueError("unsupported campaign strategy")


def _supported_expression_windows(
    expression: str,
) -> tuple[str, int, int | None] | None:
    parsed = parse_supported_factor_expression(expression)
    if parsed is None:
        return None
    if parsed.kind == "mean" and parsed.mean_window is not None:
        return ("mean", parsed.mean_window, None)
    if parsed.kind in {"momentum", "tanh_momentum"} and parsed.momentum_window is not None:
        return ("momentum", parsed.momentum_window, None)
    if parsed.kind == "hybrid" and parsed.mean_window is not None:
        return ("hybrid", parsed.mean_window, parsed.momentum_window)
    if parsed.kind == "volatility" and parsed.volatility_window is not None:
        return ("volatility", parsed.volatility_window, None)
    if parsed.kind == "correlation" and parsed.correlation_window is not None:
        return ("correlation", parsed.correlation_window, None)
    return None


def _crossover_supported_expressions(seeds: list[str]) -> list[str]:
    parsed = [
        windows
        for windows in (_supported_expression_windows(seed) for seed in seeds)
        if windows is not None
    ]
    mean_windows = [first for kind, first, _ in parsed if kind in {"mean", "hybrid"}]
    momentum_windows = [
        (second if second is not None else first)
        for kind, first, second in parsed
        if kind in {"momentum", "hybrid"}
    ]
    if not mean_windows:
        mean_windows = [20]
    if not momentum_windows:
        momentum_windows = [5]

    expressions: list[str] = []
    for mean_window in mean_windows[:3]:
        for momentum_window in momentum_windows[:3]:
            if 2 <= mean_window <= 252 and 1 <= momentum_window <= 120:
                expressions.append(
                    "rank((close / ts_mean(close, "
                    f"{mean_window})) * (ts_delta(close, {momentum_window}) / "
                    f"ts_shift(close, {momentum_window})))"
                )
    return expressions


def _mutate_supported_expression(expression: str) -> list[str]:
    parsed = parse_supported_factor_expression(expression)
    if parsed is None:
        return [
            "rank(close / ts_mean(close, 20))",
            "rank(ts_delta(close, 5) / ts_shift(close, 5))",
        ]

    if parsed.kind == "mean" and parsed.mean_window is not None:
        field = parsed.field or "close"
        base_window = parsed.mean_window
        windows = [base_window, 5, 10, 20, 40, 60, 120]
        return [
            f"rank({field} / ts_mean({field}, {window}))"
            for window in windows
            if 2 <= window <= 252
        ]

    if parsed.kind in {"momentum", "tanh_momentum"} and parsed.momentum_window is not None:
        base_window = parsed.momentum_window
        windows = [base_window, 2, 3, 5, 10, 20, 40]
        expressions = [
            f"rank(ts_delta(close, {window}) / ts_shift(close, {window}))"
            for window in windows
            if 1 <= window <= 120
        ]
        expressions.extend(
            f"rank(tanh(ts_delta(close, {window}) / ts_shift(close, {window})))"
            for window in windows[:4]
            if 1 <= window <= 120
        )
        return expressions

    if parsed.kind == "hybrid" and parsed.mean_window and parsed.momentum_window:
        mean_windows = [parsed.mean_window, 10, 20, 40, 60]
        momentum_windows = [parsed.momentum_window, 3, 5, 10, 20]
        return [
            "rank((close / ts_mean(close, "
            f"{mean_candidate})) * (ts_delta(close, {momentum_candidate}) / "
            f"ts_shift(close, {momentum_candidate})))"
            for mean_candidate in mean_windows
            for momentum_candidate in momentum_windows
            if 2 <= mean_candidate <= 252 and 1 <= momentum_candidate <= 120
        ]

    if parsed.kind == "volatility" and parsed.volatility_window is not None:
        base_window = parsed.volatility_window
        windows = [base_window, 5, 10, 20, 40, 60]
        return [
            f"rank(ts_std(close, {window}))"
            for window in windows
            if 2 <= window <= 252
        ]

    if parsed.kind == "correlation" and parsed.correlation_window is not None:
        base_window = parsed.correlation_window
        windows = [base_window, 5, 10, 20, 40, 60]
        return [
            f"rank(ts_corr(rank(close), rank(volume), {window}))"
            for window in windows
            if 2 <= window <= 252
        ]

    return [
        "rank(close / ts_mean(close, 20))",
        "rank(ts_delta(close, 5) / ts_shift(close, 5))",
    ]


def _score_campaign_run(
    metrics: dict[str, Any] | None, gate_decision: dict[str, Any]
) -> float | None:
    if not metrics:
        return None
    rank_ic = abs(float(metrics.get("rank_ic_mean") or 0.0))
    coverage = float(metrics.get("coverage_days") or 0.0)
    inserted = float(metrics.get("inserted_values") or 0.0)
    score = min(
        100.0,
        rank_ic * 1200.0 + min(coverage, 252.0) / 5.0 + min(inserted, 10000.0) / 2000.0,
    )
    if gate_decision.get("eligible"):
        score += 10.0
    return round(min(score, 100.0), 4)


def _summarize_campaign_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item for item in items if item.get("status") == "completed"]
    failed = [item for item in items if item.get("status") != "completed"]
    scored = [item for item in completed if item.get("score") is not None]
    scored.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    best = scored[0] if scored else None

    def _metadata(item: dict[str, Any]) -> dict[str, Any]:
        value = item.get("metadata")
        return value if isinstance(value, dict) else {}

    def _operator_stats(source_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        completed_counts: dict[str, int] = {}
        best_scores: dict[str, float | None] = {}
        for item in source_items:
            operator = str(_metadata(item).get("operator") or "unknown")
            counts[operator] = counts.get(operator, 0) + 1
            if item.get("status") == "completed":
                completed_counts[operator] = completed_counts.get(operator, 0) + 1
            try:
                score = float(item.get("score")) if item.get("score") is not None else None
            except (TypeError, ValueError):
                score = None
            if score is not None and (
                best_scores.get(operator) is None or score > float(best_scores[operator] or 0)
            ):
                best_scores[operator] = score
        return [
            {
                "operator": operator,
                "totalCandidates": counts[operator],
                "completedRuns": completed_counts.get(operator, 0),
                "bestScore": best_scores.get(operator),
            }
            for operator in sorted(counts)
        ]

    reason_counts: dict[str, int] = {}
    for item in items:
        reason = str(
            _metadata(item).get("evolutionReason") or item.get("reason") or "unknown"
        ).strip() or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    reason_stats = [
        {"reason": reason, "count": reason_counts[reason]}
        for reason in sorted(reason_counts, key=lambda key: (-reason_counts[key], key))
    ]

    lineage_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, int]] = set()
    for item in items:
        metadata = _metadata(item)
        child = str(item.get("expression") or "")
        operator = str(metadata.get("operator") or "unknown")
        parents = metadata.get("parentExpressions")
        if not isinstance(parents, list):
            continue
        for parent in parents[:5]:
            parent_expression = str(parent or "")
            if not parent_expression or not child:
                continue
            edge_key = (parent_expression, child, int(item.get("generation") or 1))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            lineage_edges.append(
                {
                    "fromExpression": parent_expression,
                    "toExpression": child,
                    "operator": operator,
                    "generation": int(item.get("generation") or 1),
                    "score": item.get("score"),
                }
            )

    generation_stats: list[dict[str, Any]] = []
    for generation in sorted({int(item.get("generation") or 1) for item in items}):
        generation_items = [
            item for item in items if int(item.get("generation") or 1) == generation
        ]
        generation_completed = [
            item for item in generation_items if item.get("status") == "completed"
        ]
        generation_failed = [
            item for item in generation_items if item.get("status") != "completed"
        ]
        generation_scored = [
            item for item in generation_completed if item.get("score") is not None
        ]
        generation_scored.sort(
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )
        generation_best = generation_scored[0] if generation_scored else None
        generation_stats.append(
            {
                "generation": generation,
                "totalCandidates": len(generation_items),
                "completedRuns": len(generation_completed),
                "failedRuns": len(generation_failed),
                "operatorStats": _operator_stats(generation_items),
                "bestCandidateId": generation_best.get("candidateId")
                if generation_best
                else None,
                "bestRunId": generation_best.get("runId") if generation_best else None,
                "bestExpression": generation_best.get("expression")
                if generation_best
                else None,
                "bestScore": generation_best.get("score") if generation_best else None,
            }
        )
    return {
        "totalCandidates": len(items),
        "completedRuns": len(completed),
        "failedRuns": len(failed),
        "maxGenerations": max(
            [int(item.get("generation") or 1) for item in items],
            default=0,
        ),
        "completedGenerations": len(generation_stats),
        "generationStats": generation_stats,
        "operatorStats": _operator_stats(items),
        "reasonStats": reason_stats,
        "lineageEdges": lineage_edges[:100],
        "bestCandidateId": best.get("candidateId") if best else None,
        "bestRunId": best.get("runId") if best else None,
        "bestExpression": best.get("expression") if best else None,
        "bestScore": best.get("score") if best else None,
    }


def _build_factor_training_payload(
    promotion_row: dict[str, Any],
    active_features: list[str],
    payload: dict[str, Any],
    *,
    include_factor: bool = True,
    baseline_training_run_id: str | None = None,
) -> dict[str, Any]:
    feature_key = str(promotion_row["feature_key"])
    features = [feature for feature in active_features if feature]
    if include_factor and feature_key not in features:
        features.append(feature_key)
    if not include_factor:
        features = [feature for feature in features if feature != feature_key]
        if not features:
            raise ValueError(
                "baseline training requires at least one non-factor feature"
            )

    run_params = (
        promotion_row.get("run_params_json")
        if isinstance(promotion_row.get("run_params_json"), dict)
        else {}
    )
    start_date = _date_or_none(payload.get("train_start")) or _date_or_none(
        run_params.get("start_date")
    )
    end_date = _date_or_none(payload.get("test_end")) or _date_or_none(
        run_params.get("end_date")
    )
    if start_date is None or end_date is None or start_date >= end_date:
        raise ValueError("valid training date range is required")

    train_start, train_end, valid_start, valid_end, test_start, test_end = (
        _split_training_dates(
            start_date,
            end_date,
            payload,
        )
    )
    target_horizon_days = max(
        1,
        min(
            int(
                payload.get("target_horizon_days")
                or run_params.get("holding_period")
                or 5
            ),
            30,
        ),
    )
    lgb_params = (
        payload.get("lgb_params") if isinstance(payload.get("lgb_params"), dict) else {}
    )
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    pipeline_stage = (
        "factor_shadow_training" if include_factor else "factor_baseline_training"
    )
    default_display_name = (
        f"因子研究 Shadow 训练 - {promotion_row.get('candidate_name') or feature_key}"
        if include_factor
        else f"因子研究 Baseline 训练 - {promotion_row.get('candidate_name') or feature_key}"
    )
    display_name = str(
        (
            payload.get("display_name")
            if include_factor
            else payload.get("baseline_display_name")
        )
        or default_display_name
    ).strip()
    job_prefix = "factor_shadow" if include_factor else "factor_baseline"
    requested_baseline_run_id = baseline_training_run_id or payload.get(
        "baseline_training_run_id"
    )

    return {
        "job_name": f"{job_prefix}_{feature_key}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "display_name": display_name[:128],
        "model_type": "lightgbm",
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "valid_start": valid_start.isoformat(),
        "valid_end": valid_end.isoformat(),
        "test_start": test_start.isoformat(),
        "test_end": test_end.isoformat(),
        "val_ratio": max(
            0.01,
            min(
                0.5,
                (valid_end - valid_start).days / max(1, (train_end - train_start).days),
            ),
        ),
        "num_boost_round": int(
            payload.get("num_boost_round") or lgb_params.get("num_boost_round") or 1000
        ),
        "early_stopping_rounds": int(payload.get("early_stopping_rounds") or 100),
        "features": features,
        "feature_categories": ["factor_research"],
        "target_horizon_days": target_horizon_days,
        "target_mode": str(payload.get("target_mode") or "return"),
        "label_formula": str(
            payload.get("label_formula") or f"return_t_plus_{target_horizon_days}"
        ),
        "effective_trade_date": test_end.isoformat(),
        "training_window": (
            f"{train_start.isoformat()}~{train_end.isoformat()} | "
            f"{valid_start.isoformat()}~{valid_end.isoformat()} | "
            f"{test_start.isoformat()}~{test_end.isoformat()}"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context": {
            "initial_capital": context.get(
                "initial_capital", context.get("initialCapital", 1_000_000)
            ),
            "commission_rate": context.get(
                "commission_rate", context.get("commissionRate", 0.00025)
            ),
            "slippage": context.get("slippage", 0.0005),
            "deal_price": context.get("deal_price", context.get("dealPrice", "close")),
            "limit_up_weight": context.get(
                "limit_up_weight", context.get("limitUpWeight", 0.5)
            ),
        },
        "lgb_params": {
            "learning_rate": lgb_params.get("learning_rate", 0.05),
            "num_leaves": lgb_params.get("num_leaves", 64),
            "max_depth": lgb_params.get("max_depth", -1),
            "min_data_in_leaf": lgb_params.get("min_data_in_leaf", 50),
            "lambda_l1": lgb_params.get("lambda_l1", 0.0),
            "lambda_l2": lgb_params.get("lambda_l2", 0.0),
            "feature_fraction": lgb_params.get("feature_fraction", 0.8),
            "bagging_fraction": lgb_params.get("bagging_fraction", 0.8),
            "objective": lgb_params.get("objective", "regression"),
            "metric": lgb_params.get("metric", "l2"),
        },
        "factor_research": {
            "promotion_id": promotion_row.get("id"),
            "candidate_id": promotion_row.get("candidate_id"),
            "factor_run_id": promotion_row.get("run_id"),
            "feature_key": feature_key,
            "feature_set_version_id": promotion_row.get("version_id"),
            "expression": promotion_row.get("expression"),
            "pipeline_stage": pipeline_stage,
            "includes_promoted_factor": include_factor,
            "baseline_training_run_id": requested_baseline_run_id,
            "baseline_metrics": payload.get("baseline_metrics")
            if isinstance(payload.get("baseline_metrics"), dict)
            else None,
        },
    }


def _split_training_dates(
    start_date: date,
    end_date: date,
    payload: dict[str, Any],
) -> tuple[date, date, date, date, date, date]:
    explicit = [
        _date_or_none(payload.get("train_start")),
        _date_or_none(payload.get("train_end")),
        _date_or_none(payload.get("valid_start")),
        _date_or_none(payload.get("valid_end")),
        _date_or_none(payload.get("test_start")),
        _date_or_none(payload.get("test_end")),
    ]
    if all(item is not None for item in explicit):
        train_start, train_end, valid_start, valid_end, test_start, test_end = explicit
    else:
        total_days = max(6, (end_date - start_date).days)
        train_days = max(2, int(total_days * 0.7))
        valid_days = max(2, int(total_days * 0.15))
        train_start = start_date
        train_end = train_start + timedelta(days=train_days)
        valid_start = train_end + timedelta(days=1)
        valid_end = valid_start + timedelta(days=valid_days)
        test_start = valid_end + timedelta(days=1)
        test_end = end_date

    if not (train_start < train_end < valid_start < valid_end < test_start < test_end):
        raise ValueError("training split dates must be strictly increasing")
    return train_start, train_end, valid_start, valid_end, test_start, test_end


async def _get_candidate_and_run_for_promotion(
    session,
    *,
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    run_id: str | None,
) -> Any | None:
    run_filter = "AND r0.id = :run_id" if run_id else ""
    params = {
        "candidate_id": candidate_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "run_id": run_id,
    }
    return (
        (
            await session.execute(
                text(
                    f"""
                SELECT
                    c.id AS candidate_id,
                    c.name,
                    c.expression,
                    c.expression_hash,
                    r.id AS run_id,
                    r.status AS run_status,
                    r.metrics_json AS run_metrics_json,
                    r.gate_decision_json AS run_gate_decision_json
                FROM qm_factor_candidates c
                JOIN LATERAL (
                    SELECT *
                    FROM qm_factor_candidate_runs r0
                    WHERE r0.candidate_id = c.id
                      {run_filter}
                    ORDER BY r0.created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE c.id = :candidate_id
                  AND c.tenant_id = :tenant_id
                  AND c.user_id = :user_id
                """
                ),
                params,
            )
        )
        .mappings()
        .first()
    )


async def _upsert_factor_shadow_signal_scores(
    session,
    *,
    tenant_id: str,
    user_id: str,
    signal_run_id: str,
    factor_run_id: str,
    trade_date: date,
    candidate_id: str,
    signals: list[dict[str, object]],
    metadata: dict[str, Any],
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO engine_feature_runs (
                run_id, tenant_id, user_id, trade_date, model_name, model_version,
                feature_version, feature_dim, window_start, window_end,
                status, expected_symbols, ready_symbols, missing_symbols,
                source, checksum, quality, error_message, created_at, updated_at
            )
            VALUES (
                :run_id, :tenant_id, :user_id, :trade_date, 'factor_shadow',
                'factor_shadow', :feature_version, 1, :trade_date, :trade_date,
                'signal_ready', :expected_symbols, :ready_symbols, 0,
                'factor_research', :checksum, CAST(:quality AS JSONB), NULL, NOW(), NOW()
            )
            ON CONFLICT (run_id)
            DO UPDATE SET
                status = 'signal_ready',
                expected_symbols = EXCLUDED.expected_symbols,
                ready_symbols = EXCLUDED.ready_symbols,
                quality = EXCLUDED.quality,
                updated_at = NOW()
            """
        ),
        {
            "run_id": signal_run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "trade_date": trade_date,
            "feature_version": factor_run_id,
            "expected_symbols": len(signals),
            "ready_symbols": len(signals),
            "checksum": factor_run_id,
            "quality": _json(metadata),
        },
    )
    score_sql = text(
        """
        INSERT INTO engine_signal_scores (
            run_id, tenant_id, user_id, trade_date, symbol,
            model_version, feature_version,
            light_score, tft_score, fusion_score, risk_weight, regime, score_rank,
            universe_tag, signal_side, expected_price, quality, created_at
        ) VALUES (
            :run_id, :tenant_id, :user_id, :trade_date, :symbol,
            'factor_shadow', :feature_version,
            NULL, NULL, :fusion_score, 1.0, 'shadow', :score_rank,
            'factor_shadow', :signal_side, :expected_price, CAST(:quality AS JSONB), NOW()
        )
        ON CONFLICT (
            tenant_id, user_id, trade_date, symbol, model_version, feature_version, run_id
        )
        DO UPDATE SET
            fusion_score = EXCLUDED.fusion_score,
            score_rank = EXCLUDED.score_rank,
            signal_side = EXCLUDED.signal_side,
            expected_price = EXCLUDED.expected_price,
            quality = EXCLUDED.quality
        """
    )
    for rank, signal in enumerate(signals, start=1):
        await session.execute(
            score_sql,
            {
                "run_id": signal_run_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "trade_date": trade_date,
                "symbol": signal["symbol"],
                "feature_version": factor_run_id,
                "fusion_score": float(signal["score"]),
                "score_rank": rank,
                "signal_side": signal["side"],
                "expected_price": float(signal.get("price") or 0.0),
                "quality": _json(
                    {
                        **metadata,
                        "candidate_id": candidate_id,
                        "factor_run_id": factor_run_id,
                        "signal_id": signal.get("signal_id"),
                        "signal_source": "factor_shadow",
                    }
                ),
            },
        )


def _publish_factor_shadow_signal_stream(
    *,
    tenant_id: str,
    user_id: str,
    signal_run_id: str,
    signals: list[dict[str, object]],
    enabled: bool,
    redis_client: Any | None = None,
) -> int:
    if not enabled or not signals:
        return 0
    if redis_client is None:
        from backend.shared.redis_sentinel_client import get_redis_sentinel_client

        redis_client = get_redis_sentinel_client()
    stream = f"qm:signal:stream:{tenant_id or 'default'}"
    latest_key = f"qm:signal:latest:{tenant_id or 'default'}:{user_id}"
    published = 0
    for signal in signals:
        payload = {
            "event_type": "signal_created",
            "tenant_id": tenant_id,
            "user_id": user_id,
            "run_id": signal_run_id,
            "signal_id": str(signal.get("signal_id") or ""),
            "client_order_id": str(signal.get("client_order_id") or ""),
            "symbol": str(signal.get("symbol") or ""),
            "side": str(signal.get("side") or ""),
            "trade_action": str(signal.get("trade_action") or ""),
            "position_side": str(signal.get("position_side") or ""),
            "is_margin_trade": str(bool(signal.get("is_margin_trade"))).lower(),
            "quantity": str(int(signal.get("quantity") or 0)),
            "price": str(float(signal.get("price") or 0.0)),
            "score": str(float(signal.get("score") or 0.0)),
            "signal_source": "factor_shadow",
            "trade_date": str(signal.get("trade_date") or ""),
        }
        redis_client.xadd(stream, payload, maxlen=200000, approximate=True)
        published += 1
    if published:
        redis_client.set(latest_key, signal_run_id, ex=86400)
    return published


def _safe_feature_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    key = re.sub(r"[^a-z0-9_]+", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    if not key:
        raise ValueError("feature key is required")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,95}", key):
        raise ValueError("invalid feature key")
    return key


def _factor_feature_id(feature_key: str) -> str:
    return f"feat_{_safe_feature_key(feature_key)}"


def _check_feature_snapshot_materialization(feature_key: str) -> dict[str, Any]:
    if not _FEATURE_SNAPSHOT_DIR.exists():
        return {
            "status": "pending_materialization",
            "reason": "feature_snapshot_dir_missing",
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    paths = sorted(_FEATURE_SNAPSHOT_DIR.glob("model_features_*.parquet"))
    if not paths:
        return {
            "status": "pending_materialization",
            "reason": "feature_snapshot_files_missing",
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    try:
        import pyarrow.parquet as pq
    except Exception as exc:
        return {
            "status": "unknown",
            "reason": "pyarrow_unavailable",
            "error": str(exc),
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    for path in reversed(paths):
        try:
            columns = set(pq.read_schema(path).names)
        except Exception:
            continue
        if feature_key in columns:
            return {
                "status": "materialized",
                "reason": "feature_snapshot_column_found",
                "path": str(path),
            }
    return {
        "status": "pending_materialization",
        "reason": "feature_snapshot_column_missing",
        "path": str(_FEATURE_SNAPSHOT_DIR),
        "checked_files": len(paths),
    }


def _prefix_symbol_for_materialization(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if re.fullmatch(r"[0-9]{6}\.SS", raw):
        raw = f"{raw[:6]}.SH"
    prefix = StockCodeUtil.to_prefix(raw)
    if re.fullmatch(r"(SH|SZ|BJ)[0-9]{6}", prefix):
        return prefix
    return None


async def _load_local_snapshot_base_rows_for_factor_values(
    session,
    values: list[dict[str, Any]],
) -> dict[str, Any]:
    keys: dict[tuple[str, str], dict[str, str]] = {}
    for item in values:
        trade_date_value = _date_or_none(item.get("trade_date"))
        symbol = _prefix_symbol_for_materialization(item.get("symbol"))
        if trade_date_value is None or symbol is None:
            continue
        keys[(trade_date_value.isoformat(), symbol)] = {
            "trade_date": trade_date_value.isoformat(),
            "symbol": symbol,
        }
    if not keys:
        return {
            "status": "unavailable",
            "reason": "factor_value_keys_empty",
            "row_count": 0,
        }

    table = _safe_table_name(
        os.getenv("FACTOR_RESEARCH_DATA_TABLE", "stock_daily_latest")
    )
    contract = local_market_data_contract(table)
    try:
        table_exists = (
            await session.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table}"},
            )
        ).scalar_one()
        if not table_exists:
            return {
                "status": "unavailable",
                "reason": "data_table_missing",
                "source": contract.source,
                "table": contract.table,
                "row_count": 0,
            }

        normalized_symbol = prefix_symbol_sql("m.symbol")
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        WITH keys AS (
                            SELECT DISTINCT
                                trade_date::date AS trade_date,
                                UPPER(symbol) AS symbol
                            FROM jsonb_to_recordset(CAST(:keys_json AS JSONB))
                                AS x(trade_date TEXT, symbol TEXT)
                        )
                        SELECT
                            m.trade_date::date AS trade_date,
                            {normalized_symbol} AS symbol,
                            m.open::double precision AS open,
                            m.high::double precision AS high,
                            m.low::double precision AS low,
                            m.close::double precision AS close,
                            m.volume::double precision AS volume
                        FROM {contract.table} m
                        JOIN keys k
                          ON m.trade_date::date = k.trade_date
                         AND {normalized_symbol} = k.symbol
                        WHERE m.open IS NOT NULL
                          AND m.high IS NOT NULL
                          AND m.low IS NOT NULL
                          AND m.close IS NOT NULL
                          AND m.volume IS NOT NULL
                          AND m.volume > 0
                        ORDER BY m.trade_date ASC, symbol ASC
                        """
                    ),
                    {"keys_json": _json_array(list(keys.values()))},
                )
            )
            .mappings()
            .all()
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "local_market_data_query_failed",
            "source": contract.source,
            "table": contract.table,
            "row_count": 0,
            "error": str(exc),
        }

    return {
        "status": "loaded" if rows else "unavailable",
        "reason": (
            "local_market_data_rows_loaded"
            if rows
            else "local_market_data_rows_missing"
        ),
        "source": contract.source,
        "table": contract.table,
        "requested_keys": len(keys),
        "row_count": len(rows),
        "rows": [dict(row) for row in rows],
    }


def _create_baseline_feature_snapshot(
    *,
    pd,
    path: Path,
    feature_key: str,
    year_values,
    base_rows: list[dict[str, Any]] | None,
    base_source: str = "local_market_data",
) -> dict[str, Any]:
    if not base_rows:
        return {
            "path": str(path),
            "status": "skipped",
            "reason": "local_market_base_rows_missing",
        }

    base_df = pd.DataFrame(base_rows)
    required_columns = [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    missing_columns = [
        column for column in required_columns if column not in base_df.columns
    ]
    if missing_columns:
        return {
            "path": str(path),
            "status": "skipped",
            "reason": "local_market_base_columns_missing",
            "missing_columns": missing_columns,
        }

    year_int = int(year_values["year"].iloc[0])
    base_df["__qm_trade_date"] = pd.to_datetime(
        base_df["trade_date"], errors="coerce"
    ).dt.date
    base_df["__qm_symbol_key"] = base_df["symbol"].map(_snapshot_symbol_key)
    base_df["__qm_year"] = pd.to_datetime(base_df["__qm_trade_date"]).dt.year
    base_df = base_df.dropna(subset=["__qm_trade_date", "__qm_symbol_key"])
    base_df = base_df[base_df["__qm_year"] == year_int].copy()
    if base_df.empty:
        return {
            "path": str(path),
            "status": "skipped",
            "reason": "local_market_base_year_missing",
        }

    merge_values = year_values[["trade_date", "symbol_key", feature_key]].rename(
        columns={"trade_date": "__qm_trade_date", "symbol_key": "__qm_symbol_key"}
    )
    output = base_df.merge(
        merge_values,
        on=["__qm_trade_date", "__qm_symbol_key"],
        how="inner",
    )
    output = output.dropna(subset=[feature_key]).copy()
    if output.empty:
        return {
            "path": str(path),
            "status": "skipped",
            "reason": "no_matching_local_market_rows",
        }

    output["trade_date"] = pd.to_datetime(output["__qm_trade_date"]).dt.strftime(
        "%Y-%m-%d"
    )
    output["symbol"] = output["__qm_symbol_key"]
    for column in ["open", "high", "low", "close", "volume", feature_key]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.dropna(subset=required_columns + [feature_key])
    if output.empty:
        return {
            "path": str(path),
            "status": "skipped",
            "reason": "local_market_base_numeric_values_missing",
        }

    output = (
        output[required_columns + [feature_key]]
        .drop_duplicates(subset=["trade_date", "symbol"], keep="last")
        .sort_values(["trade_date", "symbol"])
        .reset_index(drop=True)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    output.to_parquet(temp_path, index=False, engine="pyarrow", compression="zstd")
    temp_path.replace(path)
    source_label = (
        "qlib_provider" if base_source == "qlib_provider" else "local_market_data"
    )
    return {
        "path": str(path),
        "status": "created",
        "updated_rows": int(output[feature_key].notna().sum()),
        "column_count": len(output.columns),
        "reason": f"baseline_snapshot_created_from_{source_label}",
        "base_source": source_label,
    }


def _load_qlib_snapshot_base_rows_for_factor_values(values_df) -> dict[str, Any]:
    valid_values = values_df.dropna(subset=["trade_date", "symbol_key"])
    if valid_values.empty:
        return {
            "status": "unavailable",
            "reason": "factor_value_keys_empty",
            "source": "qlib_provider",
            "row_count": 0,
        }
    start_date = valid_values["trade_date"].min()
    end_date = valid_values["trade_date"].max()
    qlib_data = _load_qlib_ohlcv_frame(start_date, end_date)
    if qlib_data.get("status") != "loaded":
        return qlib_data

    frame = qlib_data["frame"].copy()
    frame["symbol_key"] = frame["symbol"].map(_snapshot_symbol_key)
    keys = {
        (item["trade_date"], item["symbol_key"])
        for item in valid_values[["trade_date", "symbol_key"]].to_dict("records")
    }
    matched = frame[
        frame.apply(lambda row: (row["trade_date"], row["symbol_key"]) in keys, axis=1)
    ].copy()
    if matched.empty:
        return {
            "status": "unavailable",
            "reason": "qlib_base_rows_missing",
            "source": "qlib_provider",
            "path": qlib_data.get("path"),
            "requested_keys": len(keys),
            "row_count": 0,
        }
    rows = matched[
        ["trade_date", "symbol", "open", "high", "low", "close", "volume"]
    ].to_dict("records")
    return {
        "status": "loaded",
        "reason": "qlib_base_rows_loaded",
        "source": "qlib_provider",
        "path": qlib_data.get("path"),
        "requested_keys": len(keys),
        "row_count": len(rows),
        "rows": rows,
    }


def _materialize_feature_values_to_snapshots(
    *,
    feature_key: str,
    values: list[dict[str, Any]],
    base_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        import pandas as pd
    except Exception as exc:
        return {
            "status": "unknown",
            "reason": "pandas_unavailable",
            "error": str(exc),
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    values_df = pd.DataFrame(values)
    if values_df.empty:
        return {"status": "pending_materialization", "reason": "factor_values_empty"}
    values_df["trade_date"] = pd.to_datetime(
        values_df["trade_date"], errors="coerce"
    ).dt.date
    values_df["symbol_key"] = values_df["symbol"].map(_snapshot_symbol_key)
    values_df = values_df.dropna(subset=["trade_date", "symbol_key"])
    values_df["year"] = pd.to_datetime(values_df["trade_date"]).dt.year
    values_df = values_df.rename(columns={"factor_value": feature_key})
    values_df = values_df.drop_duplicates(
        subset=["trade_date", "symbol_key"], keep="last"
    )

    base_source = "local_market_data" if base_rows else ""
    qlib_base_data: dict[str, Any] | None = None
    if not base_rows:
        qlib_base_data = _load_qlib_snapshot_base_rows_for_factor_values(values_df)
        if qlib_base_data.get("status") == "loaded":
            base_rows = qlib_base_data.get("rows") or []
            base_source = "qlib_provider"

    if not _FEATURE_SNAPSHOT_DIR.exists() and not base_rows:
        return {
            "status": "pending_materialization",
            "reason": "feature_snapshot_dir_missing",
            "path": str(_FEATURE_SNAPSHOT_DIR),
            "base_data": qlib_base_data,
        }

    touched_files: list[dict[str, Any]] = []
    total_updated_rows = 0
    missing_years: list[int] = []
    created_baseline_files = 0

    for year, year_values in values_df.groupby("year"):
        year_int = int(year)
        path = _FEATURE_SNAPSHOT_DIR / f"model_features_{year_int}.parquet"
        if not path.exists():
            created = _create_baseline_feature_snapshot(
                pd=pd,
                path=path,
                feature_key=feature_key,
                year_values=year_values,
                base_rows=base_rows,
                base_source=base_source or "local_market_data",
            )
            touched_files.append(created)
            if created["status"] == "created":
                total_updated_rows += int(created.get("updated_rows") or 0)
                created_baseline_files += 1
            else:
                missing_years.append(year_int)
            continue

        df = pd.read_parquet(path, engine="pyarrow")
        if "trade_date" not in df.columns or "symbol" not in df.columns:
            touched_files.append(
                {
                    "path": str(path),
                    "status": "skipped",
                    "reason": "missing_trade_date_or_symbol",
                }
            )
            continue

        original_columns = list(df.columns)
        original_symbol = df["symbol"].copy()
        df["__qm_trade_date"] = pd.to_datetime(
            df["trade_date"], errors="coerce"
        ).dt.date
        df["__qm_symbol_key"] = df["symbol"].map(_snapshot_symbol_key)
        merge_values = year_values[["trade_date", "symbol_key", feature_key]].rename(
            columns={"trade_date": "__qm_trade_date", "symbol_key": "__qm_symbol_key"}
        )
        merged = df.merge(
            merge_values,
            on=["__qm_trade_date", "__qm_symbol_key"],
            how="left",
            suffixes=("", "__new"),
        )

        if f"{feature_key}__new" in merged.columns:
            new_values = merged[f"{feature_key}__new"]
            if feature_key in original_columns:
                merged[feature_key] = new_values.combine_first(merged[feature_key])
            else:
                merged[feature_key] = new_values
            merged = merged.drop(columns=[f"{feature_key}__new"])
        elif feature_key not in merged.columns:
            merged[feature_key] = None

        updated_rows = int(merged[feature_key].notna().sum())
        if updated_rows <= 0:
            touched_files.append(
                {
                    "path": str(path),
                    "status": "skipped",
                    "reason": "no_matching_rows",
                }
            )
            continue

        merged["symbol"] = original_symbol
        output_columns = (
            original_columns
            if feature_key in original_columns
            else [*original_columns, feature_key]
        )
        output = merged[output_columns].copy()
        temp_path = path.with_suffix(path.suffix + ".tmp")
        output.to_parquet(temp_path, index=False, engine="pyarrow", compression="zstd")
        temp_path.replace(path)

        total_updated_rows += updated_rows
        touched_files.append(
            {
                "path": str(path),
                "status": "updated",
                "updated_rows": updated_rows,
                "column_count": len(output.columns),
            }
        )

    if total_updated_rows <= 0:
        snapshot_exists = _FEATURE_SNAPSHOT_DIR.exists()
        return {
            "status": "pending_materialization",
            "reason": (
                "feature_snapshot_files_missing"
                if not snapshot_exists
                or not list(_FEATURE_SNAPSHOT_DIR.glob("model_features_*.parquet"))
                else "no_snapshot_rows_updated"
            ),
            "path": str(_FEATURE_SNAPSHOT_DIR),
            "missing_years": missing_years,
            "files": touched_files,
        }

    return {
        "status": "materialized",
        "reason": (
            f"baseline_snapshots_created_from_{base_source}"
            if created_baseline_files and created_baseline_files == len(touched_files)
            else "feature_values_materialized_to_snapshots"
        ),
        "path": str(_FEATURE_SNAPSHOT_DIR),
        "updated_rows": total_updated_rows,
        "created_baseline_files": created_baseline_files,
        "missing_years": missing_years,
        "files": touched_files,
    }


def _snapshot_symbol_key(value: Any) -> str | None:
    symbol = str(value or "").strip().upper()
    if not symbol:
        return None
    if re.fullmatch(r"(SH|SZ|BJ)[0-9]{6}", symbol):
        return symbol[2:]
    if re.fullmatch(r"[0-9]{6}\.(SH|SS|SZ|BJ)", symbol):
        return symbol[:6]
    digits = re.sub(r"\D", "", symbol)
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6) if digits else None


async def _activate_feature_set_without_feature(
    session,
    *,
    feature_key: str,
    promotion_id: str,
    reason: str,
    base_items: list[dict[str, Any]] | None = None,
) -> str:
    items = [
        item
        for item in (base_items or await _load_active_feature_catalog_items(session))
        if item.get("feature_key") != feature_key
    ]
    if not items:
        items = [
            item
            for item in _load_fallback_feature_catalog_items()
            if item.get("feature_key") != feature_key
        ]

    version_id = f"factor_rollback_{promotion_id.replace('-', '')[:12]}"
    category_seen: set[str] = set()
    for item in items:
        category_id = str(item["category_id"])
        if category_id in category_seen:
            continue
        category_seen.add(category_id)
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_category (category_id, category_name, sort_order, created_at, updated_at)
                VALUES (:category_id, :category_name, :sort_order, NOW(), NOW())
                ON CONFLICT (category_id)
                DO UPDATE SET category_name = EXCLUDED.category_name,
                              sort_order = EXCLUDED.sort_order,
                              updated_at = NOW()
                """
            ),
            {
                "category_id": category_id,
                "category_name": item["category_name"],
                "sort_order": int(item.get("category_order") or 0),
            },
        )

    for item in items:
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_definition (
                    feature_id, feature_key, feature_name, formula, source_table_fields,
                    metadata_json, created_at, updated_at
                )
                VALUES (
                    :feature_id, :feature_key, :feature_name, :formula, :source_table_fields,
                    CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                ON CONFLICT (feature_key)
                DO UPDATE SET feature_name = EXCLUDED.feature_name,
                              formula = EXCLUDED.formula,
                              source_table_fields = EXCLUDED.source_table_fields,
                              metadata_json = qm_feature_definition.metadata_json || EXCLUDED.metadata_json,
                              updated_at = NOW()
                """
            ),
            {
                "feature_id": item["feature_id"],
                "feature_key": item["feature_key"],
                "feature_name": item["feature_name"],
                "formula": item.get("formula") or "",
                "source_table_fields": item.get("source_table_fields") or "",
                "metadata_json": _json(item.get("metadata") or {}),
            },
        )

    await session.execute(
        text(
            """
            UPDATE qm_feature_set_version
            SET status = 'archived', updated_at = NOW()
            WHERE status = 'active'
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO qm_feature_set_version (
                version_id, version_name, feature_count, status, effective_at,
                metadata_json, created_at, updated_at
            )
            VALUES (
                :version_id, :version_name, :feature_count, 'active', NOW(),
                CAST(:metadata_json AS JSONB), NOW(), NOW()
            )
            ON CONFLICT (version_id)
            DO UPDATE SET version_name = EXCLUDED.version_name,
                          feature_count = EXCLUDED.feature_count,
                          status = 'active',
                          effective_at = NOW(),
                          metadata_json = qm_feature_set_version.metadata_json || EXCLUDED.metadata_json,
                          updated_at = NOW()
            """
        ),
        {
            "version_id": version_id,
            "version_name": f"Factor Rollback Feature Set {promotion_id[:8]}",
            "feature_count": len(items),
            "metadata_json": _json(
                {
                    "source": "factor_research",
                    "action": "rollback",
                    "promotion_id": promotion_id,
                    "removed_feature_key": feature_key,
                    "reason": reason,
                }
            ),
        },
    )
    await session.execute(
        text("DELETE FROM qm_feature_set_item WHERE version_id = :version_id"),
        {"version_id": version_id},
    )
    for index, item in enumerate(items, start=1):
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_set_item (
                    version_id, feature_key, category_id, order_no, enabled, created_at, updated_at
                )
                VALUES (:version_id, :feature_key, :category_id, :order_no, :enabled, NOW(), NOW())
                """
            ),
            {
                "version_id": version_id,
                "feature_key": item["feature_key"],
                "category_id": item["category_id"],
                "order_no": int(item.get("order_no") or index),
                "enabled": bool(item.get("enabled", True)),
            },
        )
    return version_id


async def _activate_materialized_feature_set(
    session, *, version_id: str, feature_key: str
) -> None:
    if not version_id:
        return
    await session.execute(
        text(
            """
            UPDATE qm_feature_set_version
            SET status = 'archived', updated_at = NOW()
            WHERE status = 'active' AND version_id != :version_id
            """
        ),
        {"version_id": version_id},
    )
    await session.execute(
        text(
            """
            UPDATE qm_feature_set_item
            SET enabled = TRUE, updated_at = NOW()
            WHERE version_id = :version_id AND feature_key = :feature_key
            """
        ),
        {"version_id": version_id, "feature_key": feature_key},
    )
    await session.execute(
        text(
            """
            UPDATE qm_feature_set_version
            SET status = 'active',
                effective_at = COALESCE(effective_at, NOW()),
                updated_at = NOW()
            WHERE version_id = :version_id
            """
        ),
        {"version_id": version_id},
    )


async def _create_factor_shadow_feature_set(
    session,
    *,
    feature_key: str,
    feature_id: str,
    feature_name: str,
    formula: str,
    run_id: str,
    candidate_id: str,
    materialized: bool,
) -> str:
    base_items = await _load_active_feature_catalog_items(session)
    if not base_items:
        base_items = _load_fallback_feature_catalog_items()

    factor_item = {
        "category_id": _FACTOR_RESEARCH_CATEGORY_ID,
        "category_name": "因子研究",
        "category_order": 900,
        "feature_id": feature_id,
        "feature_key": feature_key,
        "feature_name": feature_name,
        "formula": formula,
        "source_table_fields": f"qm_factor_values.run_id={run_id}",
        "enabled": materialized,
        "order_no": len(base_items) + 1,
        "metadata": {
            "source": "factor_research",
            "candidate_id": candidate_id,
            "run_id": run_id,
            "materialized": materialized,
        },
    }
    items = [item for item in base_items if item["feature_key"] != feature_key]
    items.append(factor_item)

    category_seen: set[str] = set()
    for item in items:
        cid = str(item["category_id"])
        if cid in category_seen:
            continue
        category_seen.add(cid)
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_category (category_id, category_name, sort_order, created_at, updated_at)
                VALUES (:category_id, :category_name, :sort_order, NOW(), NOW())
                ON CONFLICT (category_id)
                DO UPDATE SET category_name = EXCLUDED.category_name,
                              sort_order = EXCLUDED.sort_order,
                              updated_at = NOW()
                """
            ),
            {
                "category_id": cid,
                "category_name": item["category_name"],
                "sort_order": int(item.get("category_order") or 0),
            },
        )

    for item in items:
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_definition (
                    feature_id, feature_key, feature_name, formula, source_table_fields,
                    metadata_json, created_at, updated_at
                )
                VALUES (
                    :feature_id, :feature_key, :feature_name, :formula, :source_table_fields,
                    CAST(:metadata_json AS JSONB), NOW(), NOW()
                )
                ON CONFLICT (feature_key)
                DO UPDATE SET feature_name = EXCLUDED.feature_name,
                              formula = EXCLUDED.formula,
                              source_table_fields = EXCLUDED.source_table_fields,
                              metadata_json = qm_feature_definition.metadata_json || EXCLUDED.metadata_json,
                              updated_at = NOW()
                """
            ),
            {
                "feature_id": item["feature_id"],
                "feature_key": item["feature_key"],
                "feature_name": item["feature_name"],
                "formula": item.get("formula") or "",
                "source_table_fields": item.get("source_table_fields") or "",
                "metadata_json": _json(item.get("metadata") or {}),
            },
        )

    status = "active" if materialized else "shadow"
    if materialized:
        await session.execute(
            text(
                """
                UPDATE qm_feature_set_version
                SET status = 'archived', updated_at = NOW()
                WHERE status = 'active'
                """
            )
        )

    version_id = f"factor_shadow_{run_id.replace('-', '')[:12]}"
    await session.execute(
        text(
            """
            INSERT INTO qm_feature_set_version (
                version_id, version_name, feature_count, status, effective_at,
                metadata_json, created_at, updated_at
            )
            VALUES (
                :version_id, :version_name, :feature_count, :status,
                CASE WHEN :status = 'active' THEN NOW() ELSE NULL END,
                CAST(:metadata_json AS JSONB), NOW(), NOW()
            )
            ON CONFLICT (version_id)
            DO UPDATE SET version_name = EXCLUDED.version_name,
                          feature_count = EXCLUDED.feature_count,
                          status = EXCLUDED.status,
                          effective_at = EXCLUDED.effective_at,
                          metadata_json = qm_feature_set_version.metadata_json || EXCLUDED.metadata_json,
                          updated_at = NOW()
            """
        ),
        {
            "version_id": version_id,
            "version_name": f"Factor Shadow Feature Set {run_id[:8]}",
            "feature_count": len(items),
            "status": status,
            "metadata_json": _json(
                {
                    "source": "factor_research",
                    "candidate_id": candidate_id,
                    "run_id": run_id,
                    "materialized": materialized,
                }
            ),
        },
    )
    await session.execute(
        text("DELETE FROM qm_feature_set_item WHERE version_id = :version_id"),
        {"version_id": version_id},
    )
    for index, item in enumerate(items, start=1):
        await session.execute(
            text(
                """
                INSERT INTO qm_feature_set_item (
                    version_id, feature_key, category_id, order_no, enabled, created_at, updated_at
                )
                VALUES (:version_id, :feature_key, :category_id, :order_no, :enabled, NOW(), NOW())
                """
            ),
            {
                "version_id": version_id,
                "feature_key": item["feature_key"],
                "category_id": item["category_id"],
                "order_no": int(item.get("order_no") or index),
                "enabled": bool(item.get("enabled", True)),
            },
        )
    return version_id


async def _load_active_feature_catalog_items(session) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT
                    c.category_id,
                    c.category_name,
                    c.sort_order,
                    i.order_no,
                    i.enabled,
                    d.feature_id,
                    d.feature_key,
                    d.feature_name,
                    d.formula,
                    d.source_table_fields,
                    d.metadata_json
                FROM qm_feature_set_version v
                JOIN qm_feature_set_item i ON i.version_id = v.version_id
                JOIN qm_feature_definition d ON d.feature_key = i.feature_key
                JOIN qm_feature_category c ON c.category_id = i.category_id
                WHERE v.status = 'active'
                ORDER BY c.sort_order ASC, i.order_no ASC
                """
                )
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "category_id": str(row["category_id"]),
            "category_name": str(row["category_name"] or row["category_id"]),
            "category_order": int(row["sort_order"] or 0),
            "order_no": int(row["order_no"] or index),
            "enabled": bool(row["enabled"]),
            "feature_id": str(row["feature_id"] or row["feature_key"]),
            "feature_key": str(row["feature_key"]),
            "feature_name": str(row["feature_name"] or row["feature_key"]),
            "formula": str(row["formula"] or ""),
            "source_table_fields": str(row["source_table_fields"] or ""),
            "metadata": row.get("metadata_json") or {},
        }
        for index, row in enumerate(rows, start=1)
    ]


def _load_fallback_feature_catalog_items() -> list[dict[str, Any]]:
    if not _FEATURE_CATALOG_FALLBACK.exists():
        return []
    try:
        raw = json.loads(_FEATURE_CATALOG_FALLBACK.read_text(encoding="utf-8"))
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for cat in raw.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        category_id = str(cat.get("id") or "").strip()
        if not category_id:
            continue
        features = cat.get("features") if isinstance(cat.get("features"), list) else []
        for order, feat in enumerate(features, start=1):
            if not isinstance(feat, dict):
                continue
            feature_key = str(feat.get("key") or "").strip()
            if not feature_key:
                continue
            items.append(
                {
                    "category_id": category_id,
                    "category_name": str(cat.get("name") or category_id),
                    "category_order": int(cat.get("order") or 0),
                    "order_no": int(feat.get("order_no") or order),
                    "enabled": bool(feat.get("enabled", True)),
                    "feature_id": str(feat.get("feature_id") or feature_key),
                    "feature_key": feature_key,
                    "feature_name": str(
                        feat.get("description")
                        or feat.get("feature_name")
                        or feature_key
                    ),
                    "formula": str(feat.get("formula") or ""),
                    "source_table_fields": str(
                        feat.get("source") or feat.get("source_table_fields") or ""
                    ),
                    "metadata": {"source": "fallback_feature_catalog"},
                }
            )
    return items


def _factor_raw_value_sql(expression: str) -> str | None:
    parsed = parse_supported_factor_expression(expression)
    if parsed is None:
        return None

    if parsed.kind == "mean" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        return (
            f"{field} / NULLIF(AVG({field}) OVER "
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW), 0)"
        )

    if parsed.kind == "ts_rank" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        return (
            "("
            "SELECT CASE WHEN COUNT(*) <= 1 THEN 0.0 ELSE "
            f"(SUM(CASE WHEN rolling.{field} <= b.{field} THEN 1 ELSE 0 END) - 1)::double precision "
            "/ NULLIF(COUNT(*) - 1, 0) END "
            "FROM ("
            f"SELECT b2.{field} "
            "FROM base b2 "
            "WHERE b2.symbol = b.symbol AND b2.trade_date <= b.trade_date "
            "ORDER BY b2.trade_date DESC "
            f"LIMIT {window}"
            ") rolling"
            ")"
        )

    if parsed.kind == "decay_linear" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        return (
            "("
            "SELECT SUM(rolling.value * rolling.weight)::double precision "
            "/ NULLIF(SUM(rolling.weight), 0) "
            "FROM ("
            f"SELECT b2.{field} AS value, "
            f"({window} + 1 - ROW_NUMBER() OVER (ORDER BY b2.trade_date DESC)) AS weight "
            "FROM base b2 "
            "WHERE b2.symbol = b.symbol AND b2.trade_date <= b.trade_date "
            "ORDER BY b2.trade_date DESC "
            f"LIMIT {window}"
            ") rolling"
            ")"
        )

    if parsed.kind == "rolling_zscore" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        rolling_window = (
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )
        return (
            f"({field} - AVG({field}) OVER {rolling_window}) "
            f"/ NULLIF(STDDEV_SAMP({field}) OVER {rolling_window}, 0)"
        )

    if parsed.kind in {"zscore_cross_sectional", "scale_cross_sectional"} and parsed.field:
        return parsed.field

    if parsed.kind in {"momentum", "tanh_momentum"} and parsed.momentum_window:
        window = parsed.momentum_window
        return (
            f"(close - LAG(close, {window}) OVER (PARTITION BY symbol ORDER BY trade_date)) / "
            f"NULLIF(LAG(close, {window}) OVER (PARTITION BY symbol ORDER BY trade_date), 0)"
        )

    if parsed.kind == "volatility" and parsed.volatility_window:
        window = parsed.volatility_window
        return (
            "STDDEV_SAMP(close) OVER "
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )

    if parsed.kind == "correlation" and parsed.correlation_window:
        window = parsed.correlation_window
        return (
            "CORR(close, volume) OVER "
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )

    if parsed.kind == "where_mean" and parsed.mean_window:
        window = parsed.mean_window
        rolling_mean = (
            "AVG(close) OVER "
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )
        return f"CASE WHEN close > {rolling_mean} THEN close / NULLIF({rolling_mean}, 0) ELSE 0 END"

    if parsed.kind == "hybrid" and parsed.mean_window and parsed.momentum_window:
        mean_window = parsed.mean_window
        momentum_window = parsed.momentum_window
        mean_sql = (
            "close / NULLIF(AVG(close) OVER "
            f"(PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN {mean_window - 1} PRECEDING AND CURRENT ROW), 0)"
        )
        momentum_sql = (
            f"(close - LAG(close, {momentum_window}) OVER (PARTITION BY symbol ORDER BY trade_date)) / "
            f"NULLIF(LAG(close, {momentum_window}) OVER (PARTITION BY symbol ORDER BY trade_date), 0)"
        )
        return f"({mean_sql}) * ({momentum_sql})"

    return None


def _feature_snapshot_paths_for_range(start_date: date, end_date: date) -> list[Path]:
    if not _FEATURE_SNAPSHOT_DIR.exists():
        return []
    years = range(start_date.year, end_date.year + 1)
    return [
        _FEATURE_SNAPSHOT_DIR / f"model_features_{year}.parquet"
        for year in years
        if (_FEATURE_SNAPSHOT_DIR / f"model_features_{year}.parquet").exists()
    ]


def _load_feature_snapshot_ohlcv_frame(
    start_date: date, end_date: date
) -> dict[str, Any]:
    paths = _feature_snapshot_paths_for_range(start_date, end_date)
    if not paths:
        return {
            "status": "unavailable",
            "reason": "feature_snapshot_files_missing",
            "source": "feature_snapshot_parquet",
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    try:
        import pandas as pd
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "pandas_unavailable",
            "source": "feature_snapshot_parquet",
            "error": str(exc),
            "path": str(_FEATURE_SNAPSHOT_DIR),
        }

    required_columns = [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    frames = []
    skipped_files: list[dict[str, Any]] = []
    for path in paths:
        try:
            frame = pd.read_parquet(path, engine="pyarrow")
        except Exception as exc:
            skipped_files.append(
                {"path": str(path), "reason": "read_failed", "error": str(exc)}
            )
            continue
        missing = [column for column in required_columns if column not in frame.columns]
        if missing:
            skipped_files.append(
                {
                    "path": str(path),
                    "reason": "required_columns_missing",
                    "missing": missing,
                }
            )
            continue
        frames.append(frame[required_columns].copy())

    if not frames:
        return {
            "status": "unavailable",
            "reason": "feature_snapshot_ohlcv_missing",
            "source": "feature_snapshot_parquet",
            "path": str(_FEATURE_SNAPSHOT_DIR),
            "files": skipped_files,
        }

    data = pd.concat(frames, ignore_index=True)
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce").dt.date
    data["symbol"] = data["symbol"].map(_prefix_symbol_for_materialization)
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=required_columns)
    data = data[
        (data["trade_date"] >= start_date)
        & (data["trade_date"] <= end_date)
        & (data["volume"] > 0)
    ].copy()
    data = data.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    data = data.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    if data.empty:
        return {
            "status": "unavailable",
            "reason": "feature_snapshot_rows_missing",
            "source": "feature_snapshot_parquet",
            "path": str(_FEATURE_SNAPSHOT_DIR),
            "files": skipped_files,
        }
    return {
        "status": "loaded",
        "reason": "feature_snapshot_rows_loaded",
        "source": "feature_snapshot_parquet",
        "path": str(_FEATURE_SNAPSHOT_DIR),
        "file_count": len(paths),
        "row_count": int(len(data)),
        "frame": data,
        "files": skipped_files,
    }


def _qlib_provider_uri() -> Path:
    return Path(
        os.getenv(
            "FACTOR_RESEARCH_QLIB_PROVIDER_URI",
            os.getenv("QLIB_PROVIDER_URI", str(_PROJECT_ROOT / "db" / "qlib_data")),
        )
    )


def _load_qlib_ohlcv_frame(start_date: date, end_date: date) -> dict[str, Any]:
    provider_uri = _qlib_provider_uri()
    if not provider_uri.exists():
        return {
            "status": "unavailable",
            "reason": "qlib_provider_missing",
            "source": "qlib_provider",
            "path": str(provider_uri),
        }

    try:
        import qlib
        from qlib.data import D
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "qlib_unavailable",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "error": str(exc),
        }

    try:
        qlib.init(provider_uri=str(provider_uri), region="cn")
        instruments = D.list_instruments(D.instruments("all"), as_list=True)
        if not instruments:
            return {
                "status": "unavailable",
                "reason": "qlib_instruments_missing",
                "source": "qlib_provider",
                "path": str(provider_uri),
            }
        frame = D.features(
            instruments,
            ["$open", "$high", "$low", "$close", "$volume"],
            start_time=start_date.isoformat(),
            end_time=end_date.isoformat(),
        )
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "qlib_read_failed",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "error": str(exc),
        }

    try:
        import pandas as pd
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "pandas_unavailable",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "error": str(exc),
        }

    if frame is None or frame.empty:
        return {
            "status": "unavailable",
            "reason": "qlib_rows_missing",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "instrument_count": len(instruments),
        }

    data = frame.reset_index()
    rename_map = {
        "datetime": "trade_date",
        "date": "trade_date",
        "$open": "open",
        "$high": "high",
        "$low": "low",
        "$close": "close",
        "$volume": "volume",
    }
    data = data.rename(
        columns={key: value for key, value in rename_map.items() if key in data.columns}
    )
    if "instrument" not in data.columns or "trade_date" not in data.columns:
        return {
            "status": "unavailable",
            "reason": "qlib_required_columns_missing",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "columns": list(data.columns),
        }

    required_columns = [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    data["symbol"] = data["instrument"].map(_prefix_symbol_for_materialization)
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce").dt.date
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data = data.dropna(subset=required_columns)
    data = data[
        (data["trade_date"] >= start_date)
        & (data["trade_date"] <= end_date)
        & (data["volume"] > 0)
    ].copy()
    data = data[required_columns].drop_duplicates(
        subset=["trade_date", "symbol"], keep="last"
    )
    data = data.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    if data.empty:
        return {
            "status": "unavailable",
            "reason": "qlib_ohlcv_rows_missing",
            "source": "qlib_provider",
            "path": str(provider_uri),
            "instrument_count": len(instruments),
        }
    return {
        "status": "loaded",
        "reason": "qlib_ohlcv_rows_loaded",
        "source": "qlib_provider",
        "path": str(provider_uri),
        "instrument_count": len(instruments),
        "row_count": int(len(data)),
        "frame": data,
    }


def _quantgpt_runner_stock_code(symbol: Any) -> str | None:
    prefix = _prefix_symbol_for_materialization(symbol)
    if prefix is None:
        return None
    return f"{prefix[:2].lower()}.{prefix[2:]}"


def _build_quantgpt_runner_market_frame(
    frame: Any,
    *,
    source: str,
) -> dict[str, Any]:
    """Convert QuantMind OHLCV rows to QuantGPT run_factor_backtest market_df."""
    try:
        import pandas as pd
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "pandas_unavailable",
            "source": source,
            "error": str(exc),
        }

    required_columns = [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    if frame is None or getattr(frame, "empty", False):
        return {
            "status": "unavailable",
            "reason": "runner_input_rows_missing",
            "source": source,
        }
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        return {
            "status": "unavailable",
            "reason": "runner_input_required_columns_missing",
            "source": source,
            "missing": missing,
        }

    data = frame.copy()
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="coerce")
    data["stock_code"] = data["symbol"].map(_quantgpt_runner_stock_code)
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if "amount" in data.columns:
        data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    else:
        data["amount"] = data["close"] * data["volume"]
    data = data.dropna(
        subset=[
            "trade_date",
            "stock_code",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        ]
    )
    data = data[data["volume"] > 0].copy()
    if data.empty:
        return {
            "status": "unavailable",
            "reason": "runner_input_rows_missing",
            "source": source,
        }

    data = data.sort_values(["stock_code", "trade_date"]).drop_duplicates(
        subset=["trade_date", "stock_code"], keep="last"
    )
    if "pct_change" in data.columns:
        data["pct_change"] = pd.to_numeric(data["pct_change"], errors="coerce")
    else:
        data["pct_change"] = data.groupby("stock_code")["close"].pct_change() * 100
    data["pct_change"] = data["pct_change"].fillna(0.0)
    data = data[
        [
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
    ].reset_index(drop=True)
    return {
        "status": "loaded",
        "reason": "quantgpt_runner_input_loaded",
        "source": source,
        "row_count": int(len(data)),
        "stock_count": int(data["stock_code"].nunique()),
        "start_date": data["trade_date"].min().date().isoformat(),
        "end_date": data["trade_date"].max().date().isoformat(),
        "frame": data,
    }


def _load_qlib_quantgpt_runner_input(
    start_date: date, end_date: date
) -> dict[str, Any]:
    qlib_data = _load_qlib_ohlcv_frame(start_date, end_date)
    if qlib_data.get("status") != "loaded":
        return qlib_data
    runner_input = _build_quantgpt_runner_market_frame(
        qlib_data.get("frame"),
        source=str(qlib_data.get("source") or "qlib_provider"),
    )
    if runner_input.get("status") == "loaded":
        runner_input["path"] = qlib_data.get("path")
        runner_input["instrument_count"] = qlib_data.get("instrument_count")
    return runner_input


def _calculate_feature_snapshot_factor_values(
    *,
    frame: Any,
    expression: str,
    holding_period: int,
    source: str = "feature_snapshot_parquet",
) -> dict[str, Any]:
    parsed = parse_supported_factor_expression(expression)
    data = frame.copy().sort_values(["symbol", "trade_date"])
    if parsed is None:
        return {
            "status": "unavailable",
            "reason": "unsupported_expression",
            "source": source,
        }

    if "amount" in data.columns:
        data["amount"] = data["amount"]
    else:
        data["amount"] = data["close"] * data["volume"]
    if "vwap" in data.columns:
        data["vwap"] = data["vwap"]
    else:
        data["vwap"] = data["close"]

    if parsed.kind == "mean" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        data["raw_value"] = data[field] / data.groupby("symbol")[field].transform(
            lambda series: series.rolling(window=window, min_periods=1).mean()
        )
    elif parsed.kind == "ts_rank" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window

        def _last_value_percent_rank(values: Any) -> float:
            clean = [float(value) for value in values if value == value]
            if len(clean) <= 1:
                return 0.0
            current = clean[-1]
            return (sum(1 for value in clean if value <= current) - 1) / (len(clean) - 1)

        data["raw_value"] = data.groupby("symbol")[field].transform(
            lambda series: series.rolling(window=window, min_periods=1).apply(
                _last_value_percent_rank,
                raw=True,
            )
        )
    elif parsed.kind == "decay_linear" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window

        def _linear_decay(values: Any) -> float:
            clean = [float(value) for value in values if value == value]
            if not clean:
                return float("nan")
            weights = list(range(1, len(clean) + 1))
            return sum(
                value * weight for value, weight in zip(clean, weights, strict=True)
            ) / sum(weights)

        data["raw_value"] = data.groupby("symbol")[field].transform(
            lambda series: series.rolling(window=window, min_periods=1).apply(
                _linear_decay,
                raw=True,
            )
        )
    elif parsed.kind == "rolling_zscore" and parsed.field and parsed.mean_window:
        field = parsed.field
        window = parsed.mean_window
        grouped = data.groupby("symbol")[field]
        rolling_mean = grouped.transform(
            lambda series: series.rolling(window=window, min_periods=1).mean()
        )
        rolling_std = grouped.transform(
            lambda series: series.rolling(window=window, min_periods=2).std()
        )
        data["raw_value"] = (data[field] - rolling_mean) / rolling_std
    elif parsed.kind in {"zscore_cross_sectional", "scale_cross_sectional"} and parsed.field:
        data["raw_value"] = data[parsed.field]
    elif parsed.kind in {"momentum", "tanh_momentum"} and parsed.momentum_window:
        window = parsed.momentum_window
        shifted = data.groupby("symbol")["close"].shift(window)
        data["raw_value"] = (data["close"] - shifted) / shifted
    elif parsed.kind == "volatility" and parsed.volatility_window:
        window = parsed.volatility_window
        data["raw_value"] = data.groupby("symbol")["close"].transform(
            lambda series: series.rolling(window=window, min_periods=2).std()
        )
    elif parsed.kind == "correlation" and parsed.correlation_window:
        window = parsed.correlation_window
        data["raw_value"] = data.groupby("symbol", group_keys=False)[
            ["close", "volume"]
        ].apply(
            lambda group: group["close"]
            .rolling(window=window, min_periods=2)
            .corr(group["volume"])
        )
    elif parsed.kind == "hybrid" and parsed.mean_window and parsed.momentum_window:
        mean_window = parsed.mean_window
        momentum_window = parsed.momentum_window
        mean_component = data["close"] / data.groupby("symbol")["close"].transform(
            lambda series: series.rolling(window=mean_window, min_periods=1).mean()
        )
        shifted = data.groupby("symbol")["close"].shift(momentum_window)
        momentum_component = (data["close"] - shifted) / shifted
        data["raw_value"] = mean_component * momentum_component
    elif parsed.kind == "where_mean" and parsed.mean_window:
        window = parsed.mean_window
        rolling_mean = data.groupby("symbol")["close"].transform(
            lambda series: series.rolling(window=window, min_periods=1).mean()
        )
        mean_component = data["close"] / rolling_mean
        data["raw_value"] = mean_component.where(data["close"] > rolling_mean, 0.0)
    else:
        return {
            "status": "unavailable",
            "reason": "unsupported_expression",
            "source": source,
        }

    grouped_close = data.groupby("symbol")["close"]
    data["forward_return"] = (
        grouped_close.shift(-holding_period) / grouped_close.shift(-1) - 1
    )
    ranked = data.dropna(subset=["raw_value", "forward_return"]).copy()
    if ranked.empty:
        return {
            "status": "unavailable",
            "reason": "feature_snapshot_factor_values_empty",
            "source": source,
        }

    date_group = ranked.groupby("trade_date")["raw_value"]
    ranked["__rank"] = date_group.rank(method="min")
    ranked["__count"] = date_group.transform("count")
    ranked["factor_value"] = (ranked["__rank"] - 1) / (ranked["__count"] - 1)
    ranked.loc[ranked["__count"] <= 1, "factor_value"] = 0.0
    ranked = ranked.dropna(subset=["factor_value", "forward_return"])

    daily_ic_values: list[float] = []
    for _, group in ranked.groupby("trade_date"):
        if len(group) < 5:
            continue
        if group["factor_value"].nunique(dropna=True) < 2:
            continue
        if group["forward_return"].nunique(dropna=True) < 2:
            continue
        corr_value = group["factor_value"].corr(group["forward_return"])
        if corr_value == corr_value:
            daily_ic_values.append(float(corr_value))

    rank_ic_mean = (
        sum(daily_ic_values) / len(daily_ic_values) if daily_ic_values else None
    )
    rows = [
        {
            "trade_date": item["trade_date"].isoformat(),
            "symbol": str(item["symbol"]),
            "factor_value": float(item["factor_value"]),
        }
        for item in ranked[["trade_date", "symbol", "factor_value"]].to_dict("records")
    ]
    return {
        "status": "loaded",
        "reason": "feature_snapshot_factor_values_loaded",
        "source": source,
        "rows": rows,
        "metrics": {
            "rank_ic_mean": rank_ic_mean,
            "coverage_days": len(daily_ic_values),
            "total_stock_count": int(ranked["symbol"].nunique()),
            "inserted_values": len(rows),
        },
    }


def _safe_table_name(name: str) -> str:
    return safe_local_market_table_name(name)


async def _complete_factor_run_from_ohlcv_frame(
    session,
    *,
    tenant_id: str,
    user_id: str,
    run_row: Any,
    run_id: str,
    expression: str,
    holding_period: int,
    frame: Any,
    source: str,
    source_metrics: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    factor_data = _calculate_feature_snapshot_factor_values(
        frame=frame,
        expression=expression,
        holding_period=holding_period,
        source=source,
    )
    if factor_data.get("status") != "loaded" or not factor_data.get("rows"):
        return None
    source_metrics = source_metrics or {}

    upsert_metrics = await upsert_factor_values(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        candidate_id=run_row["factor_candidate_id"],
        run_id=run_id,
        rows=factor_data["rows"],
        source=factor_data["source"],
    )
    metrics_values = factor_data["metrics"]
    inserted_values = int(upsert_metrics.get("inserted_values") or 0)
    if inserted_values <= 0:
        return None
    metrics = QuantGPTCandidateMetrics(
        score=None,
        grade=None,
        rank_ic_mean=_float_or_none(metrics_values.get("rank_ic_mean")),
        ic_ir=None,
        turnover=None,
        wq_fitness=None,
        monotonicity_score=None,
        anti_overfit_score=None,
        coverage_days=int(metrics_values.get("coverage_days") or 0),
        total_stock_count=int(metrics_values.get("total_stock_count") or 0),
        raw={
            "source": factor_data["source"],
            "inserted_values": inserted_values,
            "invalid_symbol_count": int(
                upsert_metrics.get("invalid_symbol_count") or 0
            ),
            **source_metrics,
        },
    )
    decision = evaluate_promotion_eligibility(metrics)
    metrics_json = {
        "rank_ic_mean": metrics.rank_ic_mean,
        "coverage_days": metrics.coverage_days,
        "total_stock_count": metrics.total_stock_count,
        "source": factor_data["source"],
        "inserted_values": inserted_values,
        "invalid_symbol_count": int(upsert_metrics.get("invalid_symbol_count") or 0),
        **source_metrics,
    }
    gate_decision = {
        "eligible": decision.eligible,
        "reasons": decision.reasons,
        "policy": "default",
    }
    await session.execute(
        text(
            """
            UPDATE qm_factor_candidate_runs
            SET status = 'completed',
                metrics_json = CAST(:metrics_json AS JSONB),
                gate_decision_json = CAST(:gate_decision_json AS JSONB),
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
            """
        ),
        {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "metrics_json": _json(metrics_json),
            "gate_decision_json": _json(gate_decision),
        },
    )
    await session.execute(
        text(
            """
            UPDATE qm_factor_candidates
            SET status = CASE WHEN :eligible THEN 'validated' ELSE 'rejected' END,
                updated_at = NOW()
            WHERE id = :candidate_id AND tenant_id = :tenant_id AND user_id = :user_id
            """
        ),
        {
            "candidate_id": run_row["factor_candidate_id"],
            "tenant_id": tenant_id,
            "user_id": user_id,
            "eligible": decision.eligible,
        },
    )
    return await _get_run_in_session(session, tenant_id, user_id, run_id)


async def _complete_factor_run_from_feature_snapshot(
    session,
    *,
    tenant_id: str,
    user_id: str,
    run_row: Any,
    run_id: str,
    expression: str,
    start_date: date,
    end_date: date,
    holding_period: int,
) -> dict[str, Any] | None:
    snapshot_data = _load_feature_snapshot_ohlcv_frame(start_date, end_date)
    if snapshot_data.get("status") != "loaded":
        return None
    return await _complete_factor_run_from_ohlcv_frame(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_row=run_row,
        run_id=run_id,
        expression=expression,
        holding_period=holding_period,
        frame=snapshot_data["frame"],
        source=str(snapshot_data.get("source") or "feature_snapshot_parquet"),
        source_metrics={
            "snapshot_file_count": int(snapshot_data.get("file_count") or 0)
        },
    )


async def _complete_factor_run_from_qlib_provider(
    session,
    *,
    tenant_id: str,
    user_id: str,
    run_row: Any,
    run_id: str,
    expression: str,
    start_date: date,
    end_date: date,
    holding_period: int,
) -> dict[str, Any] | None:
    qlib_data = _load_qlib_ohlcv_frame(start_date, end_date)
    if qlib_data.get("status") != "loaded":
        return None
    return await _complete_factor_run_from_ohlcv_frame(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_row=run_row,
        run_id=run_id,
        expression=expression,
        holding_period=holding_period,
        frame=qlib_data["frame"],
        source=str(qlib_data.get("source") or "qlib_provider"),
        source_metrics={
            "qlib_instrument_count": int(qlib_data.get("instrument_count") or 0),
            "qlib_row_count": int(qlib_data.get("row_count") or 0),
        },
    )


async def evaluate_factor_run_locally(
    tenant_id: str, user_id: str, run_id: str
) -> dict[str, Any]:
    async with get_session() as session:
        run_row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                        r.*,
                        c.expression,
                        c.id AS factor_candidate_id
                    FROM qm_factor_candidate_runs r
                    JOIN qm_factor_candidates c ON c.id = r.candidate_id
                    WHERE r.id = :run_id AND r.tenant_id = :tenant_id AND r.user_id = :user_id
                    """
                    ),
                    {"run_id": run_id, "tenant_id": tenant_id, "user_id": user_id},
                )
            )
            .mappings()
            .first()
        )
        if not run_row:
            raise LookupError("factor evaluation run not found")

        params = run_row.get("params_json") or {}
        expression = str(run_row.get("expression") or "")
        raw_value_sql = _factor_raw_value_sql(expression)
        if raw_value_sql is None:
            await _mark_run_failed(
                session,
                run_id,
                tenant_id,
                user_id,
                "unsupported_expression",
                {
                    "eligible": False,
                    "reasons": ["unsupported_expression"],
                    "policy": "default",
                },
            )
            return await _get_run_in_session(session, tenant_id, user_id, run_id)

        start_date = _date_or_none(params.get("start_date"))
        end_date = _date_or_none(params.get("end_date"))
        if start_date is None or end_date is None:
            await _mark_run_failed(
                session,
                run_id,
                tenant_id,
                user_id,
                "invalid_date_range",
                {
                    "eligible": False,
                    "reasons": ["invalid_date_range"],
                    "policy": "default",
                },
            )
            return await _get_run_in_session(session, tenant_id, user_id, run_id)
        holding_period = int(params.get("holding_period") or 5)

        table = _safe_table_name(
            os.getenv("FACTOR_RESEARCH_DATA_TABLE", "stock_daily_latest")
        )
        data_contract = local_market_data_contract(table)
        table_exists = (
            await session.execute(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table}"},
            )
        ).scalar_one()

        await session.execute(
            text(
                """
                UPDATE qm_factor_candidate_runs
                SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
                WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"run_id": run_id, "tenant_id": tenant_id, "user_id": user_id},
        )
        if not table_exists:
            snapshot_result = await _complete_factor_run_from_feature_snapshot(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                run_row=run_row,
                run_id=run_id,
                expression=expression,
                start_date=start_date,
                end_date=end_date,
                holding_period=holding_period,
            )
            if snapshot_result is not None:
                return snapshot_result
            qlib_result = await _complete_factor_run_from_qlib_provider(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                run_row=run_row,
                run_id=run_id,
                expression=expression,
                start_date=start_date,
                end_date=end_date,
                holding_period=holding_period,
            )
            if qlib_result is not None:
                return qlib_result
            await _mark_run_failed(
                session,
                run_id,
                tenant_id,
                user_id,
                f"data_table_missing:{table}",
                {
                    "eligible": False,
                    "reasons": ["data_table_missing"],
                    "policy": "default",
                },
            )
            return await _get_run_in_session(session, tenant_id, user_id, run_id)

        values_cte = _build_factor_values_cte(table, raw_value_sql)
        upsert_metrics = await upsert_factor_values_from_select(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            candidate_id=run_row["factor_candidate_id"],
            run_id=run_id,
            values_select_sql=values_cte
            + """
            SELECT trade_date, symbol, factor_value
            FROM ranked
            """,
            values_params={
                "start_date": start_date,
                "end_date": end_date,
                "holding_period": holding_period,
            },
            source=data_contract.source,
        )
        inserted = int(upsert_metrics.get("inserted_values") or 0)
        if inserted <= 0:
            await _mark_run_failed(
                session,
                run_id,
                tenant_id,
                user_id,
                "no_factor_values_generated",
                {
                    "eligible": False,
                    "reasons": ["no_factor_values_generated"],
                    "policy": "default",
                },
            )
            return await _get_run_in_session(session, tenant_id, user_id, run_id)

        metrics_result = await session.execute(
            text(
                values_cte
                + """
                , daily_ic AS (
                    SELECT trade_date, corr(factor_value, forward_return) AS rank_ic
                    FROM ranked
                    GROUP BY trade_date
                    HAVING COUNT(*) >= 5
                )
                SELECT
                    AVG(rank_ic) AS rank_ic_mean,
                    COUNT(rank_ic) AS coverage_days,
                    (SELECT COUNT(DISTINCT symbol) FROM ranked) AS total_stock_count
                FROM daily_ic
                """
            ),
            {
                "start_date": start_date,
                "end_date": end_date,
                "holding_period": holding_period,
            },
        )
        metrics_row = metrics_result.mappings().one()
        metrics = QuantGPTCandidateMetrics(
            score=None,
            grade=None,
            rank_ic_mean=_float_or_none(metrics_row.get("rank_ic_mean")),
            ic_ir=None,
            turnover=None,
            wq_fitness=None,
            monotonicity_score=None,
            anti_overfit_score=None,
            coverage_days=int(metrics_row.get("coverage_days") or 0),
            total_stock_count=int(metrics_row.get("total_stock_count") or 0),
            raw={
                "source": data_contract.source,
                "inserted_values": inserted,
                "invalid_symbol_count": int(
                    upsert_metrics.get("invalid_symbol_count") or 0
                ),
            },
        )
        decision = evaluate_promotion_eligibility(metrics)
        metrics_json = {
            "rank_ic_mean": metrics.rank_ic_mean,
            "coverage_days": metrics.coverage_days,
            "total_stock_count": metrics.total_stock_count,
            "source": data_contract.source,
            "inserted_values": inserted,
            "invalid_symbol_count": int(
                upsert_metrics.get("invalid_symbol_count") or 0
            ),
        }
        gate_decision = {
            "eligible": decision.eligible,
            "reasons": decision.reasons,
            "policy": "default",
        }
        await session.execute(
            text(
                """
                UPDATE qm_factor_candidate_runs
                SET status = 'completed',
                    metrics_json = CAST(:metrics_json AS JSONB),
                    gate_decision_json = CAST(:gate_decision_json AS JSONB),
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {
                "run_id": run_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "metrics_json": _json(metrics_json),
                "gate_decision_json": _json(gate_decision),
            },
        )
        await session.execute(
            text(
                """
                UPDATE qm_factor_candidates
                SET status = CASE WHEN :eligible THEN 'validated' ELSE 'rejected' END,
                    updated_at = NOW()
                WHERE id = :candidate_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {
                "candidate_id": run_row["factor_candidate_id"],
                "tenant_id": tenant_id,
                "user_id": user_id,
                "eligible": decision.eligible,
            },
        )
        return await _get_run_in_session(session, tenant_id, user_id, run_id)


def _build_factor_values_cte(table: str, raw_value_sql: str) -> str:
    return build_local_factor_values_cte(table, raw_value_sql)


async def _mark_run_failed(
    session,
    run_id: str,
    tenant_id: str,
    user_id: str,
    error_message: str,
    gate_decision: dict[str, Any],
) -> None:
    await session.execute(
        text(
            """
            UPDATE qm_factor_candidate_runs
            SET status = 'failed',
                error_message = :error_message,
                gate_decision_json = CAST(:gate_decision_json AS JSONB),
                completed_at = NOW(),
                updated_at = NOW()
            WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
            """
        ),
        {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "error_message": error_message,
            "gate_decision_json": _json(gate_decision),
        },
    )
    await session.execute(
        text(
            """
            UPDATE qm_factor_candidates c
            SET status = 'rejected', updated_at = NOW()
            FROM qm_factor_candidate_runs r
            WHERE r.candidate_id = c.id
              AND r.id = :run_id
              AND r.tenant_id = :tenant_id
              AND r.user_id = :user_id
              AND c.tenant_id = :tenant_id
              AND c.user_id = :user_id
            """
        ),
        {"run_id": run_id, "tenant_id": tenant_id, "user_id": user_id},
    )


async def _get_run_in_session(
    session, tenant_id: str, user_id: str, run_id: str
) -> dict[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT *
                FROM qm_factor_candidate_runs
                WHERE id = :run_id AND tenant_id = :tenant_id AND user_id = :user_id
                """
                ),
                {"run_id": run_id, "tenant_id": tenant_id, "user_id": user_id},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise LookupError("factor evaluation run not found")
    return _row_to_run(row)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
