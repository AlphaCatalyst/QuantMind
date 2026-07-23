from __future__ import annotations

from collections import Counter

from .models import FAILURE_TAXONOMY


def initial_memory() -> dict:
    return {
        "schema_version": "campaign-research-memory-v1", "rounds_completed": 0,
        "families_attempted": [], "structures_attempted": [],
        "admission_failures": {}, "development_failures": {}, "annual_failures": {},
        "successful_mechanisms": [], "repeated_failures": {}, "underexplored_families": [],
        "novelty_map": {}, "budget_usage": {}, "temporarily_frozen_families": [],
        "consecutive_no_admission": 0, "consecutive_no_development_improvement": 0,
        "daily_labels_included": False, "daily_returns_included": False,
        "daily_ic_included": False, "single_stock_contributions_included": False,
        "report_period_feedback_included": False, "fresh_forward_evidence_included": False,
    }


def update_memory(memory: dict, round_result: dict, budget_usage: dict) -> dict:
    value = dict(memory)
    value["rounds_completed"] = int(value.get("rounds_completed", 0)) + 1
    value["families_attempted"] = list(value.get("families_attempted", [])) + [round_result["theme"]]
    value["structures_attempted"] = list(value.get("structures_attempted", [])) + list(round_result.get("structural_fingerprints", []))
    failures = Counter(value.get("repeated_failures", {}))
    for code in round_result.get("failure_codes", []):
        if (code in FAILURE_TAXONOMY and code != "report_period_degradation") or code == "AGENT_DEFAULT_PARAMETERS_MISSING":
            failures[code] += 1
    value["repeated_failures"] = dict(sorted(failures.items()))
    value["admission_failures"] = dict(Counter(value.get("admission_failures", {})) + Counter(round_result.get("admission_failure_codes", [])))
    value["development_failures"] = dict(Counter(value.get("development_failures", {})) + Counter(round_result.get("development_failure_codes", [])))
    value["annual_failures"] = dict(Counter(value.get("annual_failures", {})) + Counter(round_result.get("annual_failure_codes", [])))
    admitted = int(round_result.get("admitted_count", 0))
    locks = int(round_result.get("development_lock_count", 0))
    value["consecutive_no_admission"] = 0 if admitted else int(value.get("consecutive_no_admission", 0)) + 1
    value["consecutive_no_development_improvement"] = 0 if locks else int(value.get("consecutive_no_development_improvement", 0)) + 1
    family_failures = [code for code in round_result.get("failure_codes", []) if code in {"duplicate_structure", "duplicate_signal", "weak_predictive_signal"}]
    frozen = set(value.get("temporarily_frozen_families", []))
    if len(family_failures) >= 2:
        frozen.add(round_result["theme"])
    value["temporarily_frozen_families"] = sorted(frozen)
    value["budget_usage"] = dict(budget_usage)
    return value
