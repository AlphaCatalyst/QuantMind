"""Engine-side factor value backfill orchestration."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from backend.shared.database_manager_v2 import get_session


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _unique(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _backfill_params(
    base: dict[str, Any] | None,
    *,
    start_date: str | None,
    end_date: str | None,
    universe: str | None,
    holding_period: int | None,
) -> dict[str, Any]:
    params = dict(base or {})
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    if universe is not None:
        params["universe"] = universe
    if holding_period is not None:
        params["holding_period"] = int(holding_period)
    params.setdefault("universe", "hs300")
    params.setdefault("n_groups", 5)
    params.setdefault("holding_period", 5)
    params.setdefault("neutralize_industry", True)
    params.setdefault("neutralize_cap", True)
    params["validation_profile"] = "factor_value_backfill"
    params["metadata"] = {
        **dict(params.get("metadata") or {}),
        "backfill": True,
    }
    return params


def _row_to_backfill_job(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "tenantId": data["tenant_id"],
        "userId": data["user_id"],
        "status": data.get("status") or "pending",
        "target": data.get("target_json") or {},
        "params": data.get("params_json") or {},
        "result": data.get("result_json"),
        "errorMessage": data.get("error_message"),
        "workerId": data.get("worker_id"),
        "startedAt": _iso(data.get("started_at")),
        "completedAt": _iso(data.get("completed_at")),
        "createdAt": _iso(data.get("created_at")),
        "updatedAt": _iso(data.get("updated_at")),
    }


def _row_to_backfill_event(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "jobId": data.get("job_id"),
        "tenantId": data.get("tenant_id"),
        "userId": data.get("user_id"),
        "workerId": data.get("worker_id"),
        "eventType": data.get("event_type"),
        "status": data.get("status") or "ok",
        "details": data.get("details_json") or {},
        "createdAt": _iso(data.get("created_at")),
    }


async def record_factor_value_backfill_event(
    *,
    event_type: str,
    job_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    worker_id: str | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> str:
    event_id = str(uuid.uuid4())
    async with get_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO qm_factor_value_backfill_events (
                    id, job_id, tenant_id, user_id, worker_id, event_type,
                    status, details_json, created_at
                )
                VALUES (
                    :id, :job_id, :tenant_id, :user_id, :worker_id,
                    :event_type, :status, CAST(:details_json AS JSONB), NOW()
                )
                """
            ),
            {
                "id": event_id,
                "job_id": job_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "worker_id": worker_id,
                "event_type": event_type,
                "status": status,
                "details_json": _json(details or {}),
            },
        )
    return event_id


