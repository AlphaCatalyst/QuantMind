#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.breadth_gated_momentum.artifact import validate_artifact  # noqa: E402
from backend.services.engine.breadth_gated_momentum.engine import (  # noqa: E402
    build_historical, build_incremental_features, fetch_incremental, preregister,
    replay, run_fresh, token_status, validate_study,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


INSPECT = {
    "inspect-historical": "breadth_gated_momentum_historical_diagnostic",
    "inspect-fresh": "breadth_gated_momentum_fresh_assessment",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QM2 breadth-gated Signal-D forward protocol")
    value.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-010"))
    commands = value.add_subparsers(dest="command", required=True)
    for command in ("validate-gate", "create-fresh-lock", "build-historical-diagnostic",
                    "probe-token", "fetch-incremental-data", "build-incremental-features",
                    "run-fresh-observation", "validate-study"):
        commands.add_parser(command)
    for command in INSPECT:
        child = commands.add_parser(command); child.add_argument("artifact_id")
    return value


def _bundle(args):
    return load_authority_bundle(authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                 work_root=args.work_root / "inspect-authority", store_root=args.store_root)


def _inspect(args) -> dict:
    bundle = _bundle(args); expected = INSPECT[args.command]
    descriptor = bundle.store.find_by_artifact_id(args.artifact_id)
    if descriptor is None or descriptor.artifact_kind != expected:
        raise ValueError(f"Artifact not found with expected kind {expected}: {args.artifact_id}")
    target = args.work_root / "inspect" / expected / args.artifact_id
    if target.exists(): shutil.rmtree(target)
    bundle.store.materialize_artifact(descriptor.descriptor_id, target)
    identity = json.loads((target / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return {"status": "valid", "validation": validate_artifact(target, args.artifact_id, expected),
            "descriptor_id": descriptor.descriptor_id, "identity": identity}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        common = {"repository_root": ROOT, "work_root": args.work_root, "store_root": args.store_root}
        if args.command in {"validate-gate", "create-fresh-lock"}:
            result = preregister(**common)
        elif args.command == "build-historical-diagnostic":
            result = build_historical(**common)
        elif args.command == "probe-token":
            result = token_status()
        elif args.command == "fetch-incremental-data":
            result = fetch_incremental(**common)
        elif args.command == "build-incremental-features":
            result = build_incremental_features(**common)
        elif args.command == "run-fresh-observation":
            result = run_fresh(**common)
        elif args.command == "validate-study":
            result = validate_study(**common)
        elif args.command in INSPECT:
            result = _inspect(args)
        else:
            result = replay(**common)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
