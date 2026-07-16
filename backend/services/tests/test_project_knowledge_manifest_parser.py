from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.api.project_knowledge.indexing import (
    ImplementationManifestParser,
    ManifestParseError,
    UnsupportedManifestSchemaError,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFESTS = sorted(
    (ROOT / "docs/quantmind2/implementation/runs").glob("*/*/*/manifest.json")
)


def _current_v1() -> tuple[Path, dict]:
    for path in reversed(MANIFESTS):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("manifest_schema_version") == "1.0.0":
            return path, payload
    raise AssertionError("historical Manifest v1 fixture is missing")


def test_parser_accepts_current_v1_without_enrichment() -> None:
    path, payload = _current_v1()
    relative = path.relative_to(ROOT).as_posix()
    parsed = ImplementationManifestParser().parse(
        path.read_bytes(),
        manifest_path=relative,
        directory_run_id=payload["implementation_run_id"],
    )
    assert parsed.payload == payload
    assert parsed.source_status == payload["task_status"]
    assert "status" not in parsed.payload.get("task", {})


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda value: value.update(manifest_schema_version="3.0.0"), UnsupportedManifestSchemaError),
        (lambda value: value.pop("task_id"), ManifestParseError),
        (lambda value: value.update(task_status="invented"), ManifestParseError),
    ],
)
def test_parser_rejects_unsupported_or_invalid_manifest(mutation, error) -> None:  # noqa: ANN001
    path, payload = _current_v1()
    mutation(payload)
    relative = path.relative_to(ROOT).as_posix()
    with pytest.raises(error):
        ImplementationManifestParser().parse(
            json.dumps(payload).encode(),
            manifest_path=relative,
            directory_run_id=path.parent.name,
        )


def test_parser_rejects_malformed_json_and_path_mismatch() -> None:
    path, payload = _current_v1()
    relative = path.relative_to(ROOT).as_posix()
    with pytest.raises(ManifestParseError):
        ImplementationManifestParser().parse(
            b"{",
            manifest_path=relative,
            directory_run_id=path.parent.name,
        )
    payload["implementation_run_id"] = "QM2-P0-999-20260715T000000Z-abcdef0"
    with pytest.raises(ManifestParseError):
        ImplementationManifestParser().parse(
            json.dumps(payload).encode(),
            manifest_path=relative,
            directory_run_id=path.parent.name,
        )


def test_parser_rejects_malicious_declared_path() -> None:
    path, payload = _current_v1()
    payload["report_path"] = "../report.md"
    with pytest.raises(ManifestParseError):
        ImplementationManifestParser().parse(
            json.dumps(payload).encode(),
            manifest_path=path.relative_to(ROOT).as_posix(),
            directory_run_id=path.parent.name,
        )
