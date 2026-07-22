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

from backend.services.engine.default_first_momentum_search.artifact import validate_artifact  # noqa: E402
from backend.services.engine.default_first_momentum_search.engine import (  # noqa: E402
    execute_experiment, replay_experiment, validate_governance,
)
from backend.services.engine.default_first_momentum_search.protocol import (  # noqa: E402
    ANNUAL_PERIODS, BUDGET, DEFAULT_GATE, DEVELOPMENT_PERIOD, ELIGIBILITY, FORMAL_STRATEGY,
    GOVERNANCE_DECISION_ID, REPORT_PERIODS, ROUND_FEATURES, ROUND_THEMES, SOURCE_CATALOG_ID,
    SOURCE_DATASET_ID,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


INSPECT = {
    "inspect-default-evaluation": "default_parameter_evaluation",
    "inspect-local-rescue": "local_factor_rescue_study",
    "inspect-development-lock": "development_parameter_lock",
    "inspect-candidate": "default_first_momentum_candidate_lock",
    "inspect-report": "default_first_momentum_report",
    "inspect-assessment": "default_first_momentum_assessment",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="QM2 default-first momentum structure search v2")
    value.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    value.add_argument("--store-root", type=Path)
    value.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-007"))
    commands = value.add_subparsers(dest="command", required=True)
    for command in ("validate-governance", "plan", "execute", "validate-experiment"):
        commands.add_parser(command)
    for command in INSPECT:
        item = commands.add_parser(command); item.add_argument("artifact_id")
    return value


def bundle(args):
    return load_authority_bundle(authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
                                 work_root=args.work_root / "cli-authority", store_root=args.store_root)


def inspect(args) -> dict:
    source = bundle(args); expected = INSPECT[args.command]
    descriptor = source.store.find_by_artifact_id(args.artifact_id)
    if descriptor is None or descriptor.artifact_kind != expected:
        raise ValueError(f"Artifact not found with expected kind {expected}: {args.artifact_id}")
    destination = args.work_root / "inspect" / expected / args.artifact_id
    if destination.exists(): shutil.rmtree(destination)
    source.store.materialize_artifact(descriptor.descriptor_id, destination)
    validation = validate_artifact(destination, args.artifact_id, expected)
    identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return {"status": "valid", "descriptor_id": descriptor.descriptor_id, "validation": validation, "identity": identity}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate-governance":
            result = validate_governance(bundle(args), args.work_root / "governance")
        elif args.command == "plan":
            result = {"status": "planned", "governance_decision_id": GOVERNANCE_DECISION_ID,
                "source_catalog_id": SOURCE_CATALOG_ID, "source_dataset_id": SOURCE_DATASET_ID,
                "development_period": DEVELOPMENT_PERIOD, "annual_periods": ANNUAL_PERIODS,
                "report_periods": REPORT_PERIODS, "round_themes": ROUND_THEMES,
                "round_features": ROUND_FEATURES, "strategy": FORMAL_STRATEGY,
                "default_gate": DEFAULT_GATE, "eligibility": ELIGIBILITY, "budget": BUDGET.__dict__,
                "factor_optimization_mode": "default_first", "strategy_optimization_calls": 0,
                "combined_optimization_calls": 0, "runtime_mode": args.artifact_runtime_mode}
        elif args.command == "execute":
            result = execute_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-experiment":
            result = replay_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            result = inspect(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
