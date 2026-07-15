#!/usr/bin/env python3
"""Versioned explicit-SQL runner for the QuantMind 2.0 Ledger schema.

The runner deliberately has no application database, Repository, SQLAlchemy,
or third-party dependency. It coordinates psql with argv lists and stdin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


LEDGER_MIGRATION_RUNNER_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
ADVISORY_LOCK_KEY = 4379672674272511630
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "data/migrations/quantmind2/manifest.json"
BUSINESS_TABLES = (
    "implementation_tasks",
    "implementation_runs",
    "implementation_run_relationships",
    "implementation_changed_files",
    "implementation_changed_symbols",
    "implementation_test_executions",
    "implementation_artifacts",
    "implementation_component_references",
    "implementation_adr_references",
    "implementation_limitations",
    "implementation_recommended_tasks",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MigrationError(RuntimeError):
    """Safe, credential-free migration failure."""


def exact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_child(base: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise MigrationError("migration path must be a non-empty relative path")
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise MigrationError("migration path escapes its manifest directory") from exc
    if candidate.parent != base.resolve():
        raise MigrationError("migration SQL files must be direct manifest siblings")
    return candidate


def _validate_sql(sql: str, *, direction: str) -> None:
    lowered = sql.lower()
    forbidden = (
        r"\bcascade\b",
        r"\bcreate\s+(?:constraint\s+)?trigger\b",
        r"\bgrant\b",
        r"\brevoke\b",
        r"\balter\s+(?:role|database)\b",
        r"\bset\s+search_path\b",
        r"\b(public|pg_catalog|information_schema)\s*\.",
        r"\bdrop\s+schema\s+(?!quantmind2\b)",
    )
    for pattern in forbidden:
        if re.search(pattern, lowered):
            raise MigrationError(f"unsafe or out-of-scope SQL in {direction} migration")
    if direction == "up":
        for table in BUSINESS_TABLES:
            if len(re.findall(rf"create\s+table\s+quantmind2\.{table}\s*\(", lowered)) != 1:
                raise MigrationError(f"up migration must create exactly one quantmind2.{table}")
        if "create schema if not exists quantmind2" not in lowered:
            raise MigrationError("up migration must explicitly create quantmind2 schema")
        if "quantmind2._schema_migrations" not in lowered:
            raise MigrationError("up migration must define migration history infrastructure")
    else:
        for table in BUSINESS_TABLES:
            if len(re.findall(rf"drop\s+table\s+quantmind2\.{table}\s*;", lowered)) != 1:
                raise MigrationError(f"down migration must drop exactly one quantmind2.{table}")
        if "drop schema quantmind2;" not in lowered:
            raise MigrationError("down migration must safely remove quantmind2 schema")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationError("migration manifest is not readable valid UTF-8 JSON") from exc
    required_root = {
        "manifest_schema_version",
        "runner_version",
        "schema",
        "history_table",
        "checksum_algorithm",
        "migrations",
    }
    if set(raw) != required_root:
        raise MigrationError("migration manifest root fields do not match v1 contract")
    if raw["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise MigrationError("unsupported migration manifest schema version")
    if raw["runner_version"] != LEDGER_MIGRATION_RUNNER_VERSION:
        raise MigrationError("manifest runner version does not match this runner")
    if raw["schema"] != "quantmind2" or raw["history_table"] != "_schema_migrations":
        raise MigrationError("manifest targets an unsupported schema or history table")
    if raw["checksum_algorithm"] != "sha256-exact-file-bytes":
        raise MigrationError("unsupported checksum algorithm")
    if not isinstance(raw["migrations"], list) or not raw["migrations"]:
        raise MigrationError("manifest migrations must be a non-empty array")

    expected_fields = {"version", "name", "up_path", "down_path", "up_checksum", "down_checksum"}
    migrations: list[dict[str, Any]] = []
    versions: list[str] = []
    for item in raw["migrations"]:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise MigrationError("migration entry fields do not match v1 contract")
        if not all(isinstance(item[k], str) and item[k] for k in expected_fields):
            raise MigrationError("migration entry values must be non-empty strings")
        if not re.fullmatch(r"[0-9]{4}", item["version"]):
            raise MigrationError("migration version must be four decimal digits")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", item["name"]):
            raise MigrationError("migration name is invalid")
        if not SHA256.fullmatch(item["up_checksum"]) or not SHA256.fullmatch(item["down_checksum"]):
            raise MigrationError("migration checksum must be lowercase SHA-256")
        up_path = _safe_child(path.parent, item["up_path"])
        down_path = _safe_child(path.parent, item["down_path"])
        if not up_path.is_file() or not down_path.is_file():
            raise MigrationError("paired migration SQL file is missing")
        try:
            up_sql = up_path.read_text(encoding="utf-8")
            down_sql = down_path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise MigrationError("migration SQL must be valid UTF-8") from exc
        if exact_sha256(up_path) != item["up_checksum"] or exact_sha256(down_path) != item["down_checksum"]:
            raise MigrationError("migration checksum drift detected")
        _validate_sql(up_sql, direction="up")
        _validate_sql(down_sql, direction="down")
        enriched = dict(item, up_file=up_path, down_file=down_path, up_sql=up_sql, down_sql=down_sql)
        migrations.append(enriched)
        versions.append(item["version"])
    if versions != sorted(versions) or len(versions) != len(set(versions)):
        raise MigrationError("migration versions must be unique and sorted")
    return raw, migrations


def _psql_argv(args: argparse.Namespace) -> list[str]:
    if args.docker_container:
        if not SAFE_NAME.fullmatch(args.docker_container):
            raise MigrationError("invalid Docker container name")
        argv = [args.docker_command, "exec", "-i", args.docker_container, "psql"]
    else:
        executable = shutil.which(args.psql_command) if "/" not in args.psql_command else args.psql_command
        if not executable:
            raise MigrationError("psql executable was not found")
        argv = [executable]
        if args.host:
            argv.extend(["--host", args.host])
        if args.port:
            argv.extend(["--port", str(args.port)])
    argv.extend(["--username", args.username, "--dbname", args.database, "-X", "--no-psqlrc", "-qAt", "-v", "ON_ERROR_STOP=1"])
    return argv


def run_psql(args: argparse.Namespace, sql: str) -> str:
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = env.get("PGCONNECT_TIMEOUT", "10")
    try:
        result = subprocess.run(
            _psql_argv(args), input=sql, text=True, capture_output=True, env=env, check=False
        )
    except OSError as exc:
        raise MigrationError("database command could not be started") from exc
    if result.returncode:
        message = result.stderr.strip() or "psql returned a non-zero status"
        for key in ("PGPASSWORD", "DATABASE_URL", "POSTGRES_PASSWORD"):
            secret = env.get(key)
            if secret:
                message = message.replace(secret, "[REDACTED]")
        raise MigrationError(message)
    return result.stdout.strip()


def applied_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    exists = run_psql(args, "SELECT COALESCE(to_regclass('quantmind2._schema_migrations')::text, '');")
    if not exists:
        return []
    output = run_psql(
        args,
        "SELECT version || E'\\t' || name || E'\\t' || up_checksum || E'\\t' || down_checksum "
        "FROM quantmind2._schema_migrations ORDER BY version;",
    )
    rows = []
    for line in output.splitlines() if output else []:
        version, name, up_checksum, down_checksum = line.split("\t")
        rows.append({"version": version, "name": name, "up_checksum": up_checksum, "down_checksum": down_checksum})
    return rows


def status(migrations: list[dict[str, Any]], applied: list[dict[str, str]]) -> tuple[list[str], bool]:
    expected = {m["version"]: m for m in migrations}
    actual = {m["version"]: m for m in applied}
    lines: list[str] = []
    drift = False
    for migration in migrations:
        row = actual.get(migration["version"])
        if row is None:
            state = "pending"
        elif row["name"] != migration["name"] or row["up_checksum"] != migration["up_checksum"] or row["down_checksum"] != migration["down_checksum"]:
            state, drift = "checksum_drift", True
        else:
            state = "applied"
        lines.append(f"{migration['version']} {migration['name']} {state}")
    for row in applied:
        if row["version"] not in expected:
            lines.append(f"{row['version']} {row['name']} unknown_applied")
            drift = True
    return lines, drift


def up(args: argparse.Namespace, migrations: list[dict[str, Any]]) -> None:
    known_versions = ", ".join(f"'{migration['version']}'" for migration in migrations)
    for migration in migrations:
        sql = f"""BEGIN;
