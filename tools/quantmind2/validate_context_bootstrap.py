#!/usr/bin/env python3
"""Validate the QuantMind 2.0 repository context without external packages.

This is a deliberately bounded JSON Schema Draft 2020-12 validator. It checks
the keywords used by the repository's v1 schemas; it is not a general-purpose
replacement for the jsonschema package.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QM2 = ROOT / "docs" / "quantmind2"
SCHEMAS = QM2 / "implementation" / "schemas"
RESEARCH_DECISION_CONTRACT = QM2 / "architecture" / "RESEARCH_DECISION_CONTRACT_V1.md"
RESEARCH_DECISION_SCHEMA = QM2 / "architecture" / "schemas" / "research_decision_v1.schema.json"
RESEARCH_DECISION_EXAMPLE = QM2 / "architecture" / "examples" / "research_decision_v1.example.json"
PERSISTENCE_REALITY_AUDIT = QM2 / "implementation" / "LEDGER_PERSISTENCE_REALITY_AUDIT_V1.md"
LEDGER_DOMAIN_CONTRACT = QM2 / "implementation" / "LEDGER_DOMAIN_MODEL_V1.md"
LEDGER_REPOSITORY_CONTRACT = QM2 / "implementation" / "LEDGER_REPOSITORY_CONTRACT_V1.md"
LEDGER_CORE_ORM_CONTRACT = QM2 / "implementation" / "LEDGER_CORE_ORM_MAPPING_V1.md"
LEDGER_DOMAIN_ROOT = ROOT / "backend" / "services" / "engine" / "project_knowledge" / "domain"
LEDGER_TESTING_ROOT = ROOT / "backend" / "services" / "engine" / "project_knowledge" / "testing"
LEDGER_API_ROOT = ROOT / "backend" / "services" / "api" / "project_knowledge"
LEDGER_ORM_ROOT = LEDGER_API_ROOT / "persistence"
LEGACY_FACTOR_LAB_PATH = (
    "/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/"
    "backend/services/engine/factor_lab"
)
OFFICIAL_FACTOR_LAB_PATH = (
    "/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/"
    "backend/services/engine/factor_lab/"
)
PERSISTENCE_AUDIT_EVIDENCE_PATHS = (
    "backend/shared/database_manager_v2.py",
    "backend/shared/database_pool.py",
    "backend/shared/database.py",
    "backend/shared/schema_registry.py",
    "backend/services/api/models/base.py",
    "backend/services/api/user_app/database.py",
    "backend/services/api/main.py",
    "backend/services/engine/main.py",
    "backend/services/engine/tasks/celery_tasks.py",
    "backend/services/trade/main.py",
    "backend/services/trade/deps.py",
    "backend/services/stream/market_app/database.py",
    "data/quantmind_init.sql",
    "data/upgrade_v1.1.0.sql",
    "data/migrations/upgrade_v1.4.0_stock_tag.sql",
    "deploy/deploy.sh",
    "docker-compose.yml",
    "requirements/production.txt",
    "requirements/database.txt",
    "backend/services/tests/conftest.py",
)
ACCEPTED_ADR_HASHES = {
    "docs/quantmind2/adr/ADR-0005-memory-and-implementation-ledger-separation.md":
        "e9c544ae846b3b92e2365a74a2c15a39dd7bb8f33628dbf0d7b856078a5aacb5",
    "docs/quantmind2/adr/ADR-0007-immutable-research-identities-and-lineage.md":
        "959abb4ae5498b64524c63cf33c98fc179fa5d5ee59712619f5475f68cdfe12d",
    "docs/quantmind2/adr/ADR-0009-decision-control-execution-separation.md":
        "38d80043864f943957d64657453d75fe54e2519a2739f3549e9df732a697f2f3",
}


class ValidationError(ValueError):
    """Raised when a document violates a local schema or bootstrap invariant."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON {path}: {exc}") from exc


def canonical_manifest_payload_hash(payload: dict[str, Any]) -> str:
    """Hash canonical JSON after excluding the self-referential hash field."""
    normalized = copy.deepcopy(payload)
    normalized.pop("manifest_payload_hash", None)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationError(f"unsupported non-local $ref: {ref}")
    node: Any = root_schema
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise ValidationError(f"unresolved $ref: {ref}")
        node = node[token]
    if not isinstance(node, dict):
        raise ValidationError(f"$ref does not resolve to an object schema: {ref}")
    return node


