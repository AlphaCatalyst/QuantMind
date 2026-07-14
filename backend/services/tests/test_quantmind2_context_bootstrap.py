from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from tools.quantmind2.validate_context_bootstrap import (
    QM2,
    RESEARCH_DECISION_CONTRACT,
    RESEARCH_DECISION_EXAMPLE,
    RESEARCH_DECISION_SCHEMA,
    SCHEMAS,
    ValidationError,
    load_json,
    validate_bootstrap,
    validate_instance,
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
