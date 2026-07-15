"""Strict parser for committed Implementation Manifest v1 blobs."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from tools.quantmind2.validate_context_bootstrap import (
    ValidationError,
    validate_instance,
)

from .errors import ManifestParseError, UnsupportedManifestSchemaError
from .models import ParsedImplementationManifest


SUPPORTED_MANIFEST_SCHEMAS = frozenset({"1.0.0"})
RUNS_PREFIX = PurePosixPath("docs/quantmind2/implementation/runs")
SCHEMA_PATH = (
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
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self._schema = schema

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
        version = payload.get("manifest_schema_version")
        if version not in SUPPORTED_MANIFEST_SCHEMAS:
            raise UnsupportedManifestSchemaError(
                "manifest schema version is unsupported",
                run_id=directory_run_id,
                check="manifest_schema_version",
            )
        try:
            validate_instance(payload, self._schema)
        except ValidationError as exc:
            raise ManifestParseError("manifest does not conform to schema v1", run_id=directory_run_id) from exc
        run_id = payload["implementation_run_id"]
        if run_id != directory_run_id:
            raise ManifestParseError("run directory and manifest ID differ", run_id=directory_run_id)
        manifest = _safe_path(manifest_path, field="manifest_path", run_id=run_id)
        declared_manifest = _safe_path(payload["manifest_path"], field="manifest_path", run_id=run_id)
        expected_dir = RUNS_PREFIX / manifest.parts[-4] / manifest.parts[-3] / run_id
        if manifest.name != "manifest.json" or manifest.parent != expected_dir:
            raise ManifestParseError("manifest location is outside the canonical Run layout", run_id=run_id)
        if declared_manifest != manifest:
            raise ManifestParseError("declared manifest path differs from Git path", run_id=run_id)
        report = _safe_path(payload["report_path"], field="report_path", run_id=run_id)
        if report != manifest.parent / "report.md":
            raise ManifestParseError("declared report path differs from paired Run report", run_id=run_id)
        return ParsedImplementationManifest(
            run_id=run_id,
            manifest_path=manifest.as_posix(),
            report_path=report.as_posix(),
            source_status=payload["task_status"],
            payload=payload,
        )
