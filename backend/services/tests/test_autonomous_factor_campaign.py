from __future__ import annotations

import json

import pytest

from backend.services.engine.artifact_store.config import resolve_config
from backend.services.engine.artifact_store.store import FileSystemResearchArtifactStore
from backend.services.engine.autonomous_factor_campaign.admission import admit_proposal
from backend.services.engine.autonomous_factor_campaign.artifact import publish_artifact, validate_artifact
from backend.services.engine.autonomous_factor_campaign.failure_memory import initial_memory, update_memory
from backend.services.engine.autonomous_factor_campaign.models import (
    AutonomousFactorCampaignSpecV1,
    CampaignBudget,
    empty_budget_usage,
)
from backend.services.engine.autonomous_factor_campaign.orchestrator import (
    _recover_interrupted_agent_round,
)
from backend.services.engine.autonomous_factor_campaign.planner import early_stop_reason, plan_next_round
from backend.services.engine.research_campaign.agent import baseline_proposals


OPERATORS = {
    "add", "subtract", "multiply", "divide", "negate", "absolute", "delta",
    "rolling_mean", "rolling_std", "rolling_min", "rolling_max", "cs_rank", "cs_zscore",
}


def test_frozen_spec_identity_and_budget():
    payload = AutonomousFactorCampaignSpecV1().payload()
    assert payload["campaign_spec_id"].startswith("afc1_")
    assert payload["budgets"]["maximum_agent_calls"] == 12
    assert payload["fresh_validation"] is False
    with pytest.raises(ValueError):
        AutonomousFactorCampaignSpecV1(budgets=CampaignBudget(maximum_agent_calls=13)).payload()


def test_planner_uses_aggregate_memory_and_never_report_or_fresh():
    memory = initial_memory()
    memory["repeated_failures"] = {"high_turnover": 2}
    plan = plan_next_round(memory, 2)
    assert plan["theme"] in {"path_quality", "multi_horizon_trend"}
    assert plan["uses_report_period_evidence"] is False
    assert plan["uses_fresh_forward_evidence"] is False
    assert plan["manual_planning"] is False


def test_admission_limits_defaults_and_structural_duplicates():
    source = dict(baseline_proposals(1)[0])
    source["_round_number"] = 1
    source["_factor_family"] = "multi_horizon_trend"
    result = admit_proposal(
        source,
        allowed_features={"mom_ret_1d", "style_idio_vol_20"},
        allowed_operators=OPERATORS,
        known_fingerprints=set(),
    )
    assert result["admitted"] is True
    duplicate = admit_proposal(
        source,
        allowed_features={"mom_ret_1d", "style_idio_vol_20"},
        allowed_operators=OPERATORS,
        known_fingerprints={result["proposal"]["structural_fingerprint"]},
    )
    assert duplicate["failure_code"] == "duplicate_structure"
    assert result["proposal"]["default_parameters"] == {"window": 5}


def test_failure_memory_and_early_stops_are_bounded():
    memory = initial_memory()
    usage = {
        "rounds": 1, "agent_calls": 1, "proposals": 1, "admitted_templates": 0,
        "local_rescue_trials": 0, "formal_qlib_calls": 0, "candidate_locks": 0,
    }
    row = {
        "theme": "path_quality", "failure_codes": ["duplicate_structure"],
        "admission_failure_codes": ["duplicate_structure"], "development_failure_codes": [],
        "annual_failure_codes": [], "admitted_count": 0, "development_lock_count": 0,
    }
    for _ in range(3):
        memory = update_memory(memory, row, usage)
    assert memory["consecutive_no_admission"] == 3
    assert early_stop_reason(memory, usage, AutonomousFactorCampaignSpecV1().payload()["budgets"]) == "novelty_exhausted"
    assert memory["report_period_feedback_included"] is False
    assert memory["fresh_forward_evidence_included"] is False


def test_artifact_is_immutable_store_validated_and_secret_free(tmp_path):
    identity = {
        "schema_version": "autonomous-round-plan-v1", "provider_id": "tushare-pro-v1",
        "campaign_spec_id": "afc1_test", "round_number": 1, "theme": "path_quality",
        "promotion_writes": 0,
    }
    artifact = publish_artifact(tmp_path / "domain", "autonomous_factor_round_plan", identity, {"round_plan.json": identity})
    artifact_id = artifact["round_plan_id"]
    assert validate_artifact(artifact["path"], artifact_id)["status"] == "valid"
    store = FileSystemResearchArtifactStore(resolve_config(tmp_path / "store"))
    store.initialize()
    receipt = store.import_artifact("autonomous_factor_round_plan", artifact["path"], artifact_id)
    assert store.find_by_artifact_id(artifact_id).descriptor_id == receipt.descriptor_id
    path = __import__("pathlib").Path(artifact["path"])
    assert json.loads((path / "round_plan.json").read_text())["promotion_writes"] == 0


def test_report_period_failure_cannot_become_planner_feedback():
    memory = initial_memory()
    row = {
        "theme": "path_quality", "failure_codes": ["report_period_degradation"],
        "admission_failure_codes": [], "development_failure_codes": [],
        "annual_failure_codes": [], "admitted_count": 1, "development_lock_count": 1,
    }
    updated = update_memory(memory, row, {})
    assert "report_period_degradation" not in updated["repeated_failures"]
    plan = plan_next_round(updated, 2)
    assert plan["reason"] == "failure_memory_and_underexplored_family_priority"


def test_interrupted_agent_checkpoint_closes_round_without_repeating_call():
    class Repository:
        def __init__(self):
            self.published = []

        def identities_by_kind(self, kind, _campaign_id):
            if kind == "autonomous_factor_round_plan":
                return [{
                    "artifact_id": "afrp1_plan", "round_number": 1,
                    "theme": "path_quality",
                }]
            if kind == "autonomous_factor_proposal":
                return [{
                    "artifact_id": "afp1_response", "round_number": 1,
                    "record_type": "agent_response",
                }]
            return []

        def publish(self, kind, identity, _files, lineage=()):
            self.published.append((kind, identity, lineage))
            return {"artifact_id": f"{kind}-id"}

    usage = empty_budget_usage()
    usage["agent_calls"] = 1
    state = {
        "campaign_spec_id": "afc1_test",
        "state": "paused_recoverable_error",
        "checkpoint_sequence": 1,
        "budget_usage": usage,
        "round_artifact_ids": [],
        "candidate_lock_ids": [],
        "near_miss_ids": [],
        "known_fingerprints": [],
        "eligible_candidate_refs": [],
        "memory": initial_memory(),
        "memory_id": None,
        "report_id": None,
        "stop_reason": "CodexProviderError: interrupted after provider call",
        "manual_intervention_count": 0,
        "manual_round_planning_count": 0,
    }
    repository = Repository()

    _recover_interrupted_agent_round(repository, state)

    assert state["budget_usage"]["agent_calls"] == 1
    assert state["budget_usage"]["rounds"] == 1
    assert state["state"] == "running"
    round_record = next(item for item in repository.published if item[0] == "autonomous_factor_round")
    assert round_record[1]["agent_call"]["call_repeated"] is False
    assert round_record[1]["fresh_forward_evidence_used"] is False
    assert round_record[1]["report_period_feedback_used"] is False
