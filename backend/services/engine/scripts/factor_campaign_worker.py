from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.engine.research.factor_campaign_service import (  # noqa: E402
    claim_next_pending_factor_campaign,
    ensure_factor_campaign_tables,
    record_factor_campaign_worker_event,
    recover_stale_running_factor_campaigns,
)

logger = logging.getLogger(__name__)


async def _record_worker_event_safe(
    event_type: str,
    *,
    campaign: dict[str, Any] | None = None,
    worker_id: str | None = None,
    attempt_no: int | None = None,
    duration_ms: int | None = None,
    heartbeat_at: datetime | None = None,
    status: str = "ok",
    details: dict[str, Any] | None = None,
) -> None:
    try:
        await record_factor_campaign_worker_event(
            event_type=event_type,
            campaign_id=str(campaign.get("id"))
            if campaign and campaign.get("id")
            else None,
            tenant_id=(
                str(campaign.get("tenantId") or campaign.get("tenant_id"))
                if campaign and (campaign.get("tenantId") or campaign.get("tenant_id"))
                else None
            ),
            user_id=(
                str(campaign.get("userId") or campaign.get("user_id"))
                if campaign and (campaign.get("userId") or campaign.get("user_id"))
                else None
            ),
            worker_id=worker_id,
            attempt_no=attempt_no,
            duration_ms=duration_ms,
            heartbeat_at=heartbeat_at,
            status=status,
            details=details or {},
        )
    except Exception:
        logger.debug("Failed to record factor campaign worker event", exc_info=True)