def _is_type(instance: Any, expected: str) -> bool:
    checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
    }
    if expected not in checks:
        raise ValidationError(f"unsupported schema type: {expected}")
    return checks[expected](instance)


def validate_instance(
    instance: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> None:
    root_schema = root_schema or schema
    if "$ref" in schema:
        validate_instance(
            instance,
            _resolve_ref(root_schema, schema["$ref"]),
            root_schema=root_schema,
            path=path,
        )
        return

    if "anyOf" in schema:
        failures: list[str] = []
        for candidate in schema["anyOf"]:
            try:
                validate_instance(instance, candidate, root_schema=root_schema, path=path)
                break
            except ValidationError as exc:
                failures.append(str(exc))
        else:
            raise ValidationError(f"{path}: no anyOf branch matched: {failures}")

    for item in schema.get("allOf", []):
        if "if" in item and "then" in item:
            try:
                validate_instance(instance, item["if"], root_schema=root_schema, path=path)
            except ValidationError:
                continue
            validate_instance(instance, item["then"], root_schema=root_schema, path=path)
        else:
            validate_instance(instance, item, root_schema=root_schema, path=path)

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path}: value {instance!r} is not in {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_is_type(instance, item) for item in types):
            raise ValidationError(f"{path}: expected type {types}, got {type(instance).__name__}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise ValidationError(f"{path}: missing required properties {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(instance) - set(properties))
            if extras:
                raise ValidationError(f"{path}: additional properties not allowed: {extras}")
        for key, value in instance.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(schema.get("additionalProperties"), dict):
                child_schema = schema["additionalProperties"]
            if child_schema is not None:
                validate_instance(value, child_schema, root_schema=root_schema, path=f"{path}.{key}")

    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            raise ValidationError(f"{path}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            canonical = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in instance]
            if len(canonical) != len(set(canonical)):
                raise ValidationError(f"{path}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, value in enumerate(instance):
                validate_instance(value, item_schema, root_schema=root_schema, path=f"{path}[{index}]")

    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            raise ValidationError(f"{path}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            raise ValidationError(f"{path}: string does not match {pattern!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{path}: value is below minimum")


def validate_file(document_path: Path, schema_path: Path) -> dict[str, Any]:
    document = load_json(document_path)
    schema = load_json(schema_path)
    validate_instance(document, schema)
    return document


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError(f"expected repository-relative path: {value}")
    return ROOT / path


def validate_bootstrap(root: Path = ROOT) -> list[str]:
    if root.resolve() != ROOT.resolve():
        raise ValidationError("custom repository roots are not supported by v1")
    checks: list[str] = []
    documents = {
        "context_index": (
            QM2 / "context" / "context_index.json",
            SCHEMAS / "context_index_v1.schema.json",
        ),
        "current_state": (
            QM2 / "context" / "current_state.json",
            SCHEMAS / "current_state_v1.schema.json",
        ),
        "component_catalog": (
            QM2 / "context" / "component_catalog.json",
            SCHEMAS / "component_catalog_v1.schema.json",
        ),
        "handoff": (
            QM2 / "context" / "handoff.json",
            SCHEMAS / "handoff_v1.schema.json",
        ),
    }
    loaded: dict[str, dict[str, Any]] = {}
    for name, (document, schema) in documents.items():
        loaded[name] = validate_file(document, schema)
        checks.append(f"schema:{name}")

    context = loaded["context_index"]
    for path in context["source_paths"] + context["authoritative_documents"] + context["derived_documents"]:
        if not _repo_path(path).is_file():
            raise ValidationError(f"context index path does not exist: {path}")
    for path in context["mandatory_read_order"]:
        if not _repo_path(path).exists():
            raise ValidationError(f"mandatory read path does not exist: {path}")
    checks.append("context_paths")

    adr_index_path = _repo_path(context["adr_index_ref"])
    adr_index = load_json(adr_index_path)
    if adr_index.get("schema_version") != "1.0.0":
        raise ValidationError("unrecognized ADR index schema_version")
    for record in adr_index.get("adrs", []):
        if not _repo_path(record["path"]).is_file():
            raise ValidationError(f"ADR path does not exist: {record['path']}")
        if record.get("status") != "accepted":
            raise ValidationError(f"initial ADR is not accepted: {record.get('adr_id')}")
    checks.append("adr_index")

    adr_0009 = next(
        (record for record in adr_index.get("adrs", []) if record.get("adr_id") == "ADR-0009"),
        None,
    )
    if adr_0009 is None or adr_0009.get("status") != "accepted":
        raise ValidationError("ADR-0009 is missing or not accepted")
    architecture_path = QM2 / "architecture" / "QUANTMIND_2_ARCHITECTURE_V1.md"
    architecture_text = architecture_path.read_text(encoding="utf-8")
    required_architecture_markers = {
        "ADR-0009",
        "## Decision Layer",
        "## Control Layer",
        "## Execution Layer",
        "ResearchDecision",
        "Bounded Code Orchestrator",
    }
    missing_markers = sorted(required_architecture_markers - set(
        marker for marker in required_architecture_markers if marker in architecture_text
    ))
    if missing_markers:
        raise ValidationError(f"Architecture v1 is missing decision-control-execution markers: {missing_markers}")
    if not RESEARCH_DECISION_CONTRACT.is_file():
        raise ValidationError("Research Decision Contract v1 is missing")
    checks.append("decision_control_execution_architecture")

    validate_file(RESEARCH_DECISION_EXAMPLE, RESEARCH_DECISION_SCHEMA)
    checks.append("research_decision_contract")

    if not PERSISTENCE_REALITY_AUDIT.is_file():
        raise ValidationError("Ledger persistence reality audit is missing")
    audit_text = PERSISTENCE_REALITY_AUDIT.read_text(encoding="utf-8")
    required_audit_markers = {
        "Recommended Ledger Persistence Mechanism",
        "【代码确认】",
        "【工程选择】",
        "【尚未确认】",
        "【阻断风险】",
        "QM2-P0-002A1b",
    }
    missing_audit_markers = sorted(
        marker for marker in required_audit_markers if marker not in audit_text
    )
    if missing_audit_markers:
        raise ValidationError(
            f"persistence reality audit is missing markers: {missing_audit_markers}"
        )
    for path in PERSISTENCE_AUDIT_EVIDENCE_PATHS:
        if not _repo_path(path).is_file():
            raise ValidationError(f"persistence audit evidence path does not exist: {path}")
        if path not in audit_text:
            raise ValidationError(f"persistence audit does not cite evidence path: {path}")
    checks.append("persistence_reality_audit")

    for path, expected_hash in ACCEPTED_ADR_HASHES.items():
        if sha256_file(_repo_path(path)) != expected_hash:
            raise ValidationError(f"accepted ADR changed during persistence audit: {path}")
    checks.append("persistence_audit_accepted_adrs")

    required_domain_files = {
        "__init__.py",
        "enums.py",
        "errors.py",
        "validators.py",
        "models.py",
        "relationships.py",
        "repositories.py",
        "repository_errors.py",
        "repository_queries.py",
    }
    if not LEDGER_DOMAIN_CONTRACT.is_file():
        raise ValidationError("Ledger domain model contract is missing")
    domain_contract_text = LEDGER_DOMAIN_CONTRACT.read_text(encoding="utf-8")
    required_domain_markers = {
        "Domain vs Persistence Boundary",
        "ImplementationRun Invariants",
        "Manifest v1 Mapping",
        "Rules Deferred to Repository Layer",
        "QM2-P0-002A1b2",
    }
    missing_domain_markers = sorted(
        marker for marker in required_domain_markers if marker not in domain_contract_text
    )
    if missing_domain_markers:
        raise ValidationError(f"Ledger domain contract is missing markers: {missing_domain_markers}")
    if not LEDGER_DOMAIN_ROOT.is_dir():
        raise ValidationError("Ledger domain package is missing")
    actual_domain_files = {path.name for path in LEDGER_DOMAIN_ROOT.glob("*.py")}
    if not required_domain_files.issubset(actual_domain_files):
        raise ValidationError("Ledger domain package is incomplete")
    if not LEDGER_REPOSITORY_CONTRACT.is_file():
        raise ValidationError("Ledger Repository contract is missing")
    repository_contract_text = LEDGER_REPOSITORY_CONTRACT.read_text(encoding="utf-8")
    required_repository_markers = {
        "Repository Interfaces",
        "Exact Replay Semantics",
        "Graph Cycle Detection",
        "Atomic Batch Contract",
        "In-memory Test Double Boundary",
        "QM2-P0-002A2",
    }
    missing_repository_markers = sorted(
        marker for marker in required_repository_markers if marker not in repository_contract_text
    )
    if missing_repository_markers:
        raise ValidationError(
            f"Ledger Repository contract is missing markers: {missing_repository_markers}"
        )
    required_testing_files = {"__init__.py", "in_memory_ledger_repository.py"}
    if not LEDGER_TESTING_ROOT.is_dir() or not required_testing_files.issubset(
        {path.name for path in LEDGER_TESTING_ROOT.glob("*.py")}
    ):
        raise ValidationError("Ledger in-memory test double is incomplete")
    for source_root in (LEDGER_DOMAIN_ROOT, LEDGER_TESTING_ROOT):
        for path in source_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            lowered = source.lower()
            if "sqlalchemy" in lowered or "fastapi" in lowered:
                raise ValidationError(f"Ledger contract has forbidden framework import: {path}")
    required_orm_files = {"__init__.py", "orm_models.py", "orm_types.py"}
    if not LEDGER_CORE_ORM_CONTRACT.is_file():
        raise ValidationError("Ledger core ORM contract is missing")
    orm_contract_text = LEDGER_CORE_ORM_CONTRACT.read_text(encoding="utf-8")
    required_orm_markers = {
        "Domain vs ORM Boundary",
        "implementation_tasks",
        "implementation_runs",
        "implementation_run_relationships",
        "Static DDL Verification",
        "QM2-P0-002A2a2",
    }
    missing_orm_markers = sorted(
        marker for marker in required_orm_markers if marker not in orm_contract_text
    )
    if missing_orm_markers:
        raise ValidationError(f"Ledger core ORM contract is missing markers: {missing_orm_markers}")
    if not LEDGER_API_ROOT.is_dir() or not (LEDGER_API_ROOT / "__init__.py").is_file():
        raise ValidationError("Ledger API-side persistence boundary is missing")
    if not LEDGER_ORM_ROOT.is_dir() or {
        path.name for path in LEDGER_ORM_ROOT.glob("*.py")
    } != required_orm_files:
        raise ValidationError("Ledger core ORM package is incomplete or expanded beyond A2a1")
    orm_source = (LEDGER_ORM_ROOT / "orm_models.py").read_text(encoding="utf-8")
    required_orm_source_markers = {
        "from backend.services.api.models.base import Base",
        'SCHEMA_NAME = "quantmind2"',
        'TASK_TABLE_NAME = "implementation_tasks"',
        'RUN_TABLE_NAME = "implementation_runs"',
        'RELATIONSHIP_TABLE_NAME = "implementation_run_relationships"',
        'ondelete="RESTRICT"',
    }
    missing_orm_source = sorted(
        marker for marker in required_orm_source_markers if marker not in orm_source
    )
    if missing_orm_source:
        raise ValidationError(f"Ledger core ORM mapping is missing markers: {missing_orm_source}")
    forbidden_runtime_markers = (
        "create_engine(",
        "create_async_engine(",
        "sessionmaker(",
        "create_all(",
        "drop_all(",
        ".execute(",
        ".commit(",
        ".rollback(",
    )
    if any(marker in orm_source for marker in forbidden_runtime_markers):
        raise ValidationError("Ledger core ORM mapping contains forbidden runtime database behavior")
    forbidden_project_knowledge_paths = (
        LEDGER_DOMAIN_ROOT.parent / "repository.py",
        LEDGER_DOMAIN_ROOT.parent / "repositories.py",
        LEDGER_DOMAIN_ROOT.parent / "api.py",
        LEDGER_DOMAIN_ROOT.parent / "orm.py",
    )
    if any(path.exists() for path in forbidden_project_knowledge_paths):
        raise ValidationError("Project Knowledge persistence, Repository, or API exists too early")
    if list((ROOT / "data" / "migrations").glob("*ledger*")):
        raise ValidationError("Ledger migration exists before ORM/migration task")
    forbidden_ledger_markers = (
        "implementation_ledger",
        "CREATE SCHEMA quantmind2",
        'schema="quantmind2"',
        "schema='quantmind2'",
    )
    for source_root in (ROOT / "backend", ROOT / "data"):
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sql"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(marker in text for marker in forbidden_ledger_markers):
                raise ValidationError(f"Ledger persistence implementation exists: {path}")
    checks.append("ledger_domain_contract")
    checks.append("ledger_domain_scope_boundary")
    checks.append("ledger_repository_contract")
    checks.append("ledger_in_memory_test_double_boundary")
    checks.append("ledger_core_orm_mapping")
    checks.append("ledger_core_orm_runtime_boundary")

    catalog = loaded["component_catalog"]
    component_status = {item["component_id"]: item["status"] for item in catalog["components"]}
    state = loaded["current_state"]
    for component_id in state["components_by_status"]["implemented"]:
        if component_status.get(component_id) in {"planned", "not_implemented", "blocked"}:
            raise ValidationError(f"planned component marked implemented: {component_id}")
    checks.append("component_state_consistency")

    handoff = loaded["handoff"]
    if handoff["factor_lab_source"]["source_path"] != OFFICIAL_FACTOR_LAB_PATH:
        raise ValidationError("handoff does not use the official Factor Lab source")
    required_handoff_sources = {
        "docs/quantmind2/context/CONTEXT_INDEX.md",
        "docs/quantmind2/architecture/QUANTMIND_2_ARCHITECTURE_V1.md",
    }
    if not required_handoff_sources.issubset(set(handoff["source_paths"])):
        raise ValidationError("handoff does not reference context and architecture")
    handoff_text = (QM2 / "context" / "HANDOFF.md").read_text(encoding="utf-8")
    if "QM2-P0-002A2a2 — Ledger Detail ORM Mapping and Domain Mappers" not in handoff_text:
        raise ValidationError("human handoff does not name exact QM2-P0-002A2a2 next task")
    if handoff["next_recommended_tasks"] != ["QM2-P0-002"]:
        raise ValidationError("machine handoff must use legal non-inflated P0-002 parent task")
    checks.append("handoff_links")

    example = QM2 / "implementation" / "templates" / "implementation_manifest_v1.example.json"
    manifest_schema = SCHEMAS / "implementation_manifest_v1.schema.json"
    validate_file(example, manifest_schema)
    checks.append("manifest_example")

    run_root = QM2 / "implementation" / "runs"
    for manifest_path in sorted(run_root.glob("*/*/*/manifest.json")):
        report_path = manifest_path.with_name("report.md")
        if not report_path.is_file():
            raise ValidationError(f"implementation report missing beside {manifest_path}")
        manifest = validate_file(manifest_path, manifest_schema)
        declared_report = _repo_path(manifest["report_path"])
        if declared_report.resolve() != report_path.resolve():
            raise ValidationError(f"manifest report_path mismatch: {manifest_path}")
        if sha256_file(report_path) != manifest["report_hash"]:
            raise ValidationError(f"report hash mismatch: {report_path}")
        if canonical_manifest_payload_hash(manifest) != manifest["manifest_payload_hash"]:
            raise ValidationError(f"manifest payload hash mismatch: {manifest_path}")
    checks.append("implementation_runs")

    for path in QM2.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json"}:
            text = path.read_text(encoding="utf-8")
            if LEGACY_FACTOR_LAB_PATH in text:
                raise ValidationError(f"legacy Factor Lab source referenced in {path}")
    checks.append("official_factor_lab_source_only")
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)
    try:
        checks = validate_bootstrap()
    except ValidationError as exc:
        payload = {"status": "failed", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else f"FAILED: {exc}")
        return 1
    payload = {
        "status": "passed",
        "validation_level": "bounded_zero_dependency_draft_2020_12_subset_plus_repository_invariants",
        "checks": checks,
        "check_count": len(checks),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