SELECT pg_advisory_xact_lock({ADVISORY_LOCK_KEY});
CREATE SCHEMA IF NOT EXISTS quantmind2;
CREATE TABLE IF NOT EXISTS quantmind2._schema_migrations (
 version VARCHAR(32) NOT NULL, name VARCHAR(255) NOT NULL,
 up_checksum CHAR(64) NOT NULL, down_checksum CHAR(64) NOT NULL,
 applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
 runner_version VARCHAR(32) NOT NULL,
 CONSTRAINT pk_qm2_schema_migrations PRIMARY KEY (version),
 CONSTRAINT ck_qm2_schema_migrations_version_nonempty CHECK (btrim(version) <> ''),
 CONSTRAINT ck_qm2_schema_migrations_name_nonempty CHECK (btrim(name) <> ''),
 CONSTRAINT ck_qm2_schema_migrations_up_checksum CHECK (up_checksum ~ '^[0-9A-Fa-f]{{64}}$'),
 CONSTRAINT ck_qm2_schema_migrations_down_checksum CHECK (down_checksum ~ '^[0-9A-Fa-f]{{64}}$')
);
DO $qm2$ BEGIN
 IF EXISTS (SELECT 1 FROM quantmind2._schema_migrations WHERE version NOT IN ({known_versions}))
 THEN RAISE EXCEPTION 'unknown applied migration prevents up'; END IF;
 IF EXISTS (SELECT 1 FROM quantmind2._schema_migrations WHERE version = '{migration['version']}' AND
  (name <> '{migration['name']}' OR up_checksum <> '{migration['up_checksum']}' OR down_checksum <> '{migration['down_checksum']}'))
 THEN RAISE EXCEPTION 'checksum drift for migration {migration['version']}'; END IF;
