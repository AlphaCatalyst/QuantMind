#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.tushare_agent_experiment import (  # noqa: E402
    replay_experiment,
    run_experiment,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QM2 Tushare Fixed-100 Agent experiment")
    value.add_argument("--work-root", required=True, type=Path)
    value.add_argument("--store-root", type=Path)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    commands.add_parser("replay")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "run":
            result = run_experiment(
                repository_root=ROOT,
                work_root=args.work_root,
                store_root=args.store_root,
            )
        else:
            result = replay_experiment(
                repository_root=ROOT,
                work_root=args.work_root,
                store_root=args.store_root,
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": type(exc).__name__,
            "safe_summary": str(exc)[:300],
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
