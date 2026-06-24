"""Engine-side factor campaign scheduling service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import text

from backend.services.api.routers.research_factor_service import (
    _campaign_stale_running_minutes,
    _campaign_evaluation_params,
    _campaign_generation_count,
    _campaign_payload_from_row,
    _campaign_requested_candidate_count,
    _generate_campaign_expression_specs,
    _json,
    _row_to_campaign_worker_event,
    _row_to_campaign,
    _run_campaign_expression,
    _summarize_campaign_items,
    ensure_research_factor_tables,
    factor_expression_key,
    get_factor_campaign,
    get_session,
)


async def ensure_factor_campaign_tables() -> None:
    await ensure_research_factor_tables()


async def claim_next_pending_factor_campaign(
    *,
    worker_id: str | None = None,
    lease_seconds: int | None = None,
) -> dict[str, Any] | None:
    """Claim and execute one pending factor campaign for engine workers."""
    normalized_worker_id = str(worker_id or "unknown").strip() or "unknown"
    normalized_lease_seconds = (
        max(1, int(lease_seconds)) if lease_seconds is not None else None
    )
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                WITH picked AS (
                    SELECT id
                    FROM qm_factor_campaigns
                    WHERE status = 'pending'
                      AND (
                        COALESCE(metadata_json->'workerPolicy'->>'workerId', '') = ''
                        OR metadata_json->'workerPolicy'->>'workerId' = :worker_id
                      )
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE qm_factor_campaigns c
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW(),
                    metadata_json = COALESCE(c.metadata_json, '{}'::jsonb)
                        || jsonb_build_object(
                            'currentWorkerId', CAST(:worker_id AS TEXT),
                            'attemptNo',
                                COALESCE((c.metadata_json->>'attemptNo')::integer, 0) + 1,
                            'lastClaimedAt', NOW()::text,
                            'executionLeaseSeconds', CAST(:lease_seconds AS INTEGER),
                            'executionLeaseExpiresAt',
                                CASE
                                    WHEN :lease_seconds IS NULL THEN NULL
                                    ELSE (
                                        NOW() + (:lease_seconds * INTERVAL '1 second')
                                    )::text
                                END
                        )
                FROM picked
                WHERE c.id = picked.id
                RETURNING c.*
                """
            ),
            {
                "worker_id": normalized_worker_id,
                "lease_seconds": normalized_lease_seconds,
            },
        )
        row = result.mappings().first()
    if not row:
        return None
    return await execute_claimed_factor_campaign(
        row,
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        campaign_id=str(row["id"]),
    )


async def execute_factor_campaign(
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    """Claim a specific pending campaign and execute it from engine context."""
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                UPDATE qm_factor_campaigns
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW()
                WHERE id = :campaign_id
                  AND tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND status = 'pending'
                RETURNING *
                """
            ),
            {
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )
        campaign = result.mappings().first()
    if not campaign:
        return await get_factor_campaign(tenant_id, user_id, campaign_id)

    return await execute_claimed_factor_campaign(
        campaign,
        tenant_id=tenant_id,
        user_id=user_id,
        campaign_id=campaign_id,
    )


async def execute_claimed_factor_campaign(
    campaign: Any,
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
) -> dict[str, Any]:
    payload = _campaign_payload_from_row(campaign)
    params = _campaign_evaluation_params(payload)
    candidates_per_generation = _campaign_requested_candidate_count(payload)
    max_generations = _campaign_generation_count(payload)
    initial_specs = _generate_campaign_expression_specs(
        payload,
        max_candidates=candidates_per_generation,
    )
    expressions = [str(spec.get("expression") or "") for spec in initial_specs]
    if not expressions:
        raise ValueError("campaign requires at least one supported seed expression")

    try:
        return await execute_factor_campaign_from_payload(
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
    except Exception as exc:
        summary = {"error": str(exc), "completedRuns": 0, "failedRuns": 1}
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE qm_factor_campaigns
                    SET status = 'failed',
                        summary_json = CAST(:summary_json AS JSONB),
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :campaign_id
                      AND tenant_id = :tenant_id
                      AND user_id = :user_id
                    """
                ),
                {
                    "campaign_id": campaign_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "summary_json": _json(summary),
                },
            )
        raise


