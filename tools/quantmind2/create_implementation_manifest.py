#!/usr/bin/env python3
"""Create, finalize, and validate QuantMind Implementation Manifest v2."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.api.project_knowledge.indexing.domain_bundle import (  # noqa: E402
    DomainBundleBuilder,
)
from backend.services.api.project_knowledge.indexing.errors import (  # noqa: E402
    ImplementationIndexError,
    ManifestParseError,
)
from backend.services.api.project_knowledge.indexing.manifest_v2 import (  # noqa: E402
    CANONICALIZATION_VERSION,
    CHANGED_FILE_IDENTITY_VERSION,
    CHANGED_SYMBOL_IDENTITY_VERSION,
    MANIFEST_V2_SCHEMA_VERSION,
    MAPPER_CONTRACT_VERSION,
    finalize_manifest_v2_payload,
    validate_manifest_v2_payload,
)
from backend.services.api.project_knowledge.indexing.models import (  # noqa: E402
    RepositoryBinding,
)


def _load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestParseError("input is not readable UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ManifestParseError("Manifest input root must be an object")
    return value


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    temporary.replace(path)


def new_draft(source: dict) -> dict:
    """Add only protocol constants and hash placeholders; never infer semantics."""
    payload = copy.deepcopy(source)
    payload.setdefault("schema_version", MANIFEST_V2_SCHEMA_VERSION)
    payload.setdefault("mapper_contract_version", MAPPER_CONTRACT_VERSION)
    payload.setdefault(
        "identity_versions",
        {
            "changed_file": CHANGED_FILE_IDENTITY_VERSION,
            "changed_symbol": CHANGED_SYMBOL_IDENTITY_VERSION,
        },
    )
    if "run" not in payload or not isinstance(payload["run"], dict):
        raise ManifestParseError("new requires an explicit structured Run object")
    payload["run"].setdefault("manifest_schema_version", MANIFEST_V2_SCHEMA_VERSION)
    payload["run"].setdefault("result_commit", None)
    payload["run"].setdefault("source_bundle_hash", "0" * 64)
    payload["run"].setdefault("git_diff_hash", "0" * 64)
    if "integrity" not in payload or not isinstance(payload["integrity"], dict):
        raise ManifestParseError("new requires explicit integrity Git path inventories")
    payload["integrity"].setdefault("canonicalization_version", CANONICALIZATION_VERSION)
    for field in (
        "report_sha256", "manifest_payload_sha256", "source_bundle_sha256",
        "git_diff_sha256",
    ):
        payload["integrity"].setdefault(field, "0" * 64)
    payload["integrity"].setdefault("artifact_hashes", [])
    return payload


def validate_for_production(payload: dict, *, repository_id: str, repository_path: Path):
    validate_manifest_v2_payload(payload)
    if payload["repository"]["repository_id"] != repository_id:
        raise ManifestParseError("producer repository ID differs from Manifest")
    binding = RepositoryBinding(repository_id, repository_path.resolve())
    return DomainBundleBuilder(binding).build_source_v2(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new")
    new.add_argument("--input", required=True, type=Path)
    new.add_argument("--output", required=True, type=Path)
    finalize = commands.add_parser("finalize-payload")
    finalize.add_argument("--manifest", required=True, type=Path)
    finalize.add_argument("--report", required=True, type=Path)
    finalize.add_argument("--repository-root", required=True, type=Path)
    validate = commands.add_parser("validate")
    validate.add_argument("--manifest", required=True, type=Path)
    validate.add_argument("--repository-id", required=True)
    validate.add_argument("--repository-path", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "new":
            _write(args.output, new_draft(_load(args.input)))
            result = {"status": "draft_created", "path": str(args.output)}
        elif args.command == "finalize-payload":
            payload = finalize_manifest_v2_payload(
                _load(args.manifest),
                report_bytes=args.report.read_bytes(),
                repository_root=args.repository_root,
            )
            _write(args.manifest, payload)
            result = {
                "status": "payload_finalized",
                "path": str(args.manifest),
                "result_commit": payload["run"]["result_commit"],
            }
        else:
            bundle = validate_for_production(
                _load(args.manifest),
                repository_id=args.repository_id,
                repository_path=args.repository_path,
            )
            result = {
                "status": "valid",
                "schema_version": MANIFEST_V2_SCHEMA_VERSION,
                "run_id": bundle.run.implementation_run_id,
                "domain_object_families": 11,
            }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ImplementationIndexError, OSError, ValueError) as exc:
        message = exc.message if isinstance(exc, ImplementationIndexError) else str(exc)
        print(json.dumps({"status": "error", "message": message}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
