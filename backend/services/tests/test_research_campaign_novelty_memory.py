from copy import deepcopy

from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.research_campaign.agent import baseline_proposals
from backend.services.engine.research_campaign.memory import sanitize_memory
from backend.services.engine.research_campaign.novelty import structural_fingerprint


def template(): return baseline_proposals(1)[0]["template"]


def fingerprint(payload): return structural_fingerprint(parse_template(payload))


def test_novelty_ignores_name_description_default_and_range():
    left = template(); right = deepcopy(left)
    right["name"] = "renamed"; right["description"] = "Different description."
    right["output"]["name"] = "renamed"; right["parameters"][0].update(default=7, minimum=2, maximum=20)
    assert fingerprint(left) == fingerprint(right)


def test_add_commutativity():
    item = deepcopy(baseline_proposals(1)[1]["template"]); swapped = deepcopy(item)
    node = swapped["expression"]; node["left"], node["right"] = node["right"], node["left"]
    assert fingerprint(item) == fingerprint(swapped)


def test_multiply_commutativity():
    item = deepcopy(baseline_proposals(1)[1]["template"]); swapped = deepcopy(item)
    node = swapped["expression"]["left"]; node["left"], node["right"] = node["right"], node["left"]
    assert fingerprint(item) == fingerprint(swapped)


def test_novel_structure_differs():
    assert fingerprint(baseline_proposals(1)[0]["template"]) != fingerprint(baseline_proposals(2)[0]["template"])


def test_memory_is_stable_and_has_no_evidence_details():
    events = [{"event_type": "proposal_completed", "proposal_id": "p1", "development_mean_rank_ic": 0.01,
               "development_rank_icir": 0.2}]
    first = sanitize_memory(events, {"nfp_b", "nfp_a"}); second = sanitize_memory(events, {"nfp_a", "nfp_b"})
    assert first == second
    rendered = str(first).lower()
    for forbidden in ("frozen_result_id", "frozen_mean", "raw_label", "model_label"):
        assert forbidden not in rendered
    assert "warning" in first["development_feedback"][0]
