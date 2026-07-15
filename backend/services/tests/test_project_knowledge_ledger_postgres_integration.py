"""Real PostgreSQL migration, catalog parity, constraint, and rollback test.

Set QM2_LEDGER_POSTGRES_INTEGRATION=1 to allow this test to create and remove a
disposable postgres:15-alpine container with no volume mounts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

import pytest
from sqlalchemy import BigInteger, Boolean, CHAR, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from tools.quantmind2 import ledger_migrations as migrations


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "data/migrations/quantmind2/manifest.json"
RUNNER = ROOT / "tools/quantmind2/ledger_migrations.py"
PYTHON = os.environ.get("QM2_TEST_PYTHON", os.sys.executable)
pytestmark = pytest.mark.skipif(
    os.environ.get("QM2_LEDGER_POSTGRES_INTEGRATION") != "1",
    reason="requires explicit disposable PostgreSQL opt-in",
)


def _run(argv: list[str], *, env: dict[str, str], sql: str | None = None, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, input=sql, text=True, capture_output=True, env=env, check=False)
    if ok and result.returncode:
        raise AssertionError(f"command failed ({result.returncode}): {result.stderr}")
    if not ok and result.returncode == 0:
        raise AssertionError("command unexpectedly succeeded")
    return result


def _docker(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *args], env=os.environ.copy(), ok=ok)


def _runner(connection: list[str], env: dict[str, str], command: str, *extra: str, ok: bool = True):
    return _run([PYTHON, str(RUNNER), command, *connection, *extra], env=env, ok=ok)


def _psql(connection: list[str], env: dict[str, str], sql: str, *, ok: bool = True):
    return _run(["psql", *connection, "-X", "--no-psqlrc", "-qAt", "-v", "ON_ERROR_STOP=1"], env=env, sql=sql, ok=ok)


def _load_orm_tables():
    from backend.services.api.models.base import Base
    import backend.services.api.project_knowledge.persistence.orm_annotation_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_detail_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_models  # noqa: F401
    import backend.services.api.project_knowledge.persistence.orm_reference_models  # noqa: F401
    return {table.name: table for table in Base.metadata.tables.values() if table.schema == "quantmind2"}


def _expected_type(column) -> tuple[str, int | None]:
    typ = column.type
    if isinstance(typ, JSONB): return "jsonb", None
    if isinstance(typ, CHAR): return "bpchar", typ.length
    if isinstance(typ, Text): return "text", None
    if isinstance(typ, String): return "varchar", typ.length
    if isinstance(typ, Boolean): return "bool", None
    if isinstance(typ, BigInteger): return "int8", None
    if isinstance(typ, Integer): return "int4", None
    if isinstance(typ, DateTime) and typ.timezone: return "timestamptz", None
    raise AssertionError(f"unmapped ORM type: {typ!r}")


def _assert_catalog_parity(connection: list[str], env: dict[str, str]) -> dict[str, int]:
    tables = _load_orm_tables()
    actual_tables = set(_psql(connection, env, "SELECT table_name FROM information_schema.tables WHERE table_schema='quantmind2' AND table_type='BASE TABLE' ORDER BY 1;").stdout.splitlines())
    assert actual_tables == set(tables) | {"_schema_migrations"}

    column_rows = _psql(connection, env, """
SELECT table_name || E'\\t' || column_name || E'\\t' || udt_name || E'\\t' || is_nullable || E'\\t' || COALESCE(character_maximum_length::text,'') || E'\\t' || COALESCE(column_default,'')
FROM information_schema.columns WHERE table_schema='quantmind2' AND table_name <> '_schema_migrations' ORDER BY table_name, ordinal_position;
""").stdout.splitlines()
    actual_columns = {}
    for row in column_rows:
        table, name, typ, nullable, length, default = row.split("\t")
        actual_columns[(table, name)] = (typ, nullable == "YES", int(length) if length else None, default)
    expected_columns = {(table.name, col.name) for table in tables.values() for col in table.columns}
    assert set(actual_columns) == expected_columns
    for table in tables.values():
        for col in table.columns:
            typ, nullable, length, default = actual_columns[(table.name, col.name)]
            assert (typ, length) == _expected_type(col)
            assert nullable == col.nullable
            expected_default = str(col.server_default.arg) if col.server_default is not None else ""
            if expected_default:
                assert default.strip("()") == expected_default
            else:
                assert default == ""

    constraint_rows = _psql(connection, env, """
