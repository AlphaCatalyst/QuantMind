#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.optimization_governance.engine import (
    execute_governance, plan_governance, replay_governance,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind default-first optimization governance v2")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-006"))
    value.add_argument("--factor-optimization-mode", default="default_first",
                       choices=("default_first", "local_only", "full_search_diagnostic"))
    value.add_argument("--strategy-optimization-mode", default="default_first",
                       choices=("default_first", "local_only", "full_search_diagnostic"))
    value.add_argument("--allow-full-factor-search-diagnostic", action="store_true")
    value.add_argument("--allow-full-strategy-search-diagnostic", action="store_true")
    value.add_argument("--factor-optimizable-parameter-count", type=int, default=1)
    value.add_argument("--default-factor-failed", action="store_true")
    value.add_argument("--default-strategy-failed", action="store_true")
    value.add_argument("command", choices=("plan", "publish", "validate", "recover", "replay"))
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_governance(
                factor_mode=args.factor_optimization_mode,
                strategy_mode=args.strategy_optimization_mode,
                factor_optimizable_parameter_count=args.factor_optimizable_parameter_count,
                allow_full_factor_search_diagnostic=args.allow_full_factor_search_diagnostic,
                allow_full_strategy_search_diagnostic=args.allow_full_strategy_search_diagnostic,
                default_factor_failed=args.default_factor_failed,
                default_strategy_failed=args.default_strategy_failed,
            )
        elif args.command == "publish":
            # Publication records governance only; it executes no optimization trial.
            plan_governance(
                factor_mode=args.factor_optimization_mode,
                strategy_mode=args.strategy_optimization_mode,
                factor_optimizable_parameter_count=args.factor_optimizable_parameter_count,
                allow_full_factor_search_diagnostic=args.allow_full_factor_search_diagnostic,
                allow_full_strategy_search_diagnostic=args.allow_full_strategy_search_diagnostic,
                default_factor_failed=args.default_factor_failed,
                default_strategy_failed=args.default_strategy_failed,
            )
            result = execute_governance(work_root=args.work_root, store_root=args.store_root)
        else:
            result = replay_governance(work_root=args.work_root, store_root=args.store_root)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": getattr(exc, "code", type(exc).__name__),
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
