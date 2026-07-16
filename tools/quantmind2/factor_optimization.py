#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.services.engine.factor_dsl import snapshot_contract
from backend.services.engine.factor_optimization import execute_study, parse_optimization_spec, plan_study, validate_study


def _plan(args):
    spec = parse_optimization_spec(Path(args.spec))
    contract = snapshot_contract(args.snapshot_root, spec.snapshot_id)
    return spec, plan_study(spec, contract), contract


def _plan_payload(study):
    return {"study_id": study.study_id, "template_id": study.template_id, "snapshot_id": study.snapshot_id,
            "parameter_roles": {k: v.value for k, v in sorted(study.spec.parameter_roles.items())},
            "trial_count": len(study.trials), "budget": study.spec.budget.__dict__,
            "trials": [{"ordinal": t.ordinal, "trial_id": t.trial_id, "parameters": dict(t.parameters),
                        "factor_instance_id": t.factor_instance_id} for t in study.trials]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="QuantMind deterministic Factor Optimization v1")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-spec", "plan", "execute", "validate-study"):
        cmd = sub.add_parser(name); cmd.add_argument("--spec", required=True); cmd.add_argument("--snapshot-root", required=True)
        if name in ("execute", "validate-study"):
            cmd.add_argument("--factor-values-root", required=True); cmd.add_argument("--optimization-root", required=True)
    inspect = sub.add_parser("inspect"); inspect.add_argument("--optimization-root", required=True); inspect.add_argument("--study-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            path = Path(args.optimization_root) / args.study_id
            manifest = json.loads((path / "manifest.json").read_text()); summary = json.loads((path / "summary.json").read_text())
            result = {"status": "inspected", "study_id": args.study_id, "template_id": manifest["template_id"],
                      "snapshot_id": manifest["snapshot_id"], "counts": summary["counts"],
                      "validation_candidate_order": summary["validation_candidate_order"], "predictive_claim": False}
        else:
            spec, study, contract = _plan(args)
            if args.command == "validate-spec": result = {"status": "valid", **_plan_payload(study)}
            elif args.command == "plan": result = {"status": "planned", **_plan_payload(study)}
            elif args.command == "execute":
                run = execute_study(study, contract, args.snapshot_root, args.factor_values_root, args.optimization_root)
                result = {"status": "executed", "study_id": run.study_id, "result_id": run.result_id,
                          "study_status": run.status.value, "exact_existing": run.exact_existing,
                          "trial_count": len(run.trials), "eligible_count": len(run.validation_candidate_order),
                          "validation_candidate_order": list(run.validation_candidate_order), "predictive_claim": False}
            else:
                run = validate_study(study, args.snapshot_root, args.factor_values_root, args.optimization_root)
                result = {"status": "valid", "study_id": run.study_id, "result_id": run.result_id,
                          "trial_count": len(run.trials), "eligible_count": len(run.validation_candidate_order),
                          "validation_candidate_order": list(run.validation_candidate_order), "predictive_claim": False}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)); return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
