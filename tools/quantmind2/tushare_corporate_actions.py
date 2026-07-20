#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.corporate_actions.engine import (
    replay_corporate_action_audit,
    run_corporate_action_audit,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Tushare-only corporate-action evidence audit")
    sub = value.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--work-root", required=True, type=Path)
    run.add_argument("--store-root", type=Path)
    replay = sub.add_parser("replay")
    replay.add_argument("--raw-snapshot-id", required=True)
    replay.add_argument("--store-root", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "run":
        result = run_corporate_action_audit(
            work_root=args.work_root, store_root=args.store_root,
        )
    else:
        result = replay_corporate_action_audit(
            raw_snapshot_id=args.raw_snapshot_id, store_root=args.store_root,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 2 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
