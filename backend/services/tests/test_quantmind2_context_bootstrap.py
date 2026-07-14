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
    RESEARCH_DECISION_CONTRACT,
    RESEARCH_DECISION_EXAMPLE,
    RESEARCH_DECISION_SCHEMA,
    SCHEMAS,
    ValidationError,
    load_json,
    validate_bootstrap,
    validate_instance,
    sha256_file,
)


MANIFEST_SCHEMA = SCHEMAS / "implementation_manifest_v1.schema.json"
MANIFEST_EXAMPLE = (
    QM2 / "implementation" / "templates" / "implementation_manifest_v1.example.json"
)


class QuantMind2ContextBootstrapTests(unittest.TestCase):
    def test_context_bootstrap_is_consistent(self):
        checks = validate_bootstrap()
        self.assertIn("context_paths", checks)
        self.assertIn("adr_index", checks)
        self.assertIn("implementation_runs", checks)

    def test_implementation_manifest_positive_example(self):
        validate_instance(load_json(MANIFEST_EXAMPLE), load_json(MANIFEST_SCHEMA))

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
        self.assertEqual(len(index["adrs"]), 9)
        root = Path(__file__).resolve().parents[3]
        for adr in index["adrs"]:
            self.assertTrue((root / adr["path"]).is_file())
        adr_0009 = next(item for item in index["adrs"] if item["adr_id"] == "ADR-0009")
        self.assertEqual(adr_0009["status"], "accepted")

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

    def test_ledger_persistence_remains_unimplemented(self):
        state = load_json(QM2 / "context" / "current_state.json")
        self.assertNotIn(
            "quantmind2.project_knowledge",
            state["components_by_status"]["implemented"],
        )
        root = Path(__file__).resolve().parents[3]
        self.assertFalse((root / "backend/services/api/project_knowledge").exists())
        domain_root = root / "backend/services/engine/project_knowledge/domain"
        self.assertTrue(domain_root.is_dir())
        for forbidden in ("repository.py", "repositories.py", "orm.py", "api.py"):
            self.assertFalse((domain_root / forbidden).exists())
        self.assertFalse(list((root / "data/migrations").glob("*ledger*")))

    def test_handoff_names_exact_a1b2_and_machine_state_uses_legal_parent(self):
        text = (QM2 / "context" / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn(
            "QM2-P0-002A1b2 — Ledger Repository Contract and In-memory Test Double",
            text,
        )
        handoff = load_json(QM2 / "context" / "handoff.json")
        self.assertEqual(handoff["next_recommended_tasks"], ["QM2-P0-002A1"])

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