SELECT c.relname || E'\\t' || con.conname || E'\\t' || con.contype::text || E'\\t' || COALESCE(rc.relname,'') || E'\\t' || con.confdeltype::text
FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
LEFT JOIN pg_class rc ON rc.oid=con.confrelid
WHERE n.nspname='quantmind2' AND c.relname <> '_schema_migrations' ORDER BY c.relname, con.conname;
""").stdout.splitlines()
    actual_constraints = {}
    for row in constraint_rows:
        table, name, kind, target, delete = row.split("\t")
        actual_constraints[(table, name)] = (kind, target, delete)
    expected_names = {(table.name, c.name) for table in tables.values() for c in table.constraints}
    assert set(actual_constraints) == expected_names
    for table in tables.values():
        for constraint in table.constraints:
            kind, target, delete = actual_constraints[(table.name, constraint.name)]
            expected_kind = {"PrimaryKeyConstraint": "p", "UniqueConstraint": "u", "CheckConstraint": "c", "ForeignKeyConstraint": "f"}[type(constraint).__name__]
            assert kind == expected_kind
            if kind == "f":
                element = next(iter(constraint.elements))
                assert target == element.column.table.name
                assert delete == "r"

    index_rows = _psql(connection, env, """
SELECT tbl.relname || E'\\t' || idx.relname || E'\\t' || string_agg(att.attname, ',' ORDER BY keys.ordinality)
FROM pg_index i JOIN pg_class idx ON idx.oid=i.indexrelid JOIN pg_class tbl ON tbl.oid=i.indrelid
JOIN pg_namespace n ON n.oid=tbl.relnamespace
JOIN LATERAL unnest(i.indkey::smallint[]) WITH ORDINALITY keys(attnum, ordinality) ON true
JOIN pg_attribute att ON att.attrelid=tbl.oid AND att.attnum=keys.attnum
WHERE n.nspname='quantmind2' AND tbl.relname <> '_schema_migrations'
AND NOT EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid=i.indexrelid)
GROUP BY tbl.relname, idx.relname ORDER BY tbl.relname, idx.relname;
""").stdout.splitlines()
    actual_indexes = {}
    for row in index_rows:
        table, name, columns = row.split("\t")
        actual_indexes[(table, name)] = tuple(columns.split(","))
    expected_indexes = {(table.name, idx.name): tuple(col.name for col in idx.columns) for table in tables.values() for idx in table.indexes}
    assert actual_indexes == expected_indexes
    return {"tables": len(tables), "columns": len(expected_columns), "constraints": len(expected_names), "indexes": len(expected_indexes)}


def _valid_rows_sql() -> str:
    h = "a" * 64
    c = "b" * 40
    return f"""
