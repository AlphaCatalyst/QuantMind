#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.services.engine.factor_validation import (
    FrozenTestAccessContext, build_validation_dataset, evaluate_frozen, evaluate_validation,
    parse_validation_spec, production_label_contract, validate_validation_dataset,
    validate_validation_result,
)
from backend.services.engine.factor_validation.labels import label_contract_id, label_contract_payload
from backend.services.engine.factor_validation.validation import validate_spec_lineage
from backend.services.engine.artifact_runtime import resolve_frozen_result, resolve_validation_result
from backend.services.engine.artifact_runtime.cli import add_runtime_arguments, runtime_context_from_args
from backend.services.engine.artifact_runtime.enums import ArtifactRuntimeMode
from backend.services.engine.artifact_runtime.errors import LegacyArtifactPathForbidden


def _common(command):
    command.add_argument("--dataset-root", required=True)
    command.add_argument("--snapshot-root", required=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="QuantMind Factor Validation v1")
    add_runtime_arguments(parser)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit-label")
    build = sub.add_parser("build-dataset"); build.add_argument("--source-root", required=True); _common(build); build.add_argument("--symbol-limit", type=int, default=300)
    for name in ("validate-spec", "plan", "evaluate-validation"):
        cmd = sub.add_parser(name); cmd.add_argument("--spec", required=True); _common(cmd)
        cmd.add_argument("--optimization-root", required=True); cmd.add_argument("--original-snapshot-root", required=True); cmd.add_argument("--original-values-root", required=True)
        if name == "evaluate-validation": cmd.add_argument("--factor-values-root", required=True); cmd.add_argument("--validation-root", required=True)
    frozen = sub.add_parser("evaluate-frozen")
    frozen.add_argument("--dataset-root", required=True); frozen.add_argument("--validation-root", required=True); frozen.add_argument("--factor-values-root", required=True)
    frozen.add_argument("--protocol-id", required=True); frozen.add_argument("--validation-dataset-id", required=True); frozen.add_argument("--candidate-selection-id", required=True)
    frozen.add_argument("--access-reason", required=True); frozen.add_argument("--requested-by", required=True)
    verify = sub.add_parser("validate-result"); verify.add_argument("--validation-root"); verify.add_argument("--validation-result-id", required=True); verify.add_argument("--candidate-selection-id")
    inspect = sub.add_parser("inspect"); inspect.add_argument("--validation-root"); inspect.add_argument("--validation-result-id", required=True); inspect.add_argument("--candidate-selection-id")
    frozen_replay = sub.add_parser("validate-frozen"); frozen_replay.add_argument("--frozen-result-id", required=True)
    args = parser.parse_args(argv)
    try:
        runtime = runtime_context_from_args(args)
        if runtime.policy.mode is ArtifactRuntimeMode.STORE_REQUIRED and args.command in {
            "build-dataset", "validate-spec", "plan", "evaluate-validation", "evaluate-frozen"
        }:
            raise LegacyArtifactPathForbidden("store_required forbids local Validation execution inputs")
        if args.command == "audit-label":
            contract = production_label_contract(); result = {"status": "audited", "label_contract_id": label_contract_id(contract), "contract": label_contract_payload(contract),
                "production_call_chain": ["docker/training/train.py:main", "docker/training/train.py:load_data", "backend/shared/feature_preprocess.py:apply_cs_mad_zscore"]}
        elif args.command == "build-dataset":
            result = build_validation_dataset(args.source_root, args.dataset_root, args.snapshot_root, symbol_limit=args.symbol_limit)
        elif args.command in ("validate-spec", "plan"):
            spec = parse_validation_spec(Path(args.spec)); lineage = validate_spec_lineage(spec, args.dataset_root, args.optimization_root, args.original_snapshot_root, args.original_values_root)
            result = {"status": "valid" if args.command == "validate-spec" else "planned", "validation_dataset_id": spec.validation_dataset_id,
                      "study_ids": list(spec.optimization_study_ids), "trial_count": len(lineage["trials"]),
                      "frozen_policy": dict(spec.frozen_test_policy), "frozen_labels_accessed": False,
                      "splits": lineage["dataset"]["manifest"]["splits"]}
        elif args.command == "evaluate-validation":
            spec = parse_validation_spec(Path(args.spec)); result = evaluate_validation(spec, dataset_root=args.dataset_root, snapshot_root=args.snapshot_root,
                factor_values_root=args.factor_values_root, validation_root=args.validation_root, optimization_root=args.optimization_root,
                original_snapshot_root=args.original_snapshot_root, original_values_root=args.original_values_root)
        elif args.command == "evaluate-frozen":
            context = FrozenTestAccessContext(args.protocol_id, args.validation_dataset_id, args.candidate_selection_id, args.access_reason, args.requested_by)
            result = evaluate_frozen(context, dataset_root=args.dataset_root, validation_root=args.validation_root, factor_values_root=args.factor_values_root)
        elif args.command == "validate-frozen":
            result = resolve_frozen_result(runtime, args.frozen_result_id).safe_summary()
            result["status"] = "valid"
        elif args.command in {"validate-result", "inspect"} and runtime.policy.mode is not ArtifactRuntimeMode.LEGACY_LOCAL:
            resolved = resolve_validation_result(runtime, args.validation_result_id)
            manifest = json.loads((resolved.materialized_root / "manifest.json").read_text())
            result = {"status": "valid", **resolved.safe_summary(),
                      "candidate_selection_id": manifest["candidate_selection_id"],
                      "trial_count": len(manifest["trial_results"]),
                      "eligible_count": len(manifest["candidate_order"]),
                      "selected_trial_ids": manifest["selected_trial_ids"],
                      "frozen_labels_accessed": False, "backtest_claim": False}
        elif args.command in {"validate-result", "inspect"}:
            if not args.validation_root or not args.candidate_selection_id:
                raise ValueError("legacy_local result validation requires local root and selection ID")
            result = validate_validation_result(args.validation_root, args.validation_result_id, args.candidate_selection_id)
            if args.command == "inspect":
                manifest = result["manifest"]
                result = {"status": "inspected", "validation_result_id": args.validation_result_id,
                          "candidate_selection_id": args.candidate_selection_id, "trial_count": len(manifest["trial_results"]),
                          "eligible_count": len(manifest["candidate_order"]), "selected_trial_ids": manifest["selected_trial_ids"],
                          "development_diagnostic_used": False, "frozen_labels_accessed": False, "backtest_claim": False}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, default=str)); return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
