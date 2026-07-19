from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from tools.quantmind2.validate_context_bootstrap import (
    QM2,
    ACCEPTED_ADR_HASHES,
    PERSISTENCE_AUDIT_EVIDENCE_PATHS,
    PERSISTENCE_REALITY_AUDIT,
    LEDGER_CORE_ORM_CONTRACT,
    LEDGER_CORE_DETAIL_ORM_CONTRACT,
    LEDGER_REFERENCE_ORM_CONTRACT,
    LEDGER_ANNOTATION_ORM_CONTRACT,
    LEDGER_MAPPER_CONTRACT,
    LEDGER_MAPPER_IDENTITY_VECTORS,
    LEDGER_TASK_MAPPER_CONTRACT,
    LEDGER_RUN_MAPPER_CONTRACT,
    RESEARCH_DECISION_CONTRACT,
    RESEARCH_DECISION_EXAMPLE,
    RESEARCH_DECISION_SCHEMA,
    SCHEMAS,
    ValidationError,
    load_json,
    validate_bootstrap,
    validate_instance,
    validate_mapper_identity_vectors,
    canonical_manifest_v2_payload_hash,
    sha256_file,
)


MANIFEST_SCHEMA = SCHEMAS / "implementation_manifest_v1.schema.json"
MANIFEST_EXAMPLE = (
    QM2 / "implementation" / "templates" / "implementation_manifest_v1.example.json"
)
MANIFEST_V2_SCHEMA = SCHEMAS / "implementation_manifest_v2.schema.json"
MANIFEST_V2_EXAMPLE = (
    QM2 / "implementation" / "examples" / "implementation_manifest_v2.example.json"
)


