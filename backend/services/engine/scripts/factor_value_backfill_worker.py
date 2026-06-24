from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.api.routers.research_factor_service import (  # noqa: E402
    ensure_research_factor_tables,
)
from backend.services.engine.research.factor_value_backfill import (  # noqa: E402
    claim_next_pending_factor_value_backfill_job,
    execute_claimed_factor_value_backfill_job,
    record_factor_value_backfill_event,
)

logger = logging.getLogger(__name__)


async def _record_worker_event_safe(
    event_type: str,
    *,
    job: dict[str, Any] | None = None,
    worker_id: str | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> None:
    try:
        await record_factor_value_backfill_event(
            event_type=event_type,
            job_id=str(job.get("id")) if job and job.get("id") else None,
            tenant_id=(
                str(job.get("tenantId") or job.get("tenant_id"))
                if job and (job.get("tenantId") or job.get("tenant_id"))
                else None
            ),
            user_id=(
                str(job.get("userId") or job.get("user_id"))
                if job and (job.get("userId") or job.get("user_id"))
                else None
            ),
            worker_id=worker_id,
            status=status,
            details=details or {},
        )
    except Exception:
        logger.debug("Failed to record factor value backfill worker event", exc_info=True)


async def run_worker(
    *,
    once: bool,
    poll_interval: float,
    idle_limit: int | None,
    worker_id: str,
    max_claims: int | None,
    heartbeat_interval: float | None,
    lease_seconds: int | None,
) -> int:
    await ensure_research_factor_tables()
    processed = 0
    idle_count = 0
    last_heartbeat_at = 0.0
    effective_max_claims = 1 if once else max_claims
    await _record_worker_event_safe(
        "worker_started",
        worker_id=worker_id,
        details={
            "once": once,
            "pollInterval": poll_interval,
            "idleLimit": idle_limit,
            "maxClaims": effective_max_claims,
            "heartbeatInterval": heartbeat_interval,
            "leaseSeconds": lease_seconds,
        },
    )
    while True:
        if heartbeat_interval and time.monotonic() - last_heartbeat_at >= max(
            1.0, heartbeat_interval
        ):
            last_heartbeat_at = time.monotonic()
            await _record_worker_event_safe(
                "worker_heartbeat",
                worker_id=worker_id,
                details={"processed": processed, "maxClaims": effective_max_claims},
            )
        if effective_max_claims is not None and processed >= effective_max_claims:
            await _record_worker_event_safe(
                "worker_stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "max_claims_reached"},
            )
            return processed
        started_at = time.monotonic()
        job = await claim_next_pending_factor_value_backfill_job(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if job:
            try:
                completed = await execute_claimed_factor_value_backfill_job(
                    job,
                    worker_id=worker_id,
                )
            except Exception as exc:
                await _record_worker_event_safe(
                    "worker_failed",
                    job=job,
                    worker_id=worker_id,
                    status="failed",
                    details={"error": str(exc)},
                )
                raise
            duration_ms = int((time.monotonic() - started_at) * 1000)
            processed += 1
            idle_count = 0
            await _record_worker_event_safe(
                "worker_processed",
                job=completed,
                worker_id=worker_id,
                status=str(completed.get("status") or "completed"),
                details={
                    "durationMs": duration_ms,
                    "resolvedRuns": (completed.get("result") or {}).get("resolvedRuns"),
                    "processedRuns": (completed.get("result") or {}).get("processedRuns"),
                },
            )
            print(
                json.dumps(
                    {
                        "event": "factor_value_backfill_completed",
                        "job_id": completed.get("id"),
                        "status": completed.get("status"),
                        "resolved_runs": (completed.get("result") or {}).get(
                            "resolvedRuns"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            if once:
                await _record_worker_event_safe(
                    "worker_stopped",
                    worker_id=worker_id,
                    details={"processed": processed, "reason": "once_processed"},
                )
                return processed
            continue

        if once:
            await _record_worker_event_safe(
                "worker_idle",
                worker_id=worker_id,
                details={"processed": processed},
            )
            print(
                json.dumps(
                    {"event": "factor_value_backfill_idle", "processed": processed},
                    ensure_ascii=False,
                )
            )
            await _record_worker_event_safe(
                "worker_stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "once_idle"},
            )
            return processed

        idle_count += 1
        if idle_limit is not None and idle_count >= idle_limit:
            await _record_worker_event_safe(
                "worker_stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "idle_limit"},
            )
            return processed
        await asyncio.sleep(max(0.1, poll_interval))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pending factor value backfill worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument(
        "--worker-id",
        default=os.getenv(
            "QUANTMIND_FACTOR_VALUE_BACKFILL_WORKER_ID",
            f"factor-value-backfill-worker-{os.getpid()}-{uuid.uuid4().hex[:8]}",
        ),
        help="Stable worker identity recorded in backfill events",
    )
    parser.add_argument("--max-claims", type=int, default=None)
    parser.add_argument("--heartbeat-interval", type=float, default=30.0)
    parser.add_argument("--lease-seconds", type=int, default=None)
    parser.add_argument("--idle-limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run_worker(
            once=bool(args.once),
            poll_interval=float(args.poll_interval),
            idle_limit=args.idle_limit,
            worker_id=str(args.worker_id),
            max_claims=args.max_claims,
            heartbeat_interval=(
                float(args.heartbeat_interval)
                if float(args.heartbeat_interval or 0) > 0
                else None
            ),
            lease_seconds=args.lease_seconds,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
