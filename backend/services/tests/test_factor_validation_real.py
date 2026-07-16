import json
import os
from pathlib import Path

import pytest

from backend.services.engine.factor_validation import FrozenTestAccessContext, evaluate_frozen
from backend.services.engine.factor_validation.dataset import validate_validation_dataset
from backend.services.engine.factor_validation.validation import validate_validation_result


DATASET_ID = "vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62"
RESULT_ID = "fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0"
SELECTION_ID = "fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c"
FROZEN_ID = "fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787"


def _root():
    value = os.getenv("QM2_FACTOR_VALIDATION_REAL_ROOT")
    if not value: pytest.skip("set QM2_FACTOR_VALIDATION_REAL_ROOT for real 14-Trial proof")
    return Path(value)


def test_real_dataset_splits_and_complete_source_hash_evidence():
    root = _root(); result = validate_validation_dataset(root / "data", DATASET_ID,
        source_root="/Users/yj/Documents/Codex/2026-06-30/nih/work/QuantMind/db/feature_snapshots"); manifest = result["manifest"]
    assert manifest["feature_snapshot_id"] == "ds_dd1defb79ddf2a81f057be9e34715cb04df340204d68338f73ab1ad4692e338f"
    assert manifest["symbol_count"] == 300 and manifest["row_count"] == 396392
    assert all(item["hash_evidence"] == "computed_from_current_bytes" for item in manifest["source_files"])
    assert manifest["splits"]["train"]["date_count"] == 483
    assert manifest["splits"]["validation"]["date_count"] == 241
    assert manifest["splits"]["quarantined_development"]["date_count"] == 242
    assert manifest["splits"]["frozen_test"]["date_count"] == 111
    assert manifest["quarantined_periods"][0]["start"].startswith("2025")


def test_real_fourteen_trials_selection_and_frozen_exact_replay():
    root = _root(); validation = validate_validation_result(root / "artifacts", RESULT_ID, SELECTION_ID)
    manifest = validation["manifest"]
    assert len(manifest["trial_results"]) == 14 and len(manifest["candidate_order"]) == 4
    assert len(manifest["selected_trial_ids"]) == 3
    assert manifest["development_diagnostic_used"] is False and manifest["frozen_labels_accessed"] is False
    assert [item["validation_rank"] for item in validation["selection"]["candidates"]] == [1, 2, 3]
    assert all(item["train_oriented_metrics"]["date_count_valid"] >= 100 for item in manifest["trial_results"])
    context = FrozenTestAccessContext("qm2-frozen-2026-v1", DATASET_ID, SELECTION_ID,
                                      "final-confirmatory-validation", "QM2-P0-006")
    frozen = evaluate_frozen(context, dataset_root=root / "data", validation_root=root / "artifacts",
                             factor_values_root=root / "factor-values")
    assert frozen["frozen_result_id"] == FROZEN_ID
    assert len(frozen["manifest"]["results"]) == 3
    assert frozen["manifest"]["reselection_permitted"] is False