async def execute_factor_campaign_from_payload(
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
    items: list[dict[str, Any]] = []
    used_expression_keys: set[str] = set()
    generation_payload = dict(payload)
    generation_specs = (
        initial_expression_specs
        if initial_expression_specs is not None
        else [
            {
                "expression": expression,
                "metadata": {
                    "strategy": str(payload.get("strategy") or "mutation_crossover"),
                    "operator": "seed",
                    "parentExpressions": [],
                },
            }
            for expression in initial_expressions
        ]
    )
    for generation in range(1, max_generations + 1):
        if generation > 1:
            generation_specs = _generate_campaign_expression_specs(
                generation_payload,
                max_candidates=candidates_per_generation,
                exclude_keys=used_expression_keys,
            )
        if not generation_specs:
            break
        generation_items: list[dict[str, Any]] = []
        generation_expressions = [
            str(spec.get("expression") or "") for spec in generation_specs
        ]
        for spec in generation_specs:
            expression = str(spec.get("expression") or "")
            used_expression_keys.add(factor_expression_key(expression))
            item = await _run_campaign_expression(
                tenant_id=tenant_id,
                user_id=user_id,
                campaign_id=campaign_id,
                generation=generation,
                rank_no=len(items) + 1,
                expression=expression,
                params=params,
                item_metadata=spec.get("metadata") if isinstance(spec, dict) else None,
            )
            items.append(item)
            generation_items.append(item)
        scored_generation = [
            item
            for item in generation_items
            if item.get("status") == "completed" and item.get("score") is not None
        ]
        scored_generation.sort(
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )
        next_seed = (
            scored_generation[0].get("expression")
            if scored_generation
            else generation_expressions[0]
        )
        iteration_history = [
            {
                "expression": item.get("expression"),
                "score": item.get("score"),
                "generation": item.get("generation"),
                "status": item.get("status"),
            }
            for item in items
            if item.get("expression")
        ]
        generation_payload = {
            **payload,
            "seed_expression": next_seed,
            "seed_expressions": [],
            "iteration_history": iteration_history,
        }

    summary = _summarize_campaign_items(items)
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                UPDATE qm_factor_campaigns
                SET status = :status,
                    summary_json = CAST(:summary_json AS JSONB),
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :campaign_id AND tenant_id = :tenant_id AND user_id = :user_id
                RETURNING *
                """
            ),
            {
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "status": "completed" if summary["completedRuns"] > 0 else "failed",
                "summary_json": _json(summary),
            },
        )
        campaign = result.mappings().one()
    return _row_to_campaign(campaign, items=items)


async def recover_stale_running_factor_campaigns(
    *,
    stale_after_minutes: int | None = None,
    worker_id: str | None = None,
) -> int:
    """Requeue stale running campaigns and retryable failed campaigns."""
    minutes = max(1, int(stale_after_minutes or _campaign_stale_running_minutes()))
    normalized_worker_id = str(worker_id).strip() if worker_id else None
    async with get_session() as session:
        result = await session.execute(
            text(
                """
                UPDATE qm_factor_campaigns
                SET status = 'pending',
                    updated_at = NOW(),
                    metadata_json = COALESCE(metadata_json, '{}'::jsonb)
                        || jsonb_build_object(
                            'lastRecoveryReason',
                                CASE
                                    WHEN status = 'failed'
                                        THEN 'failed_worker_retry_requeue'
                                    ELSE 'stale_running_worker_requeue'
                                END,
                            'lastRecoveredAt', NOW()::text,
                            'lastRecoveryWorkerId', CAST(:worker_id AS TEXT),
                            'recoveryCount',
                                COALESCE((metadata_json->>'recoveryCount')::integer, 0) + 1,
                            'lastRecoveredStatus', status
                        )
                WHERE (
                    status = 'running'
                    AND (
                        updated_at < NOW() - (:stale_after_minutes * INTERVAL '1 minute')
                        OR (
                            metadata_json ? 'executionLeaseExpiresAt'
                            AND (metadata_json->>'executionLeaseExpiresAt')::timestamptz < NOW()
                        )
                    )
                )
                OR (
                    status = 'failed'
                    AND COALESCE((metadata_json->>'attemptNo')::integer, 0)
                        < COALESCE((metadata_json->'retryPolicy'->>'maxAttempts')::integer, 1)
                    AND updated_at < NOW() - (
                        COALESCE(
                            (metadata_json->'retryPolicy'->>'retryFailedAfterMinutes')::integer,
                            :stale_after_minutes
                        ) * INTERVAL '1 minute'
                    )
                )
                RETURNING id
                """
            ),
            {"stale_after_minutes": minutes, "worker_id": normalized_worker_id},
        )
        rows = result.mappings().all()
    return len(rows)


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
    """Persist a factor campaign worker event for health checks and operations."""
    event_id = str(uuid.uuid4())
    event_type = str(event_type or "unknown").strip() or "unknown"
    status = str(status or "ok").strip() or "ok"
    normalized_worker_id = str(worker_id).strip() if worker_id else None
    normalized_attempt_no = int(attempt_no) if attempt_no is not None else None
    normalized_duration_ms = max(0, int(duration_ms)) if duration_ms is not None else None
    normalized_heartbeat_at = (
        heartbeat_at
        if heartbeat_at is not None
        else datetime.now(timezone.utc)
        if event_type == "heartbeat"
        else None
    )
    async with get_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO qm_factor_campaign_worker_events (
                    id, event_type, campaign_id, tenant_id, user_id, worker_id,
                    attempt_no, duration_ms, heartbeat_at, status, details_json,
                    created_at
                )
                VALUES (
                    :id, :event_type, :campaign_id, :tenant_id, :user_id, :worker_id,
                    :attempt_no, :duration_ms, :heartbeat_at, :status,
                    CAST(:details_json AS JSONB), NOW()
                )
                """
            ),
            {
                "id": event_id,
                "event_type": event_type,
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "worker_id": normalized_worker_id,
                "attempt_no": normalized_attempt_no,
                "duration_ms": normalized_duration_ms,
                "heartbeat_at": normalized_heartbeat_at,
                "status": status,
                "details_json": _json(details or {}),
            },
        )
    return event_id


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
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    params = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "worker_id": worker_id,
        "event_type": event_type,
        "status": status,
        "limit": limit,
        "offset": offset,
    }
    where = [
        "(tenant_id = :tenant_id OR tenant_id IS NULL)",
        "(user_id = :user_id OR user_id IS NULL)",
    ]
    if campaign_id:
        where.append("campaign_id = :campaign_id")
    if worker_id:
        where.append("worker_id = :worker_id")
    if event_type:
        where.append("event_type = :event_type")
    if status:
        where.append("status = :status")
    where_sql = " AND ".join(where)
    async with get_session(read_only=True) as session:
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM qm_factor_campaign_worker_events
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
                        FROM qm_factor_campaign_worker_events
                        WHERE {where_sql}
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
    return {
        "items": [_row_to_campaign_worker_event(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }
