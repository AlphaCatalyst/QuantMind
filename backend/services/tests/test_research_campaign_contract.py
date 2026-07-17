import json

import pytest

from backend.services.engine.research_campaign.agent import BaselineResearchAgent
from backend.services.engine.research_campaign.decision import parse_decision
from backend.services.engine.research_campaign.errors import AgentContractError, ResearchCampaignError
from backend.services.engine.research_campaign.goal import parse_goal
from backend.services.engine.research_campaign.models import ResearchAgentRequest, ResearchCampaignBudget


GOAL_PATH = "docs/quantmind2/implementation/examples/research_goal_v1.json"


def goal(): return parse_goal(GOAL_PATH)


def valid_raw():
    request = ResearchAgentRequest({"goal_id": goal().goal_id}, {}, {"iteration": 1})
    return BaselineResearchAgent().propose(request).raw_response


def parse(raw):
    return parse_decision(raw, iteration=1, goal=goal(), budget=ResearchCampaignBudget(),
                          provider_id="test", model_id="test-v1")


def test_goal_identity_and_closed_schema():
    assert goal().goal_id.startswith("rg_")


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra=True), lambda p: p.update(goal_id="rg_" + "0" * 64),
    lambda p: p.update(maximum_iterations=0), lambda p: p.update(objective="generate Python"),
])
def test_goal_rejects_invalid_contract(mutation):
    payload = json.load(open(GOAL_PATH)); mutation(payload)
    with pytest.raises(ResearchCampaignError): parse_goal(payload)


def test_valid_agent_json_and_system_decision_id():
    decision = parse(valid_raw())
    assert decision["decision_id"].startswith("rd_")
    assert decision["decision_id"] != decision["agent_supplied_decision_id"]


@pytest.mark.parametrize("raw", ["not json", "{} trailing", "```json\n{}\n```", '{"x":NaN}', "x" * 65537])
def test_agent_response_rejects_malformed_or_unbounded(raw):
    with pytest.raises(AgentContractError): parse(raw)


@pytest.mark.parametrize("needle", ["https://example.invalid", "/private/tmp/data", "import os", "api_key=secret", "bash rm -rf work"])
def test_agent_response_rejects_unsafe_proposal_text(needle):
    payload = json.loads(valid_raw()); payload["proposals"][0]["rationale"] = needle
    with pytest.raises(AgentContractError): parse(json.dumps(payload))


def test_agent_response_rejects_unknown_field():
    payload = json.loads(valid_raw()); payload["unexpected"] = True
    with pytest.raises(AgentContractError): parse(json.dumps(payload))


def test_agent_response_rejects_parameter_mismatch():
    payload = json.loads(valid_raw()); payload["proposals"][0]["parameter_search"]["parameter_roles"] = {"unknown": "lookback_window"}
    with pytest.raises(AgentContractError): parse(json.dumps(payload))


def test_budget_hard_caps():
    ResearchCampaignBudget().validate()
    with pytest.raises(ValueError): ResearchCampaignBudget(max_iterations=4).validate()
    with pytest.raises(ValueError): ResearchCampaignBudget(max_total_trials=65).validate()
