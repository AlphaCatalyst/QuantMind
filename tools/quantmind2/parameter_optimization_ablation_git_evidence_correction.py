#!/usr/bin/env python3
"""Build immutable Git evidence correction for QM2-R1-005."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET_TASK_ID = "QM2-R1-005"
TARGET_RUN_ID = "QM2-R1-005-20260722T052636Z-82f13f9"
TARGET_BASE = "82f13f92d9accd39e1ec9209c38a66b37ccff457"
TARGET_COMMIT = "3e04743f41ee6d604a7de6064558f9925d89d993"
TARGET_DIRECTORY = (
    "docs/quantmind2/implementation/runs/2026/2026-07/" + TARGET_RUN_ID
)
TARGET_MANIFEST = f"{TARGET_DIRECTORY}/manifest.json"
TARGET_REPORT = f"{TARGET_DIRECTORY}/report.md"
OUTPUT = ROOT / (
    "docs/quantmind2/implementation/corrections/"
    "QM2-R1-005-git-evidence-correction-v1.json"
)
VERIFIED_AT = "2026-07-22T13:32:05Z"


class CorrectionError(RuntimeError):
    """Raised when immutable target evidence cannot be reconstructed."""


def _git(*args: str, text: bool = False):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=text)


def _blob(commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value) -> str:
    return _sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _target_inventory() -> tuple[list[str], list[str], list[dict]]:
    changed: list[str] = []
    added: list[str] = []
    hashes: list[dict] = []
    for line in _git(
        "diff", "--name-status", "-M", TARGET_BASE, TARGET_COMMIT, "--", text=True
    ).splitlines():
        columns = line.split("\t")
        status = columns[0]
        if status.startswith("R"):
            previous_path, path = columns[1:]
            before_path = previous_path
            change_type = "renamed"
        elif status in {"A", "M", "D"} and len(columns) == 2:
            path = columns[1]
            previous_path = None
            before_path = path
            change_type = {"A": "added", "M": "modified", "D": "deleted"}[status]
        else:
            raise CorrectionError(f"unsupported Git entry: {line}")
        changed.append(path)
        if status == "A" or status.startswith("R"):
            added.append(path)
        if path == TARGET_MANIFEST:
            continue
        before = _blob(TARGET_BASE, before_path)
        after = _blob(TARGET_COMMIT, path)
        hashes.append(
            {
                "path": path,
                "change_type": change_type,
                "before_hash": None if before is None else _sha256(before),
                "after_hash": None if after is None else _sha256(after),
                "previous_path": previous_path,
            }
        )
    return sorted(changed), sorted(added), sorted(hashes, key=lambda item: item["path"])


def _source_bundle_hash(changed: list[str], added: list[str]) -> str:
    records = []
    added_set = set(added)
    for path in changed:
        if path == TARGET_MANIFEST:
            records.append({"path": path, "sha256": None, "kind": "manifest_payload"})
            continue
        blob = _blob(TARGET_COMMIT, path)
        if blob is None and path not in added_set:
            records.append({"path": path, "sha256": None, "kind": "deleted"})
        elif blob is None:
            raise CorrectionError(f"added target blob is missing: {path}")
        else:
            records.append({"path": path, "sha256": _sha256(blob), "kind": "file"})
    return _canonical_hash(records)


def build_correction(verified_at: str = VERIFIED_AT) -> dict:
    manifest_bytes = _blob(TARGET_COMMIT, TARGET_MANIFEST)
    report_bytes = _blob(TARGET_COMMIT, TARGET_REPORT)
    if manifest_bytes is None or report_bytes is None:
        raise CorrectionError("target Run blobs are missing from target commit")
    manifest = json.loads(manifest_bytes)
    changed, added, verified_hashes = _target_inventory()
    recorded_hashes = sorted(manifest["changed_files"], key=lambda item: item["path"])
    recorded_by_path = {item["path"]: item for item in recorded_hashes}
    verified_by_path = {item["path"]: item for item in verified_hashes}
    mismatches = [
        {
            "path": path,
            "recorded": recorded_by_path[path],
            "verified": verified_by_path[path],
        }
        for path in sorted(set(recorded_by_path) & set(verified_by_path))
        if recorded_by_path[path] != verified_by_path[path]
    ]
    verified_source_bundle_hash = _source_bundle_hash(changed, added)
    return {
        "schema_version": "1.0.0",
        "object_type": "GitEvidenceCorrectionV1",
        "correction_id": "qm2-r1-005-git-evidence-correction-v1",
        "target_task_id": TARGET_TASK_ID,
        "target_run_id": TARGET_RUN_ID,
        "target_base_commit": TARGET_BASE,
        "target_commit": TARGET_COMMIT,
        "target_report_path": TARGET_REPORT,
        "target_manifest_path": TARGET_MANIFEST,
        "target_git_changed_paths": changed,
        "target_git_added_paths": added,
        "target_changed_file_hashes": verified_hashes,
        "recorded_changed_file_hashes": recorded_hashes,
        "changed_file_hash_mismatches": mismatches,
        "target_source_bundle_hash": verified_source_bundle_hash,
        "recorded_source_bundle_hash": manifest["integrity"]["source_bundle_sha256"],
        "source_bundle_hash_matches": (
            verified_source_bundle_hash
            == manifest["integrity"]["source_bundle_sha256"]
        ),
        "original_gap_codes": ["changed_file_hashes", "source_bundle_hash"],
        "correction_reason": (
            "Manifest哈希冻结后，合同文档的一处行尾空格被清理，"
            "导致提交内容与Manifest记录哈希不一致。"
        ),
        "root_cause": "post_manifest_finalization_format_change",
        "verified_by_git": {
            "method": "target_commit_diff_inventory_blob_sha256_and_source_bundle",
            "target_git_changed_path_count": len(changed),
            "target_git_added_path_count": len(added),
            "target_changed_file_hash_count": len(verified_hashes),
            "changed_file_hash_mismatch_count": len(mismatches),
            "canonical_inventory_sha256": _canonical_hash(
                {
                    "target_git_added_paths": added,
                    "target_git_changed_paths": changed,
                }
            ),
            "target_manifest_sha256": _sha256(manifest_bytes),
            "target_report_sha256": _sha256(report_bytes),
            "verified_at": verified_at,
        },
        "historical_target_task_result": "blocked",
        "historical_target_git_status": "git_inconsistent",
        "historical_target_validated": False,
        "historical_target_indexable": False,
        "resolved_ledger_status": "completed_corrected",
        "resolved_status_semantics": (
            "The immutable target remains Git-inconsistent; this independently "
            "completed correction Run and its corrects relationship are the "
            "Ledger-supported corrected completion."
        ),
        "research_execution": {
            "agent_calls": 0,
            "factor_optimization_calls": 0,
            "strategy_optimization_calls": 0,
            "qlib_calls": 0,
            "network_calls": 0,
            "promotion_writes": 0,
            "new_research_artifacts": 0,
            "new_research_blobs": 0,
            "candidate_state_changes": 0,
        },
    }


def validate_correction(payload: dict) -> dict:
    expected = build_correction(
        payload.get("verified_by_git", {}).get("verified_at", VERIFIED_AT)
    )
    if payload != expected:
        raise CorrectionError("correction differs from immutable target Git evidence")
    if len(payload["changed_file_hash_mismatches"]) != 1:
        raise CorrectionError("expected exactly one committed file-hash mismatch")
    if payload["source_bundle_hash_matches"]:
        raise CorrectionError("target source-bundle mismatch was not reproduced")
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
    print(
        json.dumps(
            {
                "correction_id": payload["correction_id"],
                "changed_path_count": len(payload["target_git_changed_paths"]),
                "added_path_count": len(payload["target_git_added_paths"]),
                "changed_file_hash_mismatch_count": len(
                    payload["changed_file_hash_mismatches"]
                ),
                "source_bundle_hash_matches": payload["source_bundle_hash_matches"],
                "valid": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