async def run_worker(
    *,
    once: bool,
    poll_interval: float,
    idle_limit: int | None,
    recover_stale_after_minutes: int | None,
    worker_id: str,
    max_claims: int | None,
    concurrency: int,
    heartbeat_interval: float | None,
    lease_seconds: int | None,
) -> int:
    await ensure_factor_campaign_tables()
    processed = 0
    idle_count = 0
    attempt_no = 0
    last_heartbeat_at = 0.0
    effective_max_claims = 1 if once else max_claims
    await _record_worker_event_safe(
        "started",
        worker_id=worker_id,
        details={
            "once": once,
            "pollInterval": poll_interval,
            "idleLimit": idle_limit,
            "recoverStaleAfterMinutes": recover_stale_after_minutes,
            "maxClaims": effective_max_claims,
            "concurrency": max(1, int(concurrency or 1)),
            "heartbeatInterval": heartbeat_interval,
            "leaseSeconds": lease_seconds,
        },
    )
    while True:
        recovered = await recover_stale_running_factor_campaigns(
            stale_after_minutes=recover_stale_after_minutes,
            worker_id=worker_id,
        )
        if recovered:
            await _record_worker_event_safe(
                "recovered",
                worker_id=worker_id,
                details={
                    "count": recovered,
                    "staleAfterMinutes": recover_stale_after_minutes,
                },
            )
            print(
                json.dumps(
                    {"event": "factor_campaign_recovered", "count": recovered},
                    ensure_ascii=False,
                )
            )
        if heartbeat_interval and time.monotonic() - last_heartbeat_at >= max(
            1.0, heartbeat_interval
        ):
            last_heartbeat_at = time.monotonic()
            await _record_worker_event_safe(
                "heartbeat",
                worker_id=worker_id,
                heartbeat_at=datetime.now(timezone.utc),
                details={
                    "processed": processed,
                    "concurrency": max(1, concurrency),
                    "maxClaims": effective_max_claims,
                },
            )
        if effective_max_claims is not None and processed >= effective_max_claims:
            await _record_worker_event_safe(
                "stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "max_claims_reached"},
            )
            return processed
        claim_slots = max(1, int(concurrency or 1))
        if effective_max_claims is not None:
            claim_slots = min(claim_slots, effective_max_claims - processed)
        claim_slots = max(1, claim_slots)
        try:
            tasks = []
            task_attempts: list[int] = []
            for _ in range(claim_slots):
                attempt_no += 1
                task_attempts.append(attempt_no)
                tasks.append(
                    _claim_one_campaign(
                        worker_id=worker_id,
                        lease_seconds=lease_seconds,
                    )
                )
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as exc:
            await _record_worker_event_safe(
                "failed",
                worker_id=worker_id,
                status="failed",
                details={"error": str(exc)},
            )
            raise
        claimed_any = False
        for task_attempt_no, result in zip(task_attempts, results, strict=True):
            if isinstance(result, Exception):
                await _record_worker_event_safe(
                    "failed",
                    worker_id=worker_id,
                    attempt_no=task_attempt_no,
                    status="failed",
                    details={"error": str(result)},
                )
                raise result
            campaign, duration_ms = result
            if campaign is None:
                continue
            claimed_any = True
            processed += 1
            idle_count = 0
            await _record_worker_event_safe(
                "processed",
                campaign=campaign,
                worker_id=worker_id,
                attempt_no=task_attempt_no,
                duration_ms=duration_ms,
                status=str(campaign.get("status") or "completed"),
                details={
                    "completedRuns": (campaign.get("summary") or {}).get(
                        "completedRuns"
                    ),
                    "itemCount": len(campaign.get("items") or []),
                },
            )
            print(
                json.dumps(
                    {
                        "event": "factor_campaign_completed",
                        "campaign_id": campaign.get("id"),
                        "status": campaign.get("status"),
                        "completed_runs": (campaign.get("summary") or {}).get(
                            "completedRuns"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            if once:
                await _record_worker_event_safe(
                    "stopped",
                    worker_id=worker_id,
                    details={"processed": processed, "reason": "once_processed"},
                )
                return processed
        if claimed_any:
            continue

        if once:
            await _record_worker_event_safe(
                "idle",
                worker_id=worker_id,
                details={"processed": processed},
            )
            print(
                json.dumps(
                    {"event": "factor_campaign_idle", "processed": processed},
                    ensure_ascii=False,
                )
            )
            await _record_worker_event_safe(
                "stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "once_idle"},
            )
            return processed

        idle_count += 1
        if idle_limit is not None and idle_count >= idle_limit:
            await _record_worker_event_safe(
                "stopped",
                worker_id=worker_id,
                details={"processed": processed, "reason": "idle_limit"},
            )
            return processed
        await asyncio.sleep(max(0.1, poll_interval))


async def _claim_one_campaign(
    *,
    worker_id: str,
    lease_seconds: int | None,
) -> tuple[dict[str, Any] | None, int]:
    started_at = time.monotonic()
    campaign = await claim_next_pending_factor_campaign(
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return campaign, duration_ms


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pending factor campaign worker")
    parser.add_argument(
        "--once", action="store_true", help="Process at most one campaign"
    )
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument(
        "--worker-id",
        default=os.getenv(
            "QUANTMIND_FACTOR_CAMPAIGN_WORKER_ID",
            f"factor-campaign-worker-{os.getpid()}-{uuid.uuid4().hex[:8]}",
        ),
        help="Stable worker identity recorded in claim metadata and worker events",
    )
    parser.add_argument(
        "--max-claims",
        type=int,
        default=None,
        help="Exit after this many successfully claimed campaigns in loop mode",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of claim attempts to run concurrently per poll loop",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=float,
        default=30.0,
        help="Record a heartbeat event at most this often; set 0 to disable",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=None,
        help="Optional execution lease stored on claimed campaigns",
    )
    parser.add_argument(
        "--recover-stale-after-minutes",
        type=int,
        default=int(os.getenv("QUANTMIND_FACTOR_CAMPAIGN_STALE_RUNNING_MINUTES", "30")),
        help="Requeue running campaigns whose updated_at is older than this many minutes",
    )
    parser.add_argument(
        "--idle-limit",
        type=int,
        default=None,
        help="Exit after this many idle polls in loop mode",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    return asyncio.run(
        run_worker(
            once=bool(args.once),
            poll_interval=float(args.poll_interval),
            idle_limit=args.idle_limit,
            recover_stale_after_minutes=args.recover_stale_after_minutes,
            worker_id=str(args.worker_id),
            max_claims=args.max_claims,
            concurrency=max(1, int(args.concurrency or 1)),
            heartbeat_interval=(
                float(args.heartbeat_interval)
                if float(args.heartbeat_interval or 0) > 0
                else None
            ),
            lease_seconds=args.lease_seconds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
