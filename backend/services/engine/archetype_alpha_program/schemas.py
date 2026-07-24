from __future__ import annotations

from backend.services.engine.research_campaign.decision import decision_json_schema


def alpha_agent_schema() -> dict:
    schema = decision_json_schema()
    proposal = schema["properties"]["proposals"]["items"]
    extra = {
        "lane_id": {"type": "string"},
        "round_id": {"type": "string"},
        "factor_family": {"type": "string"},
        "primary_archetype": {"enum": ["monotonic_rank_factor", "top_tail_selection_factor"]},
        "primary_hypothesis": {"type": "string"},
        "primary_test_statistic": {
            "enum": ["daily_official_label_rankic", "non_overlapping_top20_universe_10_session_spread"]
        },
        "expected_holding_horizon": {"type": "string"},
    }
    proposal["properties"].update(extra)
    proposal["required"].extend(extra)
    schema["properties"]["proposals"]["maxItems"] = 3
    return schema