class QuantMind2ContextBootstrapTests(unittest.TestCase):
    def test_context_bootstrap_is_consistent(self):
        checks = validate_bootstrap()
        self.assertIn("context_paths", checks)
        self.assertIn("adr_index", checks)
        self.assertIn("implementation_runs", checks)

    def test_implementation_manifest_positive_example(self):
        validate_instance(load_json(MANIFEST_EXAMPLE), load_json(MANIFEST_SCHEMA))

    def test_implementation_manifest_v2_positive_example_and_hash(self):
        payload = load_json(MANIFEST_V2_EXAMPLE)
        validate_instance(payload, load_json(MANIFEST_V2_SCHEMA))
        self.assertEqual(
            canonical_manifest_v2_payload_hash(payload),
            payload["integrity"]["manifest_payload_sha256"],
        )

    def test_implementation_manifest_v2_additional_property_is_rejected(self):
        payload = load_json(MANIFEST_V2_EXAMPLE)
        payload["task"]["prose_fallback"] = "forbidden"
        with self.assertRaisesRegex(ValidationError, "additional properties"):
            validate_instance(payload, load_json(MANIFEST_V2_SCHEMA))

    def test_implementation_manifest_missing_required_field_is_rejected(self):
        payload = load_json(MANIFEST_EXAMPLE)
        payload.pop("task_id")
        with self.assertRaisesRegex(ValidationError, "missing required"):
            validate_instance(payload, load_json(MANIFEST_SCHEMA))

    def test_implementation_manifest_invalid_enum_is_rejected(self):
        payload = load_json(MANIFEST_EXAMPLE)
        payload["task_status"] = "canonical"
        with self.assertRaisesRegex(ValidationError, "not in"):
            validate_instance(payload, load_json(MANIFEST_SCHEMA))

    def test_implementation_manifest_accepts_lowercase_task_suffix_in_run_id(self):
        payload = load_json(MANIFEST_EXAMPLE)
        payload["implementation_run_id"] = (
            "QM2-P0-002A1a-20260714T145325Z-8188a1e"
        )
        validate_instance(payload, load_json(MANIFEST_SCHEMA))

    def test_nonexistent_context_reference_is_rejected(self):
        original = load_json(QM2 / "context" / "context_index.json")
        modified = copy.deepcopy(original)
        modified["mandatory_read_order"].append(
            "docs/quantmind2/does-not-exist.md"
        )
        context_path = QM2 / "context" / "context_index.json"
        real_read_text = Path.read_text

        def fake_read_text(path, *args, **kwargs):
            if path.resolve() == context_path.resolve():
                return json.dumps(modified)
            return real_read_text(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", fake_read_text):
            with self.assertRaisesRegex(
                ValidationError, "mandatory read path does not exist"
            ):
                validate_bootstrap()

    def test_adr_index_references_are_complete(self):
        index = load_json(QM2 / "adr" / "adr_index.json")
        self.assertEqual(len(index["adrs"]), 10)
        root = Path(__file__).resolve().parents[3]
        for adr in index["adrs"]:
            self.assertTrue((root / adr["path"]).is_file())
        adr_0009 = next(item for item in index["adrs"] if item["adr_id"] == "ADR-0009")
        self.assertEqual(adr_0009["status"], "accepted")
        adr_0010 = next(item for item in index["adrs"] if item["adr_id"] == "ADR-0010")
        self.assertEqual(adr_0010["status"], "accepted")

    def test_research_decision_contract_and_architecture_exist(self):
        self.assertTrue(RESEARCH_DECISION_CONTRACT.is_file())
        architecture = (QM2 / "architecture" / "QUANTMIND_2_ARCHITECTURE_V1.md").read_text()
        for marker in ("ADR-0009", "## Decision Layer", "## Control Layer", "## Execution Layer"):
            self.assertIn(marker, architecture)

    def test_research_decision_example_validates(self):
        validate_instance(
            load_json(RESEARCH_DECISION_EXAMPLE),
            load_json(RESEARCH_DECISION_SCHEMA),
        )

    def test_persistence_reality_audit_exists_and_evidence_paths_exist(self):
        self.assertTrue(PERSISTENCE_REALITY_AUDIT.is_file())
        text = PERSISTENCE_REALITY_AUDIT.read_text(encoding="utf-8")
        root = Path(__file__).resolve().parents[3]
        for path in PERSISTENCE_AUDIT_EVIDENCE_PATHS:
            self.assertTrue((root / path).is_file(), path)
            self.assertIn(path, text)

    def test_ledger_core_orm_is_bounded_and_persistence_remains_undeployed(self):
        state = load_json(QM2 / "context" / "current_state.json")
        self.assertNotIn(
            "quantmind2.project_knowledge",
            state["components_by_status"]["implemented"],
        )
        root = Path(__file__).resolve().parents[3]
        api_root = root / "backend/services/api/project_knowledge"
        self.assertTrue((api_root / "__init__.py").is_file())
        orm_root = api_root / "persistence"
        self.assertEqual(
            {path.name for path in orm_root.glob("*.py")},
            {
                "__init__.py",
                "orm_models.py",
                "orm_detail_models.py",
                "orm_reference_models.py",
                "orm_annotation_models.py",
                "orm_types.py",
            },
        )
        self.assertTrue(LEDGER_CORE_ORM_CONTRACT.is_file())
        self.assertTrue(LEDGER_CORE_DETAIL_ORM_CONTRACT.is_file())
        self.assertTrue(LEDGER_REFERENCE_ORM_CONTRACT.is_file())
        self.assertTrue(LEDGER_ANNOTATION_ORM_CONTRACT.is_file())
        domain_root = root / "backend/services/engine/project_knowledge/domain"
        self.assertTrue(domain_root.is_dir())
        self.assertTrue((domain_root / "repositories.py").is_file())
        for forbidden in ("repository.py", "orm.py", "api.py"):
            self.assertFalse((domain_root / forbidden).exists())
        self.assertFalse(list((root / "data/migrations").glob("*ledger*")))
        self.assertFalse((api_root / "repository.py").exists())
        self.assertFalse((api_root / "api.py").exists())

    def test_mapper_contract_vectors_and_complete_implementation_boundary(self):
        self.assertTrue(LEDGER_MAPPER_CONTRACT.is_file())
        payload = load_json(LEDGER_MAPPER_IDENTITY_VECTORS)
        validate_mapper_identity_vectors(payload)
        vectors = {item["case"]: item for item in payload["vectors"]}
        self.assertEqual(
            vectors["changed_file_added"]["expected_id"],
            vectors["changed_file_same_identity_different_hash"]["expected_id"],
        )
        self.assertEqual(
            vectors["changed_symbol_method"]["expected_id"],
            vectors["changed_symbol_same_identity_different_types"]["expected_id"],
        )
        self.assertNotEqual(
            vectors["changed_file_added"]["expected_id"],
            vectors["changed_file_case_preserved"]["expected_id"],
        )
        renamed = vectors["changed_file_renamed_previous_path_excluded"]
        self.assertNotIn(renamed["input"]["previous_path"], renamed["canonical_payload"])
        root = Path(__file__).resolve().parents[3]
        persistence = root / "backend/services/api/project_knowledge/persistence"
        mapper_root = persistence / "mappers"
        self.assertEqual(
            {path.name for path in mapper_root.glob("*.py")},
            {
                "__init__.py", "errors.py", "common.py", "task.py", "run.py",
                "identity.py", "relationship.py", "details.py", "references.py",
                "annotations.py",
            },
        )
        self.assertTrue(LEDGER_TASK_MAPPER_CONTRACT.is_file())
        self.assertTrue(LEDGER_RUN_MAPPER_CONTRACT.is_file())
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in mapper_root.glob("*.py")
        )
        self.assertIn("implementation_task_to_record", source)
        self.assertIn("implementation_task_from_record", source)
        self.assertIn("implementation_run_to_record", source)
        self.assertIn("implementation_run_from_record", source)
        for marker in (
            "run_relationship_to_record", "changed_file_record_id",
            "changed_file_to_record", "changed_symbol_to_record",
            "test_execution_to_record", "implementation_artifact_to_record",
            "component_reference_to_record",
            "architecture_decision_reference_to_record", "limitation_to_record",
            "recommended_task_to_record",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("run_from_manifest", source)

    def test_handoff_records_locked_signal_audit_and_blocked_followup(self):
        text = (QM2 / "context" / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("candidates, approved and active are all zero", text)
        self.assertIn("QM2-P0-011", text)
        self.assertIn("truthful partial production dry run", text)
        self.assertIn(
            "QM2-P0-011B — Fixed-100-Universe 2019—2026 Agent Iteration and "
            "Historical Backtest",
            " ".join(text.split()),
        )
        handoff = load_json(QM2 / "context" / "handoff.json")
        self.assertIn("3,822 NaNs / 10,867 observed rows", text)
        self.assertIn("Qlib rerun calls are zero", text)
        self.assertIn("status is `blocked`", text)
        self.assertEqual(handoff["current_task"], "QM2-P0-011BF")
        self.assertEqual(handoff["completion_status"], "blocked")
        self.assertEqual(handoff["next_recommended_tasks"], [])

    def test_persistence_audit_did_not_modify_accepted_adrs(self):
        root = Path(__file__).resolve().parents[3]
        for path, expected in ACCEPTED_ADR_HASHES.items():
            self.assertEqual(sha256_file(root / path), expected)

    def test_research_decision_invalid_action_is_rejected(self):
        payload = load_json(RESEARCH_DECISION_EXAMPLE)
        payload["action"] = "CALL_QLIB_DIRECTLY"
        with self.assertRaisesRegex(ValidationError, "not in"):
            validate_instance(payload, load_json(RESEARCH_DECISION_SCHEMA))

    def test_research_decision_missing_rationale_is_rejected(self):
        payload = load_json(RESEARCH_DECISION_EXAMPLE)
        payload.pop("rationale")
        with self.assertRaisesRegex(ValidationError, "missing required"):
            validate_instance(payload, load_json(RESEARCH_DECISION_SCHEMA))

    def test_research_decision_frozen_test_field_is_rejected(self):
        payload = load_json(RESEARCH_DECISION_EXAMPLE)
        payload["frozen_test_data"] = {"rank_ic": 0.08}
        with self.assertRaisesRegex(ValidationError, "additional properties"):
            validate_instance(payload, load_json(RESEARCH_DECISION_SCHEMA))

    def test_mandatory_read_order_is_complete(self):
        index = load_json(QM2 / "context" / "context_index.json")
        self.assertGreaterEqual(len(index["mandatory_read_order"]), 8)
        root = Path(__file__).resolve().parents[3]
        for path in index["mandatory_read_order"]:
            self.assertTrue((root / path).exists())

    def test_all_quantmind2_json_files_parse(self):
        files = sorted(QM2.rglob("*.json"))
        self.assertTrue(files)
        for path in files:
            load_json(path)


if __name__ == "__main__":
    unittest.main()