END $qm2$;
SELECT EXISTS (SELECT 1 FROM quantmind2._schema_migrations WHERE version = '{migration['version']}') AS qm2_applied \\gset
\\if :qm2_applied
\\else
{migration['up_sql']}
INSERT INTO quantmind2._schema_migrations(version, name, up_checksum, down_checksum, runner_version)
VALUES ('{migration['version']}', '{migration['name']}', '{migration['up_checksum']}', '{migration['down_checksum']}', '{LEDGER_MIGRATION_RUNNER_VERSION}');
\\endif
COMMIT;
"""
        run_psql(args, sql)
        print(f"{migration['version']} {migration['name']} applied_or_current")


def down(args: argparse.Namespace, migrations: list[dict[str, Any]]) -> None:
    if not args.allow_destructive:
        raise MigrationError("down requires --allow-destructive")
    applied = applied_rows(args)
    if not applied:
        raise MigrationError("no applied migration is available to roll back")
    expected = {m["version"]: m for m in migrations}
    latest = applied[-1]
    migration = expected.get(latest["version"])
    if migration is None:
        raise MigrationError("latest applied migration is unknown to this manifest")
    if latest["name"] != migration["name"] or latest["up_checksum"] != migration["up_checksum"] or latest["down_checksum"] != migration["down_checksum"]:
        raise MigrationError("checksum drift prevents rollback")
    sql = f"""BEGIN;
SELECT pg_advisory_xact_lock({ADVISORY_LOCK_KEY});
DO $qm2$ BEGIN
 IF (SELECT version FROM quantmind2._schema_migrations ORDER BY version DESC LIMIT 1) <> '{migration['version']}'
 THEN RAISE EXCEPTION 'migration is no longer latest'; END IF;
 IF NOT EXISTS (SELECT 1 FROM quantmind2._schema_migrations WHERE version = '{migration['version']}'
  AND name = '{migration['name']}' AND up_checksum = '{migration['up_checksum']}' AND down_checksum = '{migration['down_checksum']}')
 THEN RAISE EXCEPTION 'checksum drift prevents rollback'; END IF;
END $qm2$;
{migration['down_sql']}
COMMIT;
"""
    run_psql(args, sql)
    print(f"{migration['version']} {migration['name']} rolled_back")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "validate", "status", "up", "down"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--psql-command", default="psql")
    parser.add_argument("--docker-command", default="docker")
    parser.add_argument("--docker-container")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database", default="quantmind")
    parser.add_argument("--username", default="quantmind")
    parser.add_argument("--allow-destructive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _, migrations = load_manifest(args.manifest.resolve())
        if args.command == "plan":
            for m in migrations:
                print(f"{m['version']} {m['name']} up={m['up_checksum']} down={m['down_checksum']} up_path={m['up_path']} down_path={m['down_path']}")
        elif args.command == "validate":
            print(f"valid migrations={len(migrations)} runner={LEDGER_MIGRATION_RUNNER_VERSION}")
        elif args.command == "status":
            lines, drift = status(migrations, applied_rows(args))
            print("\n".join(lines))
            if drift:
                raise MigrationError("database migration state is inconsistent")
        elif args.command == "up":
            up(args, migrations)
        else:
            down(args, migrations)
        return 0
    except MigrationError as exc:
        print(f"ledger migration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