INSERT INTO quantmind2.implementation_tasks VALUES ('task-root',NULL,'任务','目标','["范围"]'::jsonb,'["非目标"]'::jsonb,'running','2026-07-15T00:00:00Z',1);
INSERT INTO quantmind2.implementation_tasks VALUES ('task-child','task-root','Child','Objective','[]'::jsonb,'[]'::jsonb,'completed','2026-07-15T00:00:00Z',1);
INSERT INTO quantmind2.implementation_runs VALUES ('run-1','task-root','/仓库','master','{c}',NULL,'completed_uncommitted','complete','integration_tests',false,true,'2026-07-15T00:00:00Z','2026-07-15T01:00:00Z','codex','1.0.0','docs/清单.json','{h}','docs/报告.md','{h}','{h}','{h}','consistent','candidate',1);
INSERT INTO quantmind2.implementation_runs VALUES ('run-2','task-child','/repo','master','{c}','{c}','completed_committed','complete','integration_tests',false,false,'2026-07-15T00:00:00Z','2026-07-15T01:00:00Z','codex','1.0.0','manifest.json','{h}','report.md','{h}',NULL,NULL,'consistent','canonical',1);
INSERT INTO quantmind2.implementation_run_relationships VALUES ('rel-1','run-2','run-1','finalizes','完成','2026-07-15T01:00:00Z');
INSERT INTO quantmind2.implementation_changed_files VALUES ('file-1','run-1','路径/文件.py','added',NULL,'{h}',NULL);
INSERT INTO quantmind2.implementation_changed_symbols VALUES ('symbol-1','run-1','路径/文件.py','模块.函数','function','added');
INSERT INTO quantmind2.implementation_test_executions VALUES ('test-1','run-1','pytest','验证','passed',1,0,0,NULL,NULL,NULL);
INSERT INTO quantmind2.implementation_artifacts VALUES ('artifact-1','run-1','report','docs/报告.md','{h}','1.0.0',42);
INSERT INTO quantmind2.implementation_component_references VALUES ('run-1','quantmind2.project_knowledge','modified');
INSERT INTO quantmind2.implementation_adr_references VALUES ('run-1','ADR-0005','conforms_to');
INSERT INTO quantmind2.implementation_limitations VALUES ('limit-1','run-1','medium',NULL,'尚无 Repository','open');
INSERT INTO quantmind2.implementation_recommended_tasks VALUES ('recommend-1','run-1','QM2-P0-002A3','P0','实现 Repository');
"""


def _invalid_cases() -> list[tuple[str, str]]:
    h, c = "a" * 64, "b" * 40
    run_prefix = f"'bad','task-root','/repo','master','{c}',NULL"
    return [
        ("INSERT INTO quantmind2.implementation_tasks VALUES ('bad-status',NULL,'t','o','[]','[]','bogus',now(),1);", "ck_qm2_tasks_status"),
        ("INSERT INTO quantmind2.implementation_tasks VALUES ('bad-version',NULL,'t','o','[]','[]','planned',now(),0);", "ck_qm2_tasks_version_positive"),
        (f"INSERT INTO quantmind2.implementation_runs VALUES ('missing-task','absent','/r','m','{c}',NULL,'running','none','not_verified',false,false,now(),NULL,'a','1','m',NULL,'r',NULL,NULL,NULL,'unverified','noncanonical',1);", "fk_qm2_runs_task"),
        (f"INSERT INTO quantmind2.implementation_runs VALUES ({run_prefix},'completed_committed','complete','integration_tests',false,false,now(),now(),'a','1','m',NULL,'r',NULL,NULL,NULL,'consistent','candidate',1);", "ck_qm2_runs_committed_result"),
        (f"INSERT INTO quantmind2.implementation_runs VALUES ('bad-canonical','task-root','/r','m','{c}',NULL,'completed_uncommitted','complete','integration_tests',false,false,now(),now(),'a','1','m',NULL,'r',NULL,NULL,NULL,'consistent','canonical',1);", "ck_qm2_runs_canonical_gate"),
        (f"INSERT INTO quantmind2.implementation_runs VALUES ('bad-time','task-root','/r','m','{c}',NULL,'completed_uncommitted','complete','integration_tests',false,false,'2026-07-15T02:00Z','2026-07-15T01:00Z','a','1','m',NULL,'r',NULL,NULL,NULL,'consistent','candidate',1);", "ck_qm2_runs_time_order"),
        ("INSERT INTO quantmind2.implementation_run_relationships VALUES ('self','run-1','run-1','continues','x',now());", "ck_qm2_rels_distinct_runs"),
        ("INSERT INTO quantmind2.implementation_run_relationships VALUES ('rel-dup','run-2','run-1','finalizes','x',now());", "uq_qm2_rels_source_target_type"),
        (f"INSERT INTO quantmind2.implementation_changed_files VALUES ('bad-file','run-1','x','added','{h}','{h}',NULL);", "ck_qm2_files_added_shape"),
        ("INSERT INTO quantmind2.implementation_changed_symbols VALUES ('bad-symbol','run-1','x','q','bogus','added');", "ck_qm2_symbols_symbol_type"),
        ("INSERT INTO quantmind2.implementation_test_executions VALUES ('bad-count','run-1','c','p','passed',-1,0,0,NULL,NULL,NULL);", "ck_qm2_tests_counts_nonnegative"),
        ("INSERT INTO quantmind2.implementation_test_executions VALUES ('bad-failed','run-1','c','p','failed',0,0,0,NULL,NULL,NULL);", "ck_qm2_tests_failed_shape"),
        ("INSERT INTO quantmind2.implementation_artifacts VALUES ('bad-artifact','run-1','x','x',NULL,NULL,-1);", "ck_qm2_artifacts_size_nonnegative"),
        ("INSERT INTO quantmind2.implementation_adr_references VALUES ('run-1','bad','documents');", "ck_qm2_adr_refs_id_format"),
        ("INSERT INTO quantmind2.implementation_limitations VALUES ('bad-limit','run-1','low',NULL,' ','open');", "ck_qm2_limitations_description_nonempty"),
        ("INSERT INTO quantmind2.implementation_recommended_tasks VALUES ('bad-rec','run-1','next','P0',' ');", "ck_qm2_recommendations_reason_nonempty"),
        ("DELETE FROM quantmind2.implementation_tasks WHERE task_id='task-root';", "fk_qm2_tasks_parent"),
        ("DELETE FROM quantmind2.implementation_runs WHERE implementation_run_id='run-1';", "fk_qm2_"),
    ]


def test_full_migration_lifecycle_against_disposable_postgresql(tmp_path: Path) -> None:
    if shutil.which("docker") is None or shutil.which("psql") is None:
        pytest.skip("docker and psql are required")
    token = secrets.token_hex(6)
    container = f"qm2-ledger-{token}"
    password = secrets.token_urlsafe(24)
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    docker_env = os.environ.copy()
    docker_env["POSTGRES_PASSWORD"] = password
    started = False
    try:
        _run(
            ["docker", "run", "-d", "--rm", "--name", container, "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=qm2_ledger_test", "-p", "127.0.0.1::5432", "postgres:15-alpine"],
            env=docker_env,
        )
        started = True
        port = _docker("port", container, "5432/tcp").stdout.strip().rsplit(":", 1)[1]
        connection = ["--host", "127.0.0.1", "--port", port, "--username", "postgres", "--dbname", "qm2_ledger_test"]
        runner_connection = ["--host", "127.0.0.1", "--port", port, "--username", "postgres", "--database", "qm2_ledger_test"]
        for _ in range(60):
            probe = subprocess.run(
                ["psql", *connection, "-X", "--no-psqlrc", "-qAt", "-v", "ON_ERROR_STOP=1"],
                input="SELECT 1;", text=True, capture_output=True, env=env, check=False,
            )
            if probe.returncode == 0: break
            time.sleep(0.25)
        else: raise AssertionError("disposable PostgreSQL did not become ready")

        assert _psql(connection, env, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='quantmind2';").stdout.strip() == "0"
        _psql(connection, env, "CREATE TABLE public.qm2_migration_sentinel(id integer PRIMARY KEY);")
        _runner(runner_connection, env, "up")
        status = _runner(runner_connection, env, "status").stdout
        assert "0001 implementation_ledger applied" in status
        counts_first = _assert_catalog_parity(connection, env)
        assert counts_first["tables"] == 11
        _psql(connection, env, _valid_rows_sql())
        for sql, constraint in _invalid_cases():
            failure = _psql(connection, env, f"BEGIN; {sql} COMMIT;", ok=False)
            assert failure.returncode != 0 and constraint in failure.stderr

        _runner(runner_connection, env, "up")
        drift_dir = tmp_path / "drift"
        shutil.copytree(MANIFEST.parent, drift_dir)
        drift_up = drift_dir / "0001_implementation_ledger.up.sql"
        drift_up.write_bytes(drift_up.read_bytes() + b"\n-- intentional test drift\n")
        drift_manifest = drift_dir / "manifest.json"
        raw = json.loads(drift_manifest.read_text())
        raw["migrations"][0]["up_checksum"] = hashlib.sha256(drift_up.read_bytes()).hexdigest()
        drift_manifest.write_text(json.dumps(raw), encoding="utf-8")
        drift = _runner(runner_connection, env, "up", "--manifest", str(drift_manifest), ok=False)
        assert "checksum drift" in drift.stderr

        _psql(connection, env, "CREATE TABLE quantmind2.rollback_guard(id integer);")
        failed_down = _runner(runner_connection, env, "down", "--allow-destructive", ok=False)
        assert "cannot drop schema" in failed_down.stderr
        assert _psql(connection, env, "SELECT COUNT(*) FROM quantmind2._schema_migrations;").stdout.strip() == "1"
        assert _psql(connection, env, "SELECT to_regclass('quantmind2.implementation_tasks') IS NOT NULL;").stdout.strip() == "t"
        _psql(connection, env, "DROP TABLE quantmind2.rollback_guard;")
        _runner(runner_connection, env, "down", "--allow-destructive")
        assert _psql(connection, env, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='quantmind2';").stdout.strip() == "0"
        assert _psql(connection, env, "SELECT to_regclass('public.qm2_migration_sentinel') IS NOT NULL;").stdout.strip() == "t"

        _runner(runner_connection, env, "up")
        counts_second = _assert_catalog_parity(connection, env)
        assert counts_second == counts_first
        _runner(runner_connection, env, "down", "--allow-destructive")
        assert _psql(connection, env, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='quantmind2';").stdout.strip() == "0"
    finally:
        if started:
            subprocess.run(["docker", "rm", "-f", container], text=True, capture_output=True, check=False)
        assert _docker("ps", "-a", "--filter", f"name=^{container}$", "--format", "{{.Names}}").stdout.strip() == ""
