import json

import pytest

from backend.services.engine.factor_registry import RegistryStatus
from backend.services.engine.factor_registry.models import RegistryEntry
from backend.services.engine.factor_registry.parser import entry_payload, parse_entry
from backend.services.engine.research_campaign.artifact import CampaignJournal, validate_campaign
from backend.services.engine.research_campaign.errors import CampaignArtifactError


def entry(evidence=None):
    return RegistryEntry("fi_" + "1"*64, "ft_" + "2"*64, "test", {"window": 5}, "ds_" + "3"*64,
        ("fv_" + "4"*64,), "fos_" + "5"*64, "fot_" + "6"*64, None, None, None, None, 1,
        RegistryStatus.RESEARCH_REGISTERED, ("research_only",), None, None, {"x": "7"*64}, "ft_" + "2"*64,
        ("research-campaign-v1",), None, evidence)


def result():
    return {"result_id": "rcr_" + "c"*64, "iterations": 0, "agent_calls": 0, "admitted_proposals": 0,
        "total_trials": 0, "failed_proposals": 0, "failed_trials": 0, "development_is_contaminated": True,
        "validation_evidence_created": False, "frozen_evidence_created": False, "promotion_candidate_added": 0,
        "approved_added": 0, "active_added": 0}


def test_legacy_registry_entry_payload_omits_optional_research_evidence():
    payload = entry_payload(entry())
    assert "research_evidence" not in payload
    assert parse_entry(payload).research_evidence is None


def test_research_registry_entry_round_trip():
    evidence = {"campaign_id": "rc_"+"a"*64, "research_goal_id": "rg_"+"b"*64, "research_decision_id": "rd_"+"c"*64,
        "development_evaluation_id": "der_"+"d"*64, "development_is_contaminated": True,
        "is_validation_evidence": False, "is_frozen_evidence": False}
    assert parse_entry(entry_payload(entry(evidence))).research_evidence == evidence


def test_research_registry_entry_cannot_claim_formal_evidence():
    evidence = {"campaign_id": "rc_"+"a"*64, "research_goal_id": "rg_"+"b"*64, "research_decision_id": "rd_"+"c"*64,
        "development_evaluation_id": "der_"+"d"*64, "development_is_contaminated": True,
        "is_validation_evidence": True, "is_frozen_evidence": False}
    with pytest.raises(Exception): parse_entry(entry_payload(entry(evidence)))


def test_campaign_artifact_publish_reload_and_exact_existing(tmp_path):
    journal = CampaignJournal(tmp_path, "rc_" + "a" * 64)
    journal.event("created"); journal.event("completed", reason="test")
    artifact = journal.publish({"goal.json": {"goal_id": "rg_x"}, "result.json": result(),
                                "memory.json": {"development_results": []}, "sanitized_memory.json": {}})
    assert artifact["result"]["result_id"].startswith("rcr_")
    assert validate_campaign(tmp_path, artifact["campaign_id"])["campaign_id"] == artifact["campaign_id"]


def test_campaign_artifact_detects_hash_drift(tmp_path):
    journal = CampaignJournal(tmp_path, "rc_" + "b" * 64); journal.event("created"); journal.event("completed")
    artifact = journal.publish({"goal.json": {}, "result.json": result(),
                                "memory.json": {"development_results": []}, "sanitized_memory.json": {}})
    (tmp_path / "campaigns" / artifact["campaign_id"] / "goal.json").write_text("{}")
    with pytest.raises(CampaignArtifactError): validate_campaign(tmp_path, artifact["campaign_id"])
