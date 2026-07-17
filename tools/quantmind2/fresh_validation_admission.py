#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from backend.services.engine.factor_registry.reconciliation import validate_reconciliation
from backend.services.engine.factor_registry.snapshot import validate_registry_snapshot
from backend.services.engine.fresh_validation_admission import (
    CampaignAdmissionSource, reconcile_and_admit, validate_admission_result,
)
from backend.services.engine.artifact_runtime import resolve_fresh_admission
from backend.services.engine.artifact_runtime.cli import add_runtime_arguments, runtime_context_from_args
from backend.services.engine.artifact_runtime.enums import ArtifactRuntimeMode
from backend.services.engine.artifact_runtime.errors import LegacyArtifactPathForbidden

ANCESTOR_ID = "frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9"
BASELINE_ID = "frs_d40bfd7497ad56d3f71fd16dd7363222d32a5528e8780ca3765c27ca3c584718"
EXTERNAL_ID = "frs_7ab0a844d791abf4dbd62c5558a7261078875bbc0b3606aa1b02ce591cf01054"
ANCESTOR_ROOT = "/private/tmp/qm2-p0-007-registry"
BASELINE_ROOT = "/private/tmp/qm2-p0-008-final3"
EXTERNAL_ROOT = "/private/tmp/qm2-p0-008f-external4"
SNAPSHOT_ROOT = "/private/tmp/qm2-p0-006-validation/snapshots"


def sources():
    return (
        CampaignAdmissionSource(f"{BASELINE_ROOT}/campaign-artifacts",
            "rc_4970d1419d17d1327b2092c7ff85cb52d680488555c6408ec3a8ef571219cd5f",
            f"{BASELINE_ROOT}/optimization", f"{BASELINE_ROOT}/factor-values", SNAPSHOT_ROOT,
            "rcr_3b2923521f465e2787e0607f08dc723b0ef0cb3fe081a850c172cb4a7c950964"),
        CampaignAdmissionSource(f"{EXTERNAL_ROOT}/campaign-artifacts",
            "rc_0b13d7f235ac948a10c97092c6ce3bbad99ecdefc2c20c93c3648644a5d9401c",
            f"{EXTERNAL_ROOT}/optimization", f"{EXTERNAL_ROOT}/factor-values", SNAPSHOT_ROOT,
            "rcr_19183f859c9bbe7949ec9e3c07f9870d8e7c47e9140211cc47b9de429db3d3ca"))


def run(output_root):
    output = Path(output_root); baseline, external = sources()
    return reconcile_and_admit(
        ancestor_registry_root=ANCESTOR_ROOT, ancestor_snapshot_id=ANCESTOR_ID,
        baseline_registry_root=f"{BASELINE_ROOT}/registry", baseline_snapshot_id=BASELINE_ID,
        baseline_source=baseline, external_registry_root=f"{EXTERNAL_ROOT}/registry",
        external_snapshot_id=EXTERNAL_ID, external_source=external,
        registry_output_root=output / "registry", admission_output_root=output / "fresh-validation-admission",
        reconciliation_output_root=output / "registry-reconciliation")


def summary(result):
    registry = result["registry"]; admission = result["admission"]
    counts = {name: sum(x.status.value == name for x in registry.entries)
              for name in ("promotion_candidate", "approved", "active")}
    return {"common_ancestor": result["ancestor"].registry_snapshot_id,
        "source_registries": sorted(x.registry_snapshot_id for x in result["sources"]),
        "resulting_registry": registry.registry_snapshot_id,
        "reconciliation_id": result["reconciliation"].reconciliation_id,
        "entry_count": len(registry.entries), "agent_entry_count": len(admission.candidates),
        "admission_policy_id": admission.policy.policy_id, "admission_result_id": admission.result_id,
        "admitted_count": len(admission.admitted_factor_instance_ids),
        "rejected_count": len(admission.rejected_factor_instance_ids),
        "admitted_factor_instance_ids": list(admission.admitted_factor_instance_ids),
        "rejected_factor_instance_ids": list(admission.rejected_factor_instance_ids), **counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconcile Agent Registry branches and admit Fresh Validation candidates")
    add_runtime_arguments(parser)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile-registry", "evaluate-admission"):
        command = sub.add_parser(name); command.add_argument("--output-root", required=True)
    command = sub.add_parser("validate-reconciliation"); command.add_argument("--output-root", required=True); command.add_argument("--reconciliation-id", required=True)
    command = sub.add_parser("validate-admission"); command.add_argument("--output-root"); command.add_argument("--result-id", required=True)
    command = sub.add_parser("inspect"); command.add_argument("--output-root")
    args = parser.parse_args(argv)
    runtime = runtime_context_from_args(args)
    if runtime.policy.mode is not ArtifactRuntimeMode.LEGACY_LOCAL and args.command in {"validate-admission", "inspect"}:
        result_id = getattr(args, "result_id", None) or "fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab"
        resolved = resolve_fresh_admission(runtime, result_id)
        payload = {"status": "valid", **resolved.safe_summary()}
        print(json.dumps(payload, indent=2, sort_keys=True)); return 0
    if runtime.policy.mode is ArtifactRuntimeMode.STORE_REQUIRED:
        raise LegacyArtifactPathForbidden("store_required forbids local Fresh Admission reconstruction")
    if args.command in {"reconcile-registry", "evaluate-admission"}:
        payload = summary(run(args.output_root))
    elif args.command == "validate-reconciliation":
        value = validate_reconciliation(args.output_root, args.reconciliation_id); payload = {"reconciliation_id": value.reconciliation_id, "valid": True}
    elif args.command == "validate-admission":
        value = validate_admission_result(args.output_root, args.result_id); payload = {"result_id": value.result_id, "valid": True, "admitted_count": len(value.admitted_factor_instance_ids), "rejected_count": len(value.rejected_factor_instance_ids)}
    else:
        candidates = sorted((Path(args.output_root) / "fresh-validation-admission").glob("fvar_*"))
        if len(candidates) != 1: raise SystemExit("inspect requires exactly one admission artifact")
        admission = validate_admission_result(candidates[0].parent, candidates[0].name)
        registries = sorted((Path(args.output_root) / "registry" / "snapshots").glob("frs_*"))
        if len(registries) != 1: raise SystemExit("inspect requires exactly one canonical Registry")
        registry = validate_registry_snapshot(registries[0].parent.parent, registries[0].name)
        payload = {"result_id": admission.result_id, "registry_snapshot_id": registry.registry_snapshot_id,
                   "entry_count": len(registry.entries), "candidate_ids": [x.factor_instance_id for x in admission.candidates]}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
