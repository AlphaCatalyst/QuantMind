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

from backend.services.engine.skip_recent_momentum.artifact import KINDS, validate_artifact  # noqa: E402
from backend.services.engine.skip_recent_momentum.engine import execute_experiment, replay_experiment  # noqa: E402
from backend.services.engine.skip_recent_momentum.protocol import (  # noqa: E402
    BUDGET, COMPLETENESS_REQUIRED, FEATURES, FOLDS, FORMAL_STRATEGY, REPORT_PERIODS,
    SOURCE_CATALOG_ID, SOURCE_DATASET_ID, SOURCE_EXPERIMENT_ID, SUBFAMILIES,
)
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle  # noqa: E402


INSPECT_KINDS = {
    "inspect-agent-response": "research_agent_raw_response",
    "inspect-proposal": "research_proposal",
    "inspect-template": "factor_template_definition",
    "inspect-trial": "factor_optimization_trial_detail",
    "inspect-fold-lock": "factor_fold_candidate_lock",
    "inspect-candidate": "skip_recent_momentum_candidate_lock",
    "inspect-report": "skip_recent_momentum_report",
    "inspect-assessment": "skip_recent_momentum_assessment",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QM2 replayable skip-recent momentum research v1")
    parser.add_argument("--artifact-runtime-mode", choices=("store_required",), default="store_required")
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--work-root", type=Path, default=Path("/private/tmp/qm2-r1-003"))
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-artifact-contract", "plan", "execute", "validate-experiment"):
        commands.add_parser(command)
    for command in INSPECT_KINDS:
        sub = commands.add_parser(command)
        sub.add_argument("artifact_id")
    return parser


def _bundle(args):
    return load_authority_bundle(
        authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=args.work_root / "cli-authority", store_root=args.store_root,
    )


def _inspect(args) -> dict:
    bundle = _bundle(args)
    descriptor = bundle.store.find_by_artifact_id(args.artifact_id)
    expected = INSPECT_KINDS[args.command]
    if descriptor is None or descriptor.artifact_kind != expected:
        raise ValueError(f"Artifact not found with expected kind {expected}: {args.artifact_id}")
    destination = args.work_root / "inspect" / expected / args.artifact_id
    if destination.exists():
        shutil.rmtree(destination)
    bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
    validation = validate_artifact(destination, args.artifact_id, expected)
    identity = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["identity"]
    return {"status": "valid", "descriptor_id": descriptor.descriptor_id,
            "validation": validation, "identity": identity}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-artifact-contract":
            result = {"status": "valid", "contract": "RESEARCH_ARTIFACT_COMPLETENESS_V1",
                      "gate": "ResearchArtifactCompletenessGateV1",
                      "artifact_kinds": sorted(KINDS), "required_fields": COMPLETENESS_REQUIRED}
        elif args.command == "plan":
            result = {"status": "planned", "source_catalog_id": SOURCE_CATALOG_ID,
                      "source_dataset_id": SOURCE_DATASET_ID, "source_experiment_id": SOURCE_EXPERIMENT_ID,
                      "subfamilies": SUBFAMILIES, "features": FEATURES, "folds": list(FOLDS),
                      "strategy": FORMAL_STRATEGY, "report_periods": REPORT_PERIODS,
                      "budget": BUDGET.__dict__, "runtime_mode": args.artifact_runtime_mode}
        elif args.command == "execute":
            result = execute_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        elif args.command == "validate-experiment":
            result = replay_experiment(repository_root=ROOT, work_root=args.work_root, store_root=args.store_root)
        else:
            result = _inspect(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_code": type(exc).__name__,
                          "safe_summary": str(exc)[:500]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
