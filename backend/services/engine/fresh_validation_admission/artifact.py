import json
import os
import re
import shutil
import uuid
from pathlib import Path

from backend.services.engine.factor_registry.canonical import sha256_file, write_json

from .errors import FreshValidationAdmissionError
from .evaluator import candidate_payload
from .models import FreshValidationAdmissionPolicy, FreshValidationAdmissionResult
from .policy import policy_payload, validate_admission_policy


SCHEMA_VERSION = "fresh-validation-admission-result-v1"


def publish_admission_result(output_root, result):
    validate_admission_policy(result.policy)
    target = Path(output_root) / result.result_id
    if target.exists():
        return validate_admission_result(output_root, result.result_id, exact_existing=True)
    staging = target.parent / f".{result.result_id}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        write_json(staging / "policy.json", policy_payload(result.policy))
        candidates = staging / "candidates"; candidates.mkdir()
        for row in result.candidates:
            write_json(candidates / f"{row.factor_instance_id}.json", candidate_payload(row))
        write_json(staging / "admitted.json", {"factor_instance_ids": list(result.admitted_factor_instance_ids)})
        write_json(staging / "rejected.json", {"factor_instance_ids": list(result.rejected_factor_instance_ids)})
        hashes = {p.relative_to(staging).as_posix(): sha256_file(p) for p in sorted(staging.rglob("*.json"))}
        write_json(staging / "manifest.json", {"schema_version": SCHEMA_VERSION,
            "result_id": result.result_id, "policy_id": result.policy.policy_id,
            "candidate_count": len(result.candidates), "admitted_count": len(result.admitted_factor_instance_ids),
            "rejected_count": len(result.rejected_factor_instance_ids),
            "candidate_ids_in_rank_order": [row.factor_instance_id for row in result.candidates],
            "file_hashes": hashes})
        target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target); staging = None
    finally:
        if staging is not None and staging.exists(): shutil.rmtree(staging)
    return validate_admission_result(output_root, result.result_id)


def validate_admission_result(output_root, result_id, exact_existing=False):
    if not re.fullmatch(r"^fvar_[0-9a-f]{64}$", str(result_id)):
        raise FreshValidationAdmissionError("Admission Result ID is invalid")
    root = Path(output_root) / result_id
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        policy_data = json.loads((root / "policy.json").read_text())
    except Exception as exc:
        raise FreshValidationAdmissionError("Admission Result is unreadable") from exc
    inventory = {p.relative_to(root).as_posix() for p in root.rglob("*.json") if p.name != "manifest.json"}
    if inventory != set(manifest.get("file_hashes", {})):
        raise FreshValidationAdmissionError("Admission Result inventory mismatch")
    for relative, digest in manifest["file_hashes"].items():
        if sha256_file(root / relative) != digest:
            raise FreshValidationAdmissionError("Admission Result hash mismatch")
    policy = FreshValidationAdmissionPolicy(**policy_data); validate_admission_policy(policy)
    from .models import AdmissionCandidateResult
    rows = []
    candidate_ids = manifest.get("candidate_ids_in_rank_order", [])
    for factor_instance_id in candidate_ids:
        path = root / "candidates" / f"{factor_instance_id}.json"
        item = json.loads(path.read_text()); item["reasons"] = tuple(item["reasons"])
        row = AdmissionCandidateResult(**item)
        if row.factor_instance_id != factor_instance_id:
            raise FreshValidationAdmissionError("Admission candidate path identity mismatch")
        rows.append(row)
    admitted = tuple(json.loads((root / "admitted.json").read_text())["factor_instance_ids"])
    rejected = tuple(json.loads((root / "rejected.json").read_text())["factor_instance_ids"])
    # The immutable result identity is checked from its complete policy and candidate outcomes.
    stable = {"schema_version": SCHEMA_VERSION, "policy": policy_payload(policy),
              "candidates": [candidate_payload(x) for x in rows]}
    from .canonical import hash_payload
    expected = "fvar_" + hash_payload(stable)
    if (expected != result_id or manifest.get("schema_version") != SCHEMA_VERSION or
            manifest.get("result_id") != result_id or manifest.get("policy_id") != policy.policy_id or
            manifest.get("candidate_count") != len(rows) or
            manifest.get("admitted_count") != len(admitted) or manifest.get("rejected_count") != len(rejected) or
            [row.rank for row in rows] != list(range(1, len(rows) + 1)) or
            any(row.policy_id != policy.policy_id for row in rows) or
            admitted != tuple(x.factor_instance_id for x in rows if x.admitted) or
            rejected != tuple(x.factor_instance_id for x in rows if not x.admitted)):
        raise FreshValidationAdmissionError("Admission Result identity or outcome is invalid")
    return FreshValidationAdmissionResult(result_id, policy, tuple(rows), admitted, rejected,
                                           str(root), exact_existing)


__all__ = ["publish_admission_result", "validate_admission_result"]
