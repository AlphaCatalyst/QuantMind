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


def _current() -> tuple[Path, dict]:
    path = MANIFESTS[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_parser_accepts_current_v1_without_enrichment() -> None:
    path, payload = _current()
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
        (lambda value: value.update(manifest_schema_version="2.0.0"), UnsupportedManifestSchemaError),
        (lambda value: value.pop("task_id"), ManifestParseError),
        (lambda value: value.update(task_status="invented"), ManifestParseError),
    ],
)
def test_parser_rejects_unsupported_or_invalid_manifest(mutation, error) -> None:  # noqa: ANN001
    path, payload = _current()
    mutation(payload)
    relative = path.relative_to(ROOT).as_posix()
    with pytest.raises(error):
        ImplementationManifestParser().parse(
            json.dumps(payload).encode(),
            manifest_path=relative,
            directory_run_id=path.parent.name,
        )


def test_parser_rejects_malformed_json_and_path_mismatch() -> None:
    path, payload = _current()
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
    path, payload = _current()
    payload["report_path"] = "../report.md"
    with pytest.raises(ManifestParseError):
        ImplementationManifestParser().parse(
            json.dumps(payload).encode(),
            manifest_path=path.relative_to(ROOT).as_posix(),
            directory_run_id=path.parent.name,
        )
