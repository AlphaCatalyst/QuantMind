"""Strict version-routed parser for committed Implementation Manifests."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from tools.quantmind2.validate_context_bootstrap import (
    ValidationError,
    validate_instance,
)

from .errors import ManifestParseError, UnsupportedManifestSchemaError
from .manifest_v2 import MANIFEST_V2_SCHEMA_VERSION, validate_manifest_v2_payload
from .models import ParsedImplementationManifest


SUPPORTED_MANIFEST_SCHEMAS = frozenset({"1.0.0", MANIFEST_V2_SCHEMA_VERSION})
RUNS_PREFIX = PurePosixPath("docs/quantmind2/implementation/runs")
V1_SCHEMA_PATH = (
    Path(__file__).resolve().parents[5]
    / "docs/quantmind2/implementation/schemas/implementation_manifest_v1.schema.json"
)


def _safe_path(value: str, *, field: str, run_id: str | None = None) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ManifestParseError("repository path is invalid", run_id=run_id, check=field)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestParseError("repository path is invalid", run_id=run_id, check=field)
    return path


class ImplementationManifestParser:
    """Validate JSON shape exactly; never repair or enrich source fields."""

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        if schema is None:
            schema = json.loads(V1_SCHEMA_PATH.read_text(encoding="utf-8"))
        self._v1_schema = schema

    def parse(
        self,
        manifest_bytes: bytes,
        *,
        manifest_path: str,
        directory_run_id: str,
    ) -> ParsedImplementationManifest:
        try:
            payload = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManifestParseError("manifest is not valid UTF-8 JSON", run_id=directory_run_id) from exc
        if not isinstance(payload, dict):
            raise ManifestParseError("manifest root must be an object", run_id=directory_run_id)
        version = payload.get("schema_version", payload.get("manifest_schema_version"))
        if version not in SUPPORTED_MANIFEST_SCHEMAS:
            raise UnsupportedManifestSchemaError(
                "manifest schema version is unsupported",
                run_id=directory_run_id,
                check="schema_version",
            )
        if version == "1.0.0":
            try:
                validate_instance(payload, self._v1_schema)
            except ValidationError as exc:
                raise ManifestParseError(
                    "manifest does not conform to schema v1", run_id=directory_run_id
                ) from exc
            run = payload
            run_id = payload["implementation_run_id"]
            source_status = payload["task_status"]
        else:
            try:
                # Committed v2 payloads are parsed losslessly. Git evidence and
                # Domain mapping apply the narrow legacy carrier compatibility
                # rule; producer/standalone validation remains strict.
                validate_manifest_v2_payload(payload, allow_legacy_self_reference=True)
            except (ManifestParseError, UnsupportedManifestSchemaError) as exc:
                if exc.run_id is None:
                    exc.run_id = directory_run_id
                raise
            run = payload["run"]
            run_id = run["implementation_run_id"]
            source_status = run["task_status"]
        if run_id != directory_run_id:
            raise ManifestParseError("run directory and manifest ID differ", run_id=directory_run_id)
        manifest = _safe_path(manifest_path, field="manifest_path", run_id=run_id)
        declared_manifest = _safe_path(run["manifest_path"], field="manifest_path", run_id=run_id)
        expected_dir = RUNS_PREFIX / manifest.parts[-4] / manifest.parts[-3] / run_id
        if manifest.name != "manifest.json" or manifest.parent != expected_dir:
            raise ManifestParseError("manifest location is outside the canonical Run layout", run_id=run_id)
        if declared_manifest != manifest:
            raise ManifestParseError("declared manifest path differs from Git path", run_id=run_id)
        report = _safe_path(run["report_path"], field="report_path", run_id=run_id)
        if report != manifest.parent / "report.md":
            raise ManifestParseError("declared report path differs from paired Run report", run_id=run_id)
        return ParsedImplementationManifest(
            run_id=run_id,
            manifest_path=manifest.as_posix(),
            report_path=report.as_posix(),
            source_status=source_status,
            payload=payload,
        )
