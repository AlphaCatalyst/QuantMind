"""Database-free contract tests for the explicit Ledger migration system."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from tools.quantmind2 import ledger_migrations as migrations


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "data/migrations/quantmind2/manifest.json"


def copy_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(MANIFEST.parent, target)
    return target / "manifest.json"


def test_official_manifest_and_exact_byte_checksums_are_valid() -> None:
    raw, entries = migrations.load_manifest(MANIFEST)
    assert raw["checksum_algorithm"] == "sha256-exact-file-bytes"
    assert [entry["version"] for entry in entries] == ["0001"]
    for entry in entries:
        assert hashlib.sha256(entry["up_file"].read_bytes()).hexdigest() == entry["up_checksum"]
        assert hashlib.sha256(entry["down_file"].read_bytes()).hexdigest() == entry["down_checksum"]


def test_plan_is_database_free_and_contains_stable_identity(capsys: pytest.CaptureFixture[str]) -> None:
    assert migrations.main(["plan", "--manifest", str(MANIFEST)]) == 0
    output = capsys.readouterr().out
    assert "0001 implementation_ledger" in output
    assert "up_path=0001_implementation_ledger.up.sql" in output


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw["migrations"].append(dict(raw["migrations"][0])), "unique and sorted"),
        (lambda raw: raw["migrations"][0].update({"up_path": "../escape.sql"}), "escapes"),
        (lambda raw: raw["migrations"][0].update({"version": "x001"}), "four decimal"),
        (lambda raw: raw.update({"schema": "public"}), "unsupported schema"),
    ],
)
def test_manifest_rejects_duplicate_unsafe_or_invalid_metadata(tmp_path: Path, mutation, message: str) -> None:
    manifest = copy_bundle(tmp_path)
    raw = json.loads(manifest.read_text())
    mutation(raw)
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(migrations.MigrationError, match=message):
        migrations.load_manifest(manifest)


def test_checksum_drift_is_rejected(tmp_path: Path) -> None:
    manifest = copy_bundle(tmp_path)
    up = manifest.parent / "0001_implementation_ledger.up.sql"
    up.write_bytes(up.read_bytes() + b"\n-- drift\n")
    with pytest.raises(migrations.MigrationError, match="checksum drift"):
        migrations.load_manifest(manifest)


def test_missing_pair_and_non_utf8_are_rejected(tmp_path: Path) -> None:
    manifest = copy_bundle(tmp_path)
    (manifest.parent / "0001_implementation_ledger.down.sql").unlink()
    with pytest.raises(migrations.MigrationError, match="missing"):
        migrations.load_manifest(manifest)

    manifest = copy_bundle(tmp_path / "second")
    up = manifest.parent / "0001_implementation_ledger.up.sql"
    up.write_bytes(b"\xff")
    raw = json.loads(manifest.read_text())
    raw["migrations"][0]["up_checksum"] = hashlib.sha256(b"\xff").hexdigest()
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(migrations.MigrationError, match="UTF-8"):
        migrations.load_manifest(manifest)


def test_sql_scope_has_exact_inventory_and_no_forbidden_behavior() -> None:
    _, entries = migrations.load_manifest(MANIFEST)
    up = entries[0]["up_sql"].lower()
    down = entries[0]["down_sql"].lower()
    assert "quantmind2._schema_migrations" in up
    assert "cascade" not in up + down
    assert " trigger " not in up + down
    assert "public." not in up + down
    assert "canonical_status" in up
    assert "create trigger" not in up
    assert "drop schema quantmind2;" in down
    for table in migrations.BUSINESS_TABLES:
        assert up.count(f"create table quantmind2.{table} (") == 1
        assert down.count(f"drop table quantmind2.{table};") == 1


def test_down_requires_explicit_destructive_gate() -> None:
    _, entries = migrations.load_manifest(MANIFEST)
    args = migrations.build_parser().parse_args(["down"])
    with pytest.raises(migrations.MigrationError, match="--allow-destructive"):
        migrations.down(args, entries)


def test_connection_argv_is_a_list_and_contains_no_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PGPASSWORD", "never-print-this")
    args = migrations.build_parser().parse_args(
        ["status", "--host", "127.0.0.1", "--port", "5432", "--database", "isolated", "--username", "tester"]
    )
    argv = migrations._psql_argv(args)
    assert isinstance(argv, list)
    assert "never-print-this" not in " ".join(argv)
    assert "isolated" in argv and "tester" in argv


def test_orm_and_migration_static_table_inventory_match() -> None:
    from backend.services.api.models.base import Base
    import backend.services.api.project_knowledge.persistence.orm_annotation_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_detail_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_reference_models  # noqa: F401

    actual = {table.name for table in Base.metadata.tables.values() if table.schema == "quantmind2"}
    assert actual == set(migrations.BUSINESS_TABLES)
