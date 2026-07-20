from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.services.engine.artifact_store.integrity import scan_store_integrity
from backend.services.engine.expanded_factor_iteration.artifact import KINDS, validate_artifact
from backend.services.engine.expanded_factor_iteration.audit import build_existing_factor_audit
from backend.services.engine.expanded_factor_iteration.engine import replay_experiment
from backend.services.engine.tushare_agent_experiment.data import load_authority_bundle


pytestmark = pytest.mark.skipif(
    os.environ.get("QUANTMIND_RUN_EXPANDED_FACTOR_REAL_TESTS") != "1",
    reason="requires the local immutable Tushare research Artifact Store",
)


ROOT = Path(__file__).resolve().parents[3]


def _bundle(tmp_path):
    return load_authority_bundle(
        authority_path=ROOT / "docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json",
        work_root=tmp_path / "authority",
    )


def test_real_existing_factor_audit_recovers_three_complete_formulas(tmp_path):
    audit = build_existing_factor_audit(_bundle(tmp_path).store, tmp_path / "audit")
    assert audit["complete_formula_recovery"] is True and audit["factor_count"] == 3
    required = {
        "factor_instance_id", "factor_template_id", "template_name", "agent_round",
        "research_goal_id", "canonical_dsl", "canonical_ast", "input_features",
        "parameter_schema", "selected_parameters", "orientation", "values_are_oriented",
        "factor_value_artifact_id", "unified_signal_id", "structural_fingerprint",
        "economic_hypothesis", "human_explanation",
    }
    assert all(required.issubset(row) for row in audit["factors"])


def test_real_experiment_exact_replay_and_research_only_registry(tmp_path):
    summary = replay_experiment(repository_root=ROOT, work_root=tmp_path / "replay")
    assert summary["experiment_id"].startswith("afi2_")
    assert summary["exact_existing"] is True
    assert {name: summary[name] for name in (
        "agent_calls", "factor_optimization_calls", "qlib_calls", "network_calls",
        "new_artifacts", "new_blobs", "promotion_writes",
    )} == {
        "agent_calls": 0, "factor_optimization_calls": 0, "qlib_calls": 0,
        "network_calls": 0, "new_artifacts": 0, "new_blobs": 0, "promotion_writes": 0,
    }
    assert summary["round_count"] == 6 and summary["eligible_candidate_count"] == 1
    assert summary["registry"] == {
        "entry_count": 1, "statuses": ["research_registered"],
        "promotion_candidate_count": 0, "approved_count": 0, "active_count": 0,
    }
    reports = next(iter(summary["retrospective_reports"].values()))
    assert set(reports) == {"2025", "2026H1"}
    assert all(item["not_used_for_selection"] and item["not_fresh_validation"] for item in reports.values())


def test_real_store_cold_recovers_every_v2_artifact_and_is_healthy(tmp_path):
    bundle = _bundle(tmp_path)
    recovered = 0
    for kind in KINDS:
        for descriptor in bundle.store.list_by_kind(kind):
            destination = tmp_path / "cold" / descriptor.artifact_id
            bundle.store.materialize_artifact(descriptor.descriptor_id, destination)
            validation = validate_artifact(destination, descriptor.artifact_id, kind)
            assert validation["status"] == "valid"
            recovered += 1
    assert recovered == 15
    integrity = scan_store_integrity(bundle.store)
    assert integrity.status == "healthy"
    assert integrity.issues == () and integrity.unreferenced_blobs == ()


def test_real_rounds_retain_all_folds_and_fixed_formal_qlib(tmp_path):
    bundle = _bundle(tmp_path)
    descriptors = bundle.store.list_by_kind("agent_factor_round_result")
    assert len(descriptors) == 6
    total_calls = total_trials = 0
    for descriptor in descriptors:
        root = tmp_path / "rounds" / descriptor.artifact_id
        bundle.store.materialize_artifact(descriptor.descriptor_id, root)
        identity = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["identity"]
        total_calls += len(identity["provider_calls"])
        total_trials += identity["feedback"]["trial_success_count"]
        assert identity["feedback"]["later_period_feedback_included"] is False
        assert identity["feedback"]["fixed_100_relative_metrics_included"] is False
    assert total_calls == 6 and total_trials == 38


def test_real_candidate_has_four_independent_fold_locks_and_no_promotion(tmp_path):
    bundle = _bundle(tmp_path)
    descriptors = bundle.store.list_by_kind("agent_factor_candidate_lock")
    assert len(descriptors) == 2
    descriptor = next(item for item in descriptors if item.artifact_id == replay_experiment(
        repository_root=ROOT, work_root=tmp_path / "candidate-replay"
    )["candidate_lock_ids"][0])
    root = tmp_path / "candidate"
    bundle.store.materialize_artifact(descriptor.descriptor_id, root)
    identity = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["identity"]
    assert [row["evaluation_year"] for row in identity["four_fold_metrics"]] == ["2021", "2022", "2023", "2024"]
    assert all(row["qlib"]["status"] == "completed" for row in identity["four_fold_metrics"])
    assert all(row["qlib"]["formal_chain"][-1] == "CnExchange" for row in identity["four_fold_metrics"])
    assert identity["selection_data_end"] == "2024-12-31"
    assert identity["canonical_dsl"].startswith("cs_rank(")
    assert identity["contract_revision"] == 2
    assert identity["status"] == "research_registered"
    assert identity["predictive_claim"] is False
    assert identity["usable_for_promotion"] is False and identity["eligible_for_production"] is False
