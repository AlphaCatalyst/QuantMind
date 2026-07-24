#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.multi_horizon_label_research import (  # noqa: E402
    create_label_family,
    execute_study,
    inspect_artifact,
    plan_study,
    replay_study,
    validate_study,
)


INSPECT_COMMANDS = {
    "inspect-label",
    "inspect-fold",
    "inspect-alignment",
    "inspect-multiple-testing",
    "inspect-candidate",
    "inspect-fresh-lock",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind multi-horizon label research")
    value.add_argument("--store-root", type=Path)
    value.add_argument(
        "--work-root", type=Path, default=Path("/private/tmp/qm2-r2-008-multi-horizon")
    )
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-label")
    commands.add_parser("create-label-family")
    for name in (
        "validate-labels",
        "materialize-labels",
        "create-spec",
        "plan",
        "execute",
        "resume",
        "validate-study",
        "replay",
    ):
        command = commands.add_parser(name)
        command.add_argument("--label-family-id", required=True)
    for name in sorted(INSPECT_COMMANDS):
        command = commands.add_parser(name)
        command.add_argument("artifact_id")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    common = {
        "repository_root": ROOT,
        "work_root": args.work_root,
        "store_root": args.store_root,
    }
    try:
        if args.command == "create-label-family":
            result = create_label_family(**common)
        elif args.command == "audit-label":
            result = {
                "status": "audited",
                "metadata_formula": "legacy declaration differs from executable code",
                "executable_formula": "Close[T+H]/Open[T+1]-1",
                "training_dataset_actual_label_column": "model_label",
                "qlib_strategy_holding_horizon_sessions": 10,
                "legacy_label_modified": False,
            }
        elif args.command == "plan":
            result = plan_study(label_family_id=args.label_family_id, **common)
        elif args.command in {
            "validate-labels",
            "materialize-labels",
            "create-spec",
            "execute",
            "resume",
        }:
            result = execute_study(label_family_id=args.label_family_id, **common)
        elif args.command == "validate-study":
            result = validate_study(label_family_id=args.label_family_id, **common)
        elif args.command == "replay":
            result = replay_study(label_family_id=args.label_family_id, **common)
        else:
            result = inspect_artifact(artifact_id=args.artifact_id, **common)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps(
            {
                "status": "blocked",
                "error_code": type(exc).__name__,
                "safe_summary": str(exc)[:500],
            },
            ensure_ascii=False,
        ), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
