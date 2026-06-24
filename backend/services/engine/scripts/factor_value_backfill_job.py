"""Run factor value backfill jobs from the engine container."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from backend.services.engine.research.factor_value_backfill import (
    run_factor_value_backfill,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run factor value backfill job")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--candidate-id", action="append", default=[])
    parser.add_argument("--promotion-id", action="append", default=[])
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--universe")
    parser.add_argument("--holding-period", type=int)
    parser.add_argument("--max-runs", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


async def _amain(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    return await run_factor_value_backfill(
        tenant_id=str(args.tenant_id),
        user_id=str(args.user_id),
        run_ids=list(args.run_id or []),
        candidate_ids=list(args.candidate_id or []),
        promotion_ids=list(args.promotion_id or []),
        start_date=args.start_date,
        end_date=args.end_date,
        universe=args.universe,
        holding_period=args.holding_period,
        dry_run=bool(args.dry_run),
        max_runs=max(1, int(args.max_runs or 50)),
    )


def main(argv: list[str] | None = None) -> int:
    result = asyncio.run(_amain(argv))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") in {"planned", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