async def list_factor_value_backfill_events(
    tenant_id: str,
    user_id: str,
    *,
    job_id: str | None = None,
    worker_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    filters = ["(tenant_id = :tenant_id OR tenant_id IS NULL)"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    filters.append("(user_id = :user_id OR user_id IS NULL)")
    if job_id:
        filters.append("job_id = :job_id")
        params["job_id"] = job_id
    if worker_id:
        filters.append("worker_id = :worker_id")
        params["worker_id"] = worker_id
    if event_type:
        filters.append("event_type = :event_type")
        params["event_type"] = event_type
    if status:
        filters.append("status = :status")
        params["status"] = status
    where_sql = " AND ".join(filters)
    async with get_session(read_only=True) as session:
        total = int(
            (
                await session.execute(
                    text(
                        f"""
                        SELECT COUNT(*) AS total
                        FROM qm_factor_value_backfill_events
                        WHERE {where_sql}
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM qm_factor_value_backfill_events
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
    return {
        "items": [_row_to_backfill_event(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def create_factor_value_backfill_job(
    tenant_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run_ids = _unique(payload.get("run_ids") or payload.get("runIds") or [])
    candidate_ids = _unique(
        payload.get("candidate_ids") or payload.get("candidateIds") or []
    )
    promotion_ids = _unique(
        payload.get("promotion_ids") or payload.get("promotionIds") or []
    )
    if not any((run_ids, candidate_ids, promotion_ids)):
        raise ValueError("at least one run, candidate, or promotion target is required")
    job_id = str(uuid.uuid4())
    target = {
        "runIds": run_ids,
        "candidateIds": candidate_ids,
        "promotionIds": promotion_ids,
    }
    params = {
        "startDate": payload.get("start_date") or payload.get("startDate"),
        "endDate": payload.get("end_date") or payload.get("endDate"),
        "universe": payload.get("universe"),
        "holdingPeriod": payload.get("holding_period")
        or payload.get("holdingPeriod"),
        "dryRun": bool(payload.get("dry_run") or payload.get("dryRun") or False),
        "maxRuns": max(1, min(int(payload.get("max_runs") or 50), 500)),
        "metadata": payload.get("metadata") or {},
    }
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        INSERT INTO qm_factor_value_backfill_jobs (
                            id, tenant_id, user_id, status, target_json,
                            params_json, created_at, updated_at
                        )
                        VALUES (
                            :id, :tenant_id, :user_id, 'pending',
                            CAST(:target_json AS JSONB),
                            CAST(:params_json AS JSONB), NOW(), NOW()
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "id": job_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "target_json": _json(target),
                        "params_json": _json(params),
                    },
                )
            )
            .mappings()
            .one()
        )
    return _row_to_backfill_job(row)


async def list_factor_value_backfill_jobs(
    tenant_id: str,
    user_id: str,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    filters = ["tenant_id = :tenant_id", "user_id = :user_id"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }
    if status:
        filters.append("status = :status")
        params["status"] = status
    where_sql = " AND ".join(filters)
    async with get_session(read_only=True) as session:
        total = int(
            (
                await session.execute(
                    text(
                        f"""
                        SELECT COUNT(*) AS total
                        FROM qm_factor_value_backfill_jobs
                        WHERE {where_sql}
                        """
                    ),
                    params,
                )
            ).scalar_one()
            or 0
        )
        rows = (
            (
                await session.execute(
                    text(
                        f"""
                        SELECT *
                        FROM qm_factor_value_backfill_jobs
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
    return {
        "items": [_row_to_backfill_job(row) for row in rows],
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(rows),
            "hasMore": offset + len(rows) < total,
        },
    }


async def cancel_factor_value_backfill_job(
    tenant_id: str,
    user_id: str,
    job_id: str,
    *,
    reason: str = "manual_cancel",
) -> dict[str, Any]:
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        UPDATE qm_factor_value_backfill_jobs
                        SET status = 'cancelled',
                            error_message = :reason,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = :job_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND status IN ('pending', 'running')
                        RETURNING *
                        """
                    ),
                    {
                        "job_id": job_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "reason": reason,
                    },
                )
            )
            .mappings()
            .first()
        )
    if not row:
        raise LookupError("factor value backfill job not found or not cancellable")
    await record_factor_value_backfill_event(
        event_type="cancelled",
        job_id=job_id,
        tenant_id=tenant_id,
        user_id=user_id,
        status="cancelled",
        details={"reason": reason},
    )
    return _row_to_backfill_job(row)


async def claim_next_pending_factor_value_backfill_job(
    *,
    worker_id: str,
    lease_seconds: int | None = None,
) -> dict[str, Any] | None:
    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        WITH next_job AS (
                            SELECT id
                            FROM qm_factor_value_backfill_jobs
                            WHERE status = 'pending'
                            ORDER BY created_at ASC
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                        )
                        UPDATE qm_factor_value_backfill_jobs j
                        SET status = 'running',
                            worker_id = :worker_id,
                            started_at = COALESCE(j.started_at, NOW()),
                            updated_at = NOW(),
                            params_json = jsonb_set(
                                COALESCE(j.params_json, '{}'::jsonb),
                                '{executionLease}',
                                CAST(:execution_lease_json AS JSONB),
                                true
                            )
                        FROM next_job
                        WHERE j.id = next_job.id
                        RETURNING j.*
                        """
                    ),
                    {
                        "worker_id": worker_id,
                        "execution_lease_json": _json(
                            {
                                "workerId": worker_id,
                                "leaseSeconds": lease_seconds,
                            }
                        ),
                    },
                )
            )
            .mappings()
            .first()
        )
    if not row:
        return None
    job = _row_to_backfill_job(row)
    await record_factor_value_backfill_event(
        event_type="claimed",
        job_id=str(job["id"]),
        tenant_id=str(job["tenantId"]),
        user_id=str(job["userId"]),
        worker_id=worker_id,
        status="running",
        details={"leaseSeconds": lease_seconds},
    )
    return job


async def _create_backfill_run(
    session,
    *,
    tenant_id: str,
    user_id: str,
    candidate_id: str,
    params: dict[str, Any],
    source: str,
) -> str:
    run_id = str(uuid.uuid4())
    gate_decision = {
        "eligible": False,
        "reasons": ["backfill_pending"],
        "policy": "default",
    }
    metadata = dict(params.get("metadata") or {})
    metadata["backfillSource"] = source
    params = {**params, "metadata": metadata}
    await session.execute(
        text(
            """
            INSERT INTO qm_factor_candidate_runs (
                id, candidate_id, tenant_id, user_id, status, params_json,
                gate_decision_json, created_at, updated_at
            )
            VALUES (
                :id, :candidate_id, :tenant_id, :user_id, 'pending',
                CAST(:params_json AS JSONB), CAST(:gate_decision_json AS JSONB),
                NOW(), NOW()
            )
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
    return run_id


async def _resolve_existing_run_targets(
    session,
    *,
    tenant_id: str,
    user_id: str,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    if not run_ids:
        return []
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT id, candidate_id, params_json
                    FROM qm_factor_candidate_runs
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND id = ANY(:run_ids)
                    ORDER BY created_at ASC
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "run_ids": run_ids},
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "run_id": str(row["id"]),
            "candidate_id": str(row["candidate_id"]),
            "params": dict(row.get("params_json") or {}),
            "source": "run",
            "created": False,
        }
        for row in rows
    ]


async def _resolve_candidate_targets(
    session,
    *,
    tenant_id: str,
    user_id: str,
    candidate_ids: list[str],
    start_date: str | None,
    end_date: str | None,
    universe: str | None,
    holding_period: int | None,
    dry_run: bool,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        candidate = (
            (
                await session.execute(
                    text(
                        """
                        SELECT id
                        FROM qm_factor_candidates
                        WHERE id = :candidate_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        """
                    ),
                    {
                        "candidate_id": candidate_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if not candidate:
            continue
        latest_run = (
            (
                await session.execute(
                    text(
                        """
                        SELECT id, params_json
                        FROM qm_factor_candidate_runs
                        WHERE candidate_id = :candidate_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "candidate_id": candidate_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        params = _backfill_params(
            latest_run.get("params_json") if latest_run else None,
            start_date=start_date,
            end_date=end_date,
            universe=universe,
            holding_period=holding_period,
        )
        if not params.get("start_date") or not params.get("end_date"):
            continue
        run_id = (
            f"planned-candidate-{candidate_id}"
            if dry_run
            else await _create_backfill_run(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                candidate_id=candidate_id,
                params=params,
                source="candidate",
            )
        )
        targets.append(
            {
                "run_id": run_id,
                "candidate_id": candidate_id,
                "params": params,
                "source": "candidate",
                "created": True,
            }
        )
    return targets


async def _resolve_promotion_targets(
    session,
    *,
    tenant_id: str,
    user_id: str,
    promotion_ids: list[str],
    start_date: str | None,
    end_date: str | None,
    universe: str | None,
    holding_period: int | None,
    dry_run: bool,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for promotion_id in promotion_ids:
        promotion = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            p.id,
                            p.candidate_id,
                            p.run_id,
                            r.params_json
                        FROM qm_factor_feature_promotions p
                        LEFT JOIN qm_factor_candidate_runs r
                          ON r.id = p.run_id
                         AND r.tenant_id = p.tenant_id
                         AND r.user_id = p.user_id
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
        if not promotion:
            continue
        has_overrides = any(
            value is not None for value in (start_date, end_date, universe, holding_period)
        )
        if not has_overrides and promotion.get("run_id"):
            targets.append(
                {
                    "run_id": str(promotion["run_id"]),
                    "candidate_id": str(promotion["candidate_id"]),
                    "params": dict(promotion.get("params_json") or {}),
                    "source": "promotion",
                    "created": False,
                }
            )
            continue
        params = _backfill_params(
            promotion.get("params_json"),
            start_date=start_date,
            end_date=end_date,
            universe=universe,
            holding_period=holding_period,
        )
        if not params.get("start_date") or not params.get("end_date"):
            continue
        run_id = (
            f"planned-promotion-{promotion_id}"
            if dry_run
            else await _create_backfill_run(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                candidate_id=str(promotion["candidate_id"]),
                params=params,
                source="promotion",
            )
        )
        targets.append(
            {
                "run_id": run_id,
                "candidate_id": str(promotion["candidate_id"]),
                "params": params,
                "source": "promotion",
                "created": True,
            }
        )
    return targets


async def run_factor_value_backfill(
    *,
    tenant_id: str,
    user_id: str,
    run_ids: list[str] | tuple[str, ...] | None = None,
    candidate_ids: list[str] | tuple[str, ...] | None = None,
    promotion_ids: list[str] | tuple[str, ...] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    universe: str | None = None,
    holding_period: int | None = None,
    dry_run: bool = False,
    max_runs: int = 50,
) -> dict[str, Any]:
    """Resolve targets and run factor value backfill jobs asynchronously."""
    run_ids = _unique(list(run_ids or []))
    candidate_ids = _unique(list(candidate_ids or []))
    promotion_ids = _unique(list(promotion_ids or []))
    if not any((run_ids, candidate_ids, promotion_ids)):
        raise ValueError("at least one run, candidate, or promotion target is required")

    async with get_session() as session:
        targets = []
        targets.extend(
            await _resolve_existing_run_targets(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                run_ids=run_ids,
            )
        )
        targets.extend(
            await _resolve_candidate_targets(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                candidate_ids=candidate_ids,
                start_date=start_date,
                end_date=end_date,
                universe=universe,
                holding_period=holding_period,
                dry_run=dry_run,
            )
        )
        targets.extend(
            await _resolve_promotion_targets(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                promotion_ids=promotion_ids,
                start_date=start_date,
                end_date=end_date,
                universe=universe,
                holding_period=holding_period,
                dry_run=dry_run,
            )
        )

    unique_targets: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    for target in targets:
        run_id = str(target["run_id"])
        if run_id in seen_runs:
            continue
        seen_runs.add(run_id)
        unique_targets.append(target)
        if len(unique_targets) >= max_runs:
            break

    if dry_run:
        return {
            "status": "planned",
            "requestedTargets": len(run_ids) + len(candidate_ids) + len(promotion_ids),
            "resolvedRuns": len(unique_targets),
            "processedRuns": 0,
            "runs": unique_targets,
        }

    from backend.services.api.routers.research_factor_service import (
        evaluate_factor_run_locally,
    )

    processed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for target in unique_targets:
        run_id = str(target["run_id"])
        try:
            run = await evaluate_factor_run_locally(tenant_id, user_id, run_id)
            processed.append({**target, "status": run.get("status"), "run": run})
        except Exception as exc:  # pragma: no cover - defensive worker boundary
            failed.append({**target, "status": "failed", "error": str(exc)})

    return {
        "status": "completed" if not failed else "partial_failed",
        "requestedTargets": len(run_ids) + len(candidate_ids) + len(promotion_ids),
        "resolvedRuns": len(unique_targets),
        "processedRuns": len(processed),
        "failedRuns": len(failed),
        "runs": processed + failed,
    }


async def execute_factor_value_backfill_job(
    tenant_id: str,
    user_id: str,
    job_id: str,
    *,
    worker_id: str | None = None,
) -> dict[str, Any]:
    async with get_session() as session:
        job = (
            (
                await session.execute(
                    text(
                        """
                        UPDATE qm_factor_value_backfill_jobs
                        SET status = 'running',
                            worker_id = :worker_id,
                            started_at = COALESCE(started_at, NOW()),
                            updated_at = NOW()
                        WHERE id = :job_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                          AND (
                                status IN ('pending', 'failed')
                             OR (status = 'running' AND worker_id = :worker_id)
                          )
                        RETURNING *
                        """
                    ),
                    {
                        "job_id": job_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "worker_id": worker_id,
                    },
                )
            )
            .mappings()
            .first()
        )
    if not job:
        raise LookupError("factor value backfill job not found or not runnable")

    return await _execute_factor_value_backfill_job_row(job, worker_id=worker_id)


async def execute_claimed_factor_value_backfill_job(
    job: dict[str, Any],
    *,
    worker_id: str | None = None,
) -> dict[str, Any]:
    return await _execute_factor_value_backfill_job_row(job, worker_id=worker_id)


async def _execute_factor_value_backfill_job_row(
    job: Any,
    *,
    worker_id: str | None = None,
) -> dict[str, Any]:
    target = dict(job.get("target_json") or job.get("target") or {})
    params = dict(job.get("params_json") or job.get("params") or {})
    job_id = str(job.get("id"))
    tenant_id = str(job.get("tenant_id") or job.get("tenantId"))
    user_id = str(job.get("user_id") or job.get("userId"))
    await record_factor_value_backfill_event(
        event_type="started",
        job_id=job_id,
        tenant_id=tenant_id,
        user_id=user_id,
        worker_id=worker_id,
        status="running",
        details={
            "target": target,
            "dryRun": bool(params.get("dryRun") or False),
            "maxRuns": params.get("maxRuns"),
        },
    )
    try:
        result = await run_factor_value_backfill(
            tenant_id=tenant_id,
            user_id=user_id,
            run_ids=target.get("runIds") or [],
            candidate_ids=target.get("candidateIds") or [],
            promotion_ids=target.get("promotionIds") or [],
            start_date=params.get("startDate"),
            end_date=params.get("endDate"),
            universe=params.get("universe"),
            holding_period=params.get("holdingPeriod"),
            dry_run=bool(params.get("dryRun") or False),
            max_runs=int(params.get("maxRuns") or 50),
        )
        status = "completed" if result.get("status") in {"planned", "completed"} else "failed"
        error_message = None
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        status = "failed"
        error_message = str(exc)

    async with get_session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                        UPDATE qm_factor_value_backfill_jobs
                        SET status = :status,
                            result_json = CAST(:result_json AS JSONB),
                            error_message = :error_message,
                            completed_at = NOW(),
                            updated_at = NOW()
                        WHERE id = :job_id
                          AND tenant_id = :tenant_id
                          AND user_id = :user_id
                        RETURNING *
                        """
                    ),
                    {
                        "job_id": job_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "status": status,
                        "result_json": _json(result),
                        "error_message": error_message,
                    },
                )
            )
            .mappings()
            .one()
        )
    await record_factor_value_backfill_event(
        event_type="completed" if status == "completed" else "failed",
        job_id=job_id,
        tenant_id=tenant_id,
        user_id=user_id,
        worker_id=worker_id,
        status=status,
        details={
            "resultStatus": result.get("status"),
            "resolvedRuns": result.get("resolvedRuns"),
            "processedRuns": result.get("processedRuns"),
            "failedRuns": result.get("failedRuns"),
            "error": error_message,
        },
    )
    return _row_to_backfill_job(row)
