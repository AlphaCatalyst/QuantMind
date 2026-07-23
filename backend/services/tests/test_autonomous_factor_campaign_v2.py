from __future__ import annotations

import json

import pytest

from backend.services.engine.autonomous_factor_campaign.artifact import publish_artifact, validate_artifact
from backend.services.engine.autonomous_factor_campaign.models_v2 import (
    AutonomousFactorCampaignSpecV2, evidence_partitions,
)
from backend.services.engine.autonomous_factor_campaign.orchestrator_v2 import (
    LockedHoldoutAccessControllerV1, _ordering,
)
from backend.services.engine.autonomous_factor_campaign.planner_v2 import (
    plan_next_round_v2,
)


def test_v2_spec_is_frozen_and_bounded():
    value = AutonomousFactorCampaignSpecV2().payload()
    assert value["campaign_spec_id"].startswith("afc2_")
    assert value["campaign_name"] == "technical_factor_campaign_002"
    assert value["budgets"]["maximum_holdout_qlib_calls"] == 12


def test_evidence_partition_contract_is_deny_by_default_for_late_evidence():
    rows = evidence_partitions()["partitions"]
    assert rows["development"]["usable_for_parameter_selection"]
    assert rows["adaptive_discovery"]["usable_by_planner"]
    for name in ("locked_holdout", "contaminated_report", "fresh_forward"):
        assert not rows[name]["usable_by_agent"]
        assert not rows[name]["usable_by_planner"]
        assert not rows[name]["usable_by_failure_memory"]
    assert rows["locked_holdout"]["usable_for_registry"]


def test_planner_prioritizes_underexplored_family_without_late_evidence():
    plan = plan_next_round_v2({"families_attempted": [], "repeated_failures": {}}, 1)
    assert plan["theme"] == "volume_price_confirmation"
    assert plan["input_evidence_partitions"] == ["development", "adaptive_discovery"]
    assert not plan["uses_locked_holdout_evidence"]


def test_v1_saturated_family_is_limited_to_one_round():
    memory = {
        "families_attempted": [
            "volume_price_confirmation", "volume_price_confirmation", "volume_price_confirmation",
            "volatility_conditioned_trend", "volatility_conditioned_trend", "volatility_conditioned_trend",
            "liquidity_normalized_trend", "liquidity_normalized_trend", "liquidity_normalized_trend",
            "pullback_continuation", "pullback_continuation", "pullback_continuation",
            "multi_horizon_trend", "multi_horizon_trend", "multi_horizon_trend",
            "cross_family_simple_hybrid", "cross_family_simple_hybrid", "cross_family_simple_hybrid",
            "path_quality", "path_quality", "path_quality",
            "drawdown_recovery",
        ],
        "temporarily_frozen_families": [],
    }
    assert plan_next_round_v2(memory, 22)["theme"] == "residual_relative_strength"


def _access_state(**updates):
    value = {
        "rounds_stopped": True, "shortlist_lock_id": "acsl1_x",
        "memory_freeze_id": "acfmf1_x", "agent_closed": True,
        "planner_closed": True, "parameters_frozen": True,
        "budget_usage": {"locked_holdout_reads": 0},
    }
    value.update(updates)
    return value


@pytest.mark.parametrize(
    "field",
    ("rounds_stopped", "shortlist_lock_id", "memory_freeze_id",
     "agent_closed", "planner_closed", "parameters_frozen"),
)
def test_holdout_access_requires_every_frozen_precondition(field):
    state = _access_state(**{field: False})
    with pytest.raises(ValueError, match="LOCKED_HOLDOUT_EVIDENCE_CONTAMINATION"):
        LockedHoldoutAccessControllerV1(state).open()


def test_holdout_access_opens_once_only():
    state = _access_state()
    LockedHoldoutAccessControllerV1(state).open()
    assert state["holdout_opened"]
    state["budget_usage"]["locked_holdout_reads"] = 1
    with pytest.raises(ValueError, match="LOCKED_HOLDOUT_ALREADY_OPENED"):
        LockedHoldoutAccessControllerV1(state).open()


def test_capacity_ordering_uses_discovery_not_holdout():
    def row(rankic, excess, instance):
        return {
            "proposal": {"complexity_statement": {"ast_depth": 2}},
            "search_exposure": {"search_risk_class": "low_search_exposure"},
            "evaluation": {
                "summary": {
                    "positive_rankic_year_count": 2, "positive_excess_year_count": 1,
                    "median_rankic": rankic, "median_excess": excess,
                    "maximum_old_factor_correlation": .1,
                },
                "development_lock": {
                    "optimization_mode": "default_parameters", "factor_instance_id": instance,
                },
            },
        }
    assert sorted([row(.01, .02, "b"), row(.02, .01, "a")], key=_ordering)[0][
        "evaluation"
    ]["development_lock"]["factor_instance_id"] == "a"


def test_v2_artifact_identity_is_immutable(tmp_path):
    identity = {
        "schema_version": "campaign-evidence-partition-v1",
        "provider_id": "tushare-pro-v1", "campaign_spec_id": "afc2_test",
        "partitions": evidence_partitions()["partitions"], "promotion_writes": 0,
    }
    artifact = publish_artifact(
        tmp_path, "campaign_evidence_partition", identity,
        {"evidence_partitions.json": identity},
    )
    assert validate_artifact(
        artifact["path"], artifact["evidence_partition_id"],
        "campaign_evidence_partition",
    )["status"] == "valid"
    manifest = json.loads((tmp_path / "campaign_evidence_partition" /
                           artifact["evidence_partition_id"] / "manifest.json").read_text())
    assert "manifest.json" not in manifest["file_hashes"]


def test_clean_room_contract_contains_no_late_metric_field_names():
    serialized = json.dumps(evidence_partitions(), sort_keys=True)
    assert "metric_2023" not in serialized
    assert "fresh_result" not in serialized
