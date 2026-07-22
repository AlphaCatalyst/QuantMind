#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.parameter_optimization_ablation.engine import (
    execute_study, inspect_study, plan_study, replay_study,
)


COMMANDS = (
    "validate-spec", "plan", "execute-factor-ablation", "execute-strategy-ablation",
    "execute-combined-ablation", "validate-study", "inspect-trials",
    "inspect-rank-stability", "inspect-generalization-gap", "inspect-assessment",
)
INSPECT_KINDS = {
    "inspect-trials": None,
    "inspect-rank-stability": "optimization_trial_rank_stability",
    "inspect-generalization-gap": "optimization_overfit_assessment",
    "inspect-assessment": "optimization_overfit_assessment",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Factor and strategy optimization overfit ablation v1")
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-005"))
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args(argv)
    try:
        if args.command in {"validate-spec", "plan"}:
            result = plan_study(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command.startswith("execute-"):
            # The three layers are one immutable study and publish atomically. Repeating any
            # layer command therefore performs an exact Store-backed replay after first publish.
            result = execute_study(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-study":
            result = replay_study(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            result = inspect_study(repository_root=ROOT, work_root=args.work_root,
                                   store_root=args.store_root, artifact_kind=INSPECT_KINDS[args.command])
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
