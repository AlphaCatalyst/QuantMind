#!/usr/bin/env python3
"""Build immutable Git path-inventory correction evidence for QM2-P0-010."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TARGET_RUN_ID = "QM2-P0-010-20260717T154150Z-26cebb9"
TARGET_BASE = "26cebb9a9dfa95a295a57d66db193d9629844b90"
TARGET_COMMIT = "77f5b1fd36fd4f85e14a4c0dd5945abefe847f7d"
TARGET_DIRECTORY = (
    "docs/quantmind2/implementation/runs/2026/2026-07/"
    f"{TARGET_RUN_ID}"
)
TARGET_MANIFEST = f"{TARGET_DIRECTORY}/manifest.json"
TARGET_REPORT = f"{TARGET_DIRECTORY}/report.md"
SCHEMA = ROOT / (
    "docs/quantmind2/implementation/schemas/"
    "implementation_git_inventory_correction_v1.schema.json"
)
OUTPUT = ROOT / (
    "docs/quantmind2/implementation/corrections/"
    "QM2-P0-010-git-inventory-correction-v1.json"
)


class GitInventoryCorrectionError(RuntimeError):
    """Safe failure for correction construction or validation."""


def _git(root: Path, *args: str, text: bool = False):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=text
    )


def _blob(root: Path, commit: str, path: str) -> bytes:
    return _git(root, "show", f"{commit}:{path}")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_inventory_hash(changed: list[str], added: list[str]) -> str:
    payload = {
        "integrity.git_added_paths": sorted(added),
        "integrity.git_changed_paths": sorted(changed),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(encoded)


def git_path_inventory(
    root: Path, base: str, containing: str
) -> dict[str, list]:
    lines = _git(
        root, "diff", "--name-status", "-M", base, containing, "--", text=True
    ).splitlines()
    changed: list[str] = []
    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []
    renamed: list[dict[str, str]] = []
    for line in lines:
        columns = line.split("\t")
        status = columns[0]
        if status.startswith("R") and len(columns) == 3:
            previous, path = columns[1:]
            changed.append(path)
            added.append(path)
            deleted.append(previous)
            renamed.append({"previous_path": previous, "path": path})
        elif status in {"A", "M", "D"} and len(columns) == 2:
            path = columns[1]
            changed.append(path)
            {"A": added, "M": modified, "D": deleted}[status].append(path)
        else:
            raise GitInventoryCorrectionError(
                f"unsupported Git name-status entry: {status}"
            )
    return {
        "changed": sorted(set(changed)),
        "added": sorted(set(added)),
        "modified": sorted(set(modified)),
        "deleted": sorted(set(deleted)),
        "renamed": sorted(renamed, key=lambda item: (item["path"], item["previous_path"])),
    }


def compare_paths(recorded: list[str], verified: list[str]) -> dict[str, list[str]]:
    recorded_set = set(recorded)
    verified_set = set(verified)
    return {
        "recorded": sorted(recorded_set),
        "verified": sorted(verified_set),
        "missing": sorted(verified_set - recorded_set),
        "unexpected": sorted(recorded_set - verified_set),
    }


def verify_finalized_run_inventory(
    *,
    manifest_path: str,
    report_path: str,
    business_changed_files: list[str],
    declared_changed_paths: list[str],
    declared_added_paths: list[str],
    actual: dict[str, list],
) -> None:
    """Guard a finalized committed Run without altering its Manifest."""
    if sorted(declared_changed_paths) != actual["changed"]:
        raise GitInventoryCorrectionError("finalized git_changed_paths are incomplete")
    if sorted(declared_added_paths) != actual["added"]:
        raise GitInventoryCorrectionError("finalized git_added_paths are incomplete")
    if manifest_path not in actual["changed"] or manifest_path not in actual["added"]:
        raise GitInventoryCorrectionError("Run Manifest is absent from Git inventory")
    if manifest_path in business_changed_files:
        raise GitInventoryCorrectionError("Run Manifest is a business ChangedFile")
    expected_business = sorted(path for path in actual["changed"] if path != manifest_path)
    if sorted(business_changed_files) != expected_business:
        raise GitInventoryCorrectionError("business ChangedFiles are incomplete")
    if report_path not in business_changed_files:
        raise GitInventoryCorrectionError("Run Report is absent from business changes")


def build_correction(
    root: Path = ROOT,
    verified_at: str = "2026-07-18T00:00:00Z",
) -> dict:
    manifest = json.loads(_blob(root, TARGET_COMMIT, TARGET_MANIFEST))
    actual = git_path_inventory(root, TARGET_BASE, TARGET_COMMIT)
    recorded_changed = manifest["integrity"]["git_changed_paths"]
    recorded_added = manifest["integrity"]["git_added_paths"]
    business = sorted(item["path"] for item in manifest["changed_files"])
    changed_comparison = compare_paths(recorded_changed, actual["changed"])
    added_comparison = compare_paths(recorded_added, actual["added"])
    return {
        "schema_version": "1.0.0",
        "correction_id": "qm2-p0-010-git-inventory-correction-v1",
        "target_run_id": TARGET_RUN_ID,
        "target_base_commit": TARGET_BASE,
        "target_containing_commit": TARGET_COMMIT,
        "verification_method": "git_commit_diff_path_inventory",
        "fields": {
            "integrity.git_changed_paths": changed_comparison,
            "integrity.git_added_paths": added_comparison,
        },
        "verified_git_modified_paths": actual["modified"],
        "verified_git_deleted_paths": actual["deleted"],
        "verified_git_renamed_paths": actual["renamed"],
        "business_changed_files": business,
        "manifest_path": TARGET_MANIFEST,
        "report_path": TARGET_REPORT,
        "manifest_in_verified_changed_paths": TARGET_MANIFEST in actual["changed"],
        "manifest_in_verified_added_paths": TARGET_MANIFEST in actual["added"],
        "business_changed_files_manifest_exclusion_verified": TARGET_MANIFEST not in business,
        "report_business_classification_verified": TARGET_REPORT in business,
        "verified_inventory_sha256": canonical_inventory_hash(
            actual["changed"], actual["added"]
        ),
        "immutable_target_manifest_sha256": _sha256(
            _blob(root, TARGET_COMMIT, TARGET_MANIFEST)
        ),
        "immutable_target_report_sha256": _sha256(
            _blob(root, TARGET_COMMIT, TARGET_REPORT)
        ),
        "root_cause": "incorrect_run_generation_usage",
        "root_cause_detail": (
            "The pre-commit structured inventory excluded the Run Manifest from both "
            "business ChangedFiles and integrity Git inventories; only the business "
            "exclusion is valid. The producer did not infer or remove the path."
        ),
        "effect": "evidence_correction_only",
        "artifact_store_identity": {
            "reachability_plan_id": "rap_f3aca751ad751c976888fd9b464f9f56dd4913339b226786c0c3a7ef65ccc247",
            "inventory_id": "sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312",
            "artifact_count": 65,
            "blob_count": 280,
            "integrity_status": "healthy",
            "missing_reachable_artifact_count": 0,
            "unreferenced_blob_count": 0,
        },
        "fresh_validation_identity": {
            "candidate_lock_id": "fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b",
            "protocol_id": "fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867",
            "exposure_ledger_id": "rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff",
            "watermark_id": "fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248",
            "eligible_date_count": 0,
            "status": "awaiting_first_fresh_date",
        },
        "verified_at": verified_at,
    }


def validate_correction(payload: dict, root: Path = ROOT) -> dict:
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            from jsonschema import Draft202012Validator

            Draft202012Validator(schema).validate(payload)
        except ModuleNotFoundError:
            from tools.quantmind2.validate_context_bootstrap import validate_instance

            validate_instance(payload, schema)
    except Exception as exc:
        raise GitInventoryCorrectionError(
            "Git inventory correction Schema validation failed"
        ) from exc
    expected = build_correction(root, payload["verified_at"])
    if payload != expected:
        raise GitInventoryCorrectionError(
            "correction differs from immutable committed Git evidence"
        )
    return payload


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "validate", "inspect"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if args.command == "generate":
        payload = build_correction()
        _write(args.output, payload)
    else:
        payload = validate_correction(json.loads(args.output.read_text(encoding="utf-8")))
    fields = payload["fields"]
    result = {
        "correction_id": payload["correction_id"],
        "changed_missing_count": len(fields["integrity.git_changed_paths"]["missing"]),
        "added_missing_count": len(fields["integrity.git_added_paths"]["missing"]),
        "verified_inventory_sha256": payload["verified_inventory_sha256"],
        "valid": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
