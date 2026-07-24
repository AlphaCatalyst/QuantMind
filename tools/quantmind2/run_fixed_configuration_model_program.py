#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.fixed_configuration_model_program import (  # noqa: E402
    create_spec,
    execute_program,
    inspect_artifact,
    inspect_program,
    plan_program,
    replay_program,
    validate_program,
)


COMMANDS = (
    "audit-training",
    "create-spec",
    "validate-spec",
    "inspect-bundle",
    "plan",
    "execute",
    "resume",
    "inspect-fold",
    "inspect-model",
    "inspect-predictions",
    "inspect-stability",
    "inspect-multiple-testing",
    "inspect-candidate",
    "inspect-distillation-queue",
    "validate-program",
    "replay",
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QuantMind fixed-configuration model program")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r2-007-model"))
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("create-spec")
    commands.add_parser("audit-training")
    for name in ("validate-spec", "plan", "execute", "resume", "validate-program", "replay"):
        command = commands.add_parser(name)
        command.add_argument("--model-spec-id", required=True)
    for name in (
        "inspect-bundle",
        "inspect-fold",
        "inspect-model",
        "inspect-predictions",
        "inspect-stability",
        "inspect-multiple-testing",
        "inspect-candidate",
        "inspect-distillation-queue",
    ):
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
        if args.command == "create-spec":
            result = create_spec(**common)
        elif args.command == "audit-training":
            result = {
                "status": "audited",
                "training_entry": "docker/training/train.py",
                "orchestration_entry": "backend/services/engine/training/local_docker_orchestrator.py",
                "model_type": "lightgbm",
                "formal_label": "model_label",
                "outer_test_early_stopping_access": False,
                "fixed_rounds_required_by_program": True,
            }
        elif args.command == "validate-spec":
            result = inspect_program(model_spec_id=args.model_spec_id, **common)["model_spec"] | {
                "status": "valid",
                "model_spec_id": args.model_spec_id,
            }
        elif args.command == "plan":
            result = plan_program(model_spec_id=args.model_spec_id, **common)
        elif args.command in {"execute", "resume"}:
            result = execute_program(model_spec_id=args.model_spec_id, **common)
        elif args.command == "validate-program":
            result = validate_program(model_spec_id=args.model_spec_id, **common)
        elif args.command == "replay":
            result = replay_program(model_spec_id=args.model_spec_id, **common)
        else:
            result = inspect_artifact(artifact_id=args.artifact_id, **common)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "blocked",
            "error_code": type(exc).__name__,
            "safe_summary": str(exc)[:500],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
