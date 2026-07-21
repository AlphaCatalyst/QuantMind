from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.skip_recent_momentum.artifact import assert_complete, publish_artifact, validate_artifact
from backend.services.engine.skip_recent_momentum.engine import _parameter_rows, candidate_policy, ensemble_allowed
from backend.services.engine.skip_recent_momentum.protocol import (
    BUDGET, COMPLETENESS_REQUIRED, FEATURES, FOLDS, FORMAL_STRATEGY, REPORT_PERIODS,
    SOURCE_CATALOG_ID, SOURCE_DATASET_ID, SUBFAMILIES,
)


def _raw_identity(raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    return {"schema_version": "research-agent-raw-response-v1", "provider_id": "tushare-pro-v1",
            "agent_call_id": "call-1", "provider": "openai_codex_cli", "model": "gpt-5.6-terra",
            "prompt_hash": "a" * 64, "raw_response_blob_id": "blob_sha256_" + digest,
            "raw_response_hash": digest, "response_size_bytes": len(raw),
            "research_decision_id": "decision-1", "promotion_writes": 0}


def test_completeness_contract_covers_all_formal_stages():
    assert set(COMPLETENESS_REQUIRED) == {"research_agent_raw_response", "research_proposal",
        "factor_template_definition", "factor_optimization_trial_detail", "factor_fold_candidate_lock",
        "factor_candidate_eligibility_evidence"}


def test_missing_required_field_hard_fails():
    with pytest.raises(RuntimeError, match="ARTIFACT_COMPLETENESS_FAILED"):
        assert_complete("research_proposal", {"proposal_id": "p"})


def test_raw_agent_response_exact_bytes_hash_and_store_recovery(tmp_path):
    raw = b'{"schema_version":"1.0.0","decision_id":"d"}'
    local = publish_artifact(tmp_path / "local", "research_agent_raw_response", _raw_identity(raw),
                             {"raw_response.json": raw})
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store")); store.initialize()
    receipt = store.import_artifact("research_agent_raw_response", local["path"],
                                    local["raw_response_artifact_id"], lineage=("mfi1_source",))
    cold = tmp_path / "cold"
    store.materialize_artifact(receipt.descriptor_id, cold)
    assert (cold / "raw_response.json").read_bytes() == raw
    assert validate_artifact(cold, local["raw_response_artifact_id"])["status"] == "valid"


def test_raw_agent_response_hash_tampering_is_rejected(tmp_path):
    raw = b'{"ok":true}'
    local = publish_artifact(tmp_path, "research_agent_raw_response", _raw_identity(raw),
                             {"raw_response.json": raw})
    (Path(local["path"]) / "raw_response.json").write_bytes(b'{"ok":false}')
    with pytest.raises(ValueError, match="hash"):
        validate_artifact(Path(local["path"]), local["raw_response_artifact_id"])


def test_raw_response_secret_markers_are_rejected(tmp_path):
    raw = b'{"TUSHARE_TOKEN":"forbidden"}'
    with pytest.raises(ValueError, match="secret"):
        publish_artifact(tmp_path, "research_agent_raw_response", _raw_identity(raw),
                         {"raw_response.json": raw})


def test_parameter_rows_restore_explicit_parameter_contract():
    proposal = {"template": {"schema_version": "1.0.0", "name": "skip", "description": "x",
        "dataset_kinds": ["momentum_feature_matrix_v1"],
        "parameters": [{"name": "weight", "type": "number", "default": .5, "minimum": .2, "maximum": .8}],
        "expression": {"type": "multiply", "left": {"type": "parameter", "name": "weight"},
                       "right": {"type": "feature", "name": "momentum_60_10"}}, "output": {"name": "score"}},
        "parameter_search": {"parameter_roles": {"weight": "factor_internal_weight"},
                             "search_space": {"weight": {"kind": "explicit_values", "values": [.2, .8]}}}}
    assert _parameter_rows(proposal) == [{"weight": .2}, {"weight": .8}]


def test_candidate_gate_is_independent_from_ensemble_gate():
    ranking = {"positive_rankic_fold_count": 4, "positive_excess_fold_count": 3,
               "median_rankic": .1, "worst_rankic": .01, "median_excess_return": .1,
               "worst_excess_return": .01, "parameter_neighborhood_stability": 1.0,
               "median_return_without_best10": .01, "maximum_drawdown_abs": .1,
               "median_turnover": 1.0}
    eligible = [{"factor_instance_id": "fi1", "structural_fingerprint": "s1", "subfamily": "classic",
                 "maximum_existing_factor_correlation": .1, "ast_depth": 2, "summary": ranking}]
    assert candidate_policy(eligible) == eligible
    assert ensemble_allowed(candidate_policy(eligible)) is False


def test_candidate_policy_caps_three_and_deduplicates_structure():
    ranking = {"positive_rankic_fold_count": 4, "positive_excess_fold_count": 3,
               "median_rankic": .1, "worst_rankic": .01, "median_excess_return": .1,
               "worst_excess_return": .01, "parameter_neighborhood_stability": 1.0,
               "median_return_without_best10": .01, "maximum_drawdown_abs": .1,
               "median_turnover": 1.0}
    rows = [{"factor_instance_id": f"fi{i}", "structural_fingerprint": f"s{i if i < 3 else 2}",
             "subfamily": f"family{i}", "maximum_existing_factor_correlation": .1,
             "ast_depth": 2, "summary": ranking | {"median_rankic": .1-i*.001}} for i in range(5)]
    assert len(candidate_policy(rows)) == 3


def test_research_protocol_is_fixed_and_later_periods_are_reports_only():
    assert len(FOLDS) == 4 and len(SUBFAMILIES) == 6 and len(FEATURES) == 6
    assert BUDGET.max_total_agent_calls == 12 and BUDGET.max_total_templates == 18
    assert BUDGET.max_total_trials == 144
    assert FORMAL_STRATEGY["topk"] == 20 and FORMAL_STRATEGY["n_drop"] == 5
    assert FORMAL_STRATEGY["rebalance_frequency"] == 5 and FORMAL_STRATEGY["benchmark"] == "CSI300"
    assert REPORT_PERIODS == {"2025": ("2025-01-02", "2025-12-31"),
                              "2026H1": ("2026-01-05", "2026-06-23")}


def test_source_authority_ids_are_frozen():
    assert SOURCE_CATALOG_ID.startswith("mfc1_51dc0901")
    assert SOURCE_DATASET_ID.startswith("mfd1_9bb71725")


def test_candidate_lock_rejects_production_claim(tmp_path):
    identity = {"schema_version": "skip-recent-momentum-candidate-lock-v1", "provider_id": "tushare-pro-v1",
                "status": "production", "predictive_claim": False, "fresh_validation": False,
                "usable_for_promotion": False, "eligible_for_production": False, "promotion_writes": 0}
    with pytest.raises(ValueError, match="research-only"):
        publish_artifact(tmp_path, "skip_recent_momentum_candidate_lock", identity, {})


def test_artifact_file_inventory_detects_missing_factor_values(tmp_path):
    identity = {"schema_version": "factor-optimization-trial-detail-v1", "provider_id": "tushare-pro-v1",
        "trial_id": "t", "factor_template_id": "ft", "research_fold": 1, "parameters": {"w": .5},
        "factor_instance_id": "fi", "factor_value_artifact_id": "fv", "trial_metrics": {},
        "failure_reason": None, "selected": True, "promotion_writes": 0}
    artifact = publish_artifact(tmp_path, "factor_optimization_trial_detail", identity,
                                {"trial.json": identity, "factor_values.parquet": b"values"})
    Path(artifact["path"], "factor_values.parquet").unlink()
    with pytest.raises(ValueError, match="inventory"):
        validate_artifact(Path(artifact["path"]), artifact["trial_detail_id"])
