"""Pure Manifest v2 integrity, version, and structural helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping

from tools.quantmind2.validate_context_bootstrap import ValidationError, validate_instance

from .errors import ManifestParseError, UnsupportedManifestSchemaError


MANIFEST_V2_SCHEMA_VERSION = "2.0.0"
MAPPER_CONTRACT_VERSION = "1.0.0"
CHANGED_FILE_IDENTITY_VERSION = "changed-file-v1"
CHANGED_SYMBOL_IDENTITY_VERSION = "changed-symbol-v1"
CANONICALIZATION_VERSION = "implementation-manifest-v2-canonical-json-v1"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[5]
    / "docs/quantmind2/implementation/schemas/implementation_manifest_v2.schema.json"
)
_URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def canonical_manifest_v2_bytes(payload: Mapping[str, Any]) -> bytes:
    """Canonical UTF-8 JSON excluding only the self-referential payload hash."""
    normalized = copy.deepcopy(dict(payload))
    integrity = normalized.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("manifest_payload_sha256", None)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_manifest_v2_payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_manifest_v2_bytes(payload)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_manifest_v2_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_manifest_v2_payload(payload: Mapping[str, Any]) -> None:
    """Apply Schema plus cross-object and version constraints."""
    if payload.get("schema_version") != MANIFEST_V2_SCHEMA_VERSION:
        raise UnsupportedManifestSchemaError("manifest schema version is unsupported")
    if payload.get("mapper_contract_version") != MAPPER_CONTRACT_VERSION:
        raise UnsupportedManifestSchemaError("Mapper contract version is unsupported")
    if payload.get("identity_versions") != {
        "changed_file": CHANGED_FILE_IDENTITY_VERSION,
        "changed_symbol": CHANGED_SYMBOL_IDENTITY_VERSION,
    }:
        raise UnsupportedManifestSchemaError("technical identity version is unsupported")
    raw_integrity = payload.get("integrity")
    if isinstance(raw_integrity, Mapping) and raw_integrity.get(
        "canonicalization_version"
    ) != CANONICALIZATION_VERSION:
        raise UnsupportedManifestSchemaError("Manifest canonicalization version is unsupported")
    try:
        validate_instance(dict(payload), load_manifest_v2_schema())
    except ValidationError as exc:
        raise ManifestParseError("manifest does not conform to schema v2") from exc

    repository = payload["repository"]
    task = payload["task"]
    run = payload["run"]
    integrity = payload["integrity"]
    if run["task_id"] != task["task_id"]:
        raise ManifestParseError("Run task_id differs from Task identity")
    for field in ("repository_id", "branch", "base_commit"):
        if run[field] != repository[field]:
            raise ManifestParseError(f"Run {field} differs from Repository evidence")
    if run["manifest_schema_version"] != payload["schema_version"]:
        raise ManifestParseError("Run manifest schema version differs from top-level version")
    run_id = run["implementation_run_id"]
    for relationship in payload["relationships"]:
        if relationship["source_run_id"] != run_id:
            raise ManifestParseError("Relationship source must be the current Run")
    for artifact in payload["artifacts"]:
        location = artifact["path_or_uri"]
        if artifact["location_kind"] == "repository_path":
            path = PurePosixPath(location)
            if path.is_absolute() or ".." in path.parts or _URI_RE.match(location):
                raise ManifestParseError("repository artifact location is invalid")
        elif not _URI_RE.match(location):
            raise ManifestParseError("URI artifact location is invalid")
    declared_artifact_hashes = {
        item["artifact_id"]: item["sha256"] for item in integrity["artifact_hashes"]
    }
    actual_artifact_hashes = {
        item["artifact_id"]: item["content_hash"]
        for item in payload["artifacts"]
        if item["content_hash"] is not None
    }
    if declared_artifact_hashes != actual_artifact_hashes:
        raise ManifestParseError("integrity artifact hashes differ from Artifact records")
    if run["source_bundle_hash"] != integrity["source_bundle_sha256"]:
        raise ManifestParseError("Run source bundle hash differs from integrity")
    if run["git_diff_hash"] != integrity["git_diff_sha256"]:
        raise ManifestParseError("Run Git diff hash differs from integrity")
    if canonical_manifest_v2_payload_hash(payload) != integrity["manifest_payload_sha256"]:
        raise ManifestParseError("Manifest v2 payload hash is invalid")


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def finalize_manifest_v2_payload(
    payload: Mapping[str, Any], *, report_bytes: bytes, repository_root: Path
) -> dict[str, Any]:
    """Finalize deterministic pre-commit integrity without inventing a result commit."""
    finalized = copy.deepcopy(dict(payload))
    if finalized.get("schema_version") != MANIFEST_V2_SCHEMA_VERSION:
        raise UnsupportedManifestSchemaError("finalize-payload requires Manifest v2")
    run = finalized["run"]
    if run.get("result_commit") is not None:
        raise ManifestParseError("pre-commit producer must not set result_commit")
    if run.get("task_status") not in {
        "running", "completed_uncommitted", "partial_uncommitted", "failed", "blocked", "cancelled"
    }:
        raise ManifestParseError("pre-commit producer received a committed Run status")
    root = repository_root.resolve()
    integrity = finalized["integrity"]
    report_hash = sha256_bytes(report_bytes)
    integrity["report_sha256"] = report_hash

    artifact_hashes: list[dict[str, str]] = []
    for artifact in finalized["artifacts"]:
        if artifact["location_kind"] != "repository_path":
            continue
        path = PurePosixPath(artifact["path_or_uri"])
        if path.as_posix() == run["manifest_path"]:
            artifact["content_hash"] = None
            artifact["size_bytes"] = None
            continue
        local = (root / path.as_posix()).resolve()
        if root not in local.parents and local != root:
            raise ManifestParseError("artifact escapes repository root")
        data = report_bytes if path.as_posix() == run["report_path"] else local.read_bytes()
        artifact["content_hash"] = sha256_bytes(data)
        artifact["size_bytes"] = len(data)
        artifact_hashes.append(
            {"artifact_id": artifact["artifact_id"], "sha256": artifact["content_hash"]}
        )
    integrity["artifact_hashes"] = sorted(artifact_hashes, key=lambda item: item["artifact_id"])

    source_records: list[dict[str, Any]] = []
    for path_text in sorted(integrity["git_changed_paths"]):
        if path_text == run["manifest_path"]:
            source_records.append({"path": path_text, "sha256": None, "kind": "manifest_payload"})
            continue
        local = (root / path_text).resolve()
        if path_text in integrity["git_deleted_paths"]:
            source_records.append({"path": path_text, "sha256": None, "kind": "deleted"})
        else:
            data = report_bytes if path_text == run["report_path"] else local.read_bytes()
            source_records.append({"path": path_text, "sha256": sha256_bytes(data), "kind": "file"})
    source_bundle_hash = canonical_json_hash(source_records)
    git_diff_hash = canonical_json_hash(
        {
            "changed": integrity["git_changed_paths"],
            "added": integrity["git_added_paths"],
            "deleted": integrity["git_deleted_paths"],
            "domain_changed_files": finalized["changed_files"],
        }
    )
    integrity["source_bundle_sha256"] = source_bundle_hash
    integrity["git_diff_sha256"] = git_diff_hash
    run["source_bundle_hash"] = source_bundle_hash
    run["git_diff_hash"] = git_diff_hash
    integrity["manifest_payload_sha256"] = "0" * 64
    integrity["manifest_payload_sha256"] = canonical_manifest_v2_payload_hash(finalized)
    validate_manifest_v2_payload(finalized)
    return finalized
