#!/usr/bin/env python3
"""Build and validate immutable ChangedFiles correction evidence from Git blobs."""

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

TARGET_RUN_ID = "QM2-P0-009-20260717T141500Z-34dfa6e"
TARGET_BASE = "34dfa6eb50d7bd9405c3d3bdf0019aa84f9de432"
TARGET_COMMIT = "a2a416898181b6269217e75012e66ad7ebc4c395"
TARGET_MANIFEST = "docs/quantmind2/implementation/runs/2026/2026-07/QM2-P0-009-20260717T141500Z-34dfa6e/manifest.json"
TARGET_REPORT = "docs/quantmind2/implementation/runs/2026/2026-07/QM2-P0-009-20260717T141500Z-34dfa6e/report.md"
SCHEMA = ROOT / "docs/quantmind2/implementation/schemas/implementation_changed_files_correction_v1.schema.json"
OUTPUT = ROOT / "docs/quantmind2/implementation/corrections/QM2-P0-009-changed-files-correction-v1.json"


class CorrectionError(RuntimeError):
    pass


def _git(root, *args, text=False):
    return subprocess.check_output(["git", "-C", str(root), *args], text=text)


def _blob(root, commit, path):
    return _git(root, "show", f"{commit}:{path}")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_inventory_hash(inventory):
    encoded = json.dumps(inventory, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return _sha(encoded)


def git_inventory(root, base, containing, excluded_path):
    lines = _git(root, "diff", "--name-status", "-M", base, containing, text=True).splitlines()
    inventory = []
    for line in lines:
        fields = line.split("\t"); status = fields[0]
        if status.startswith("R"):
            previous, path = fields[1:]
            entry = {"path": path, "change_type": "renamed",
                     "before_hash": _sha(_blob(root, base, previous)),
                     "after_hash": _sha(_blob(root, containing, path)),
                     "previous_path": previous}
        else:
            if status not in {"A", "M", "D"}:
                raise CorrectionError(f"unsupported Git status: {status}")
            path = fields[1]
            entry = {"path": path, "change_type": {"A":"added","M":"modified","D":"deleted"}[status],
                     "before_hash": None if status == "A" else _sha(_blob(root, base, path)),
                     "after_hash": None if status == "D" else _sha(_blob(root, containing, path)),
                     "previous_path": None}
        if entry["path"] != excluded_path:
            inventory.append(entry)
    return sorted(inventory, key=lambda item: item["path"])


def classify_inventory(recorded, verified):
    recorded = sorted(recorded, key=lambda item: item["path"])
    verified = sorted(verified, key=lambda item: item["path"])
    recorded_by_path = {item["path"]: item for item in recorded}
    verified_by_path = {item["path"]: item for item in verified}
    missing = [verified_by_path[path] for path in sorted(set(verified_by_path)-set(recorded_by_path))]
    unexpected = [recorded_by_path[path] for path in sorted(set(recorded_by_path)-set(verified_by_path))]
    mismatched = [{"path": path, "recorded": recorded_by_path[path], "verified": verified_by_path[path]}
                  for path in sorted(set(recorded_by_path)&set(verified_by_path))
                  if recorded_by_path[path] != verified_by_path[path]]
    return missing, unexpected, mismatched


def build_correction(root=ROOT, verified_at="2026-07-17T14:45:00Z"):
    manifest = json.loads(_blob(root, TARGET_COMMIT, TARGET_MANIFEST))
    verified = git_inventory(root, TARGET_BASE, TARGET_COMMIT, TARGET_MANIFEST)
    recorded = sorted(manifest["changed_files"], key=lambda item: item["path"])
    missing, unexpected, mismatched = classify_inventory(recorded, verified)
    return {
        "schema_version": "1.0.0",
        "correction_id": "qm2-p0-009-changed-files-correction-v1",
        "target_run_id": TARGET_RUN_ID,
        "target_base_commit": TARGET_BASE,
        "target_containing_commit": TARGET_COMMIT,
        "target_field": "changed_files",
        "verification_method": "git_commit_diff_and_blob_sha256",
        "recorded_entry_count": len(recorded), "verified_entry_count": len(verified),
        "recorded_paths": [item["path"] for item in recorded],
        "actual_paths": [item["path"] for item in verified],
        "missing_entries": missing, "unexpected_entries": unexpected,
        "mismatched_entries": mismatched, "verified_inventory": verified,
        "verified_inventory_sha256": canonical_inventory_hash(verified),
        "effect": "evidence_correction_only", "promotion_effect": "none",
        "immutable_target_report_sha256": _sha(_blob(root, TARGET_COMMIT, TARGET_REPORT)),
        "immutable_target_manifest_sha256": _sha(_blob(root, TARGET_COMMIT, TARGET_MANIFEST)),
        "candidate_lock_id": "fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b",
        "exposure_ledger_id": "rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff",
        "protocol_id": "fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867",
        "watermark_id": "fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248",
        "registry_snapshot_id": "frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5",
        "verified_at": verified_at,
    }


def validate_correction(payload, root=ROOT):
    try:
        from jsonschema import Draft202012Validator
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(payload)
    except Exception as exc:
        raise CorrectionError("correction schema validation failed") from exc
    expected = build_correction(root, payload["verified_at"])
    if payload != expected:
        raise CorrectionError("correction differs from immutable Git evidence")
    return payload


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(rendered); temporary = Path(handle.name)
    temporary.replace(path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate","validate","inspect"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args=parser.parse_args(argv)
    if args.command == "generate":
        payload=build_correction(); _write(args.output,payload)
    else:
        payload=validate_correction(json.loads(args.output.read_text()))
    summary={"correction_id":payload["correction_id"],"recorded_entry_count":payload["recorded_entry_count"],
             "verified_entry_count":payload["verified_entry_count"],"missing_count":len(payload["missing_entries"]),
             "unexpected_count":len(payload["unexpected_entries"]),"mismatched_count":len(payload["mismatched_entries"]),
             "verified_inventory_sha256":payload["verified_inventory_sha256"],"valid":True}
    print(json.dumps(summary,indent=2,sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
