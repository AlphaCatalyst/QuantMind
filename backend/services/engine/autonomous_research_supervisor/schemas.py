from __future__ import annotations

import json
from typing import Any

from .models import FRESH_STATES


FORBIDDEN_SECRET_MARKERS = (
    "tushare_token",
    "token_hash",
    "token_prefix",
    "token_suffix",
    "access_token",
    "api_key",
)


def validate_safe_payload(payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, sort_keys=True).lower()
    if any(marker in rendered for marker in FORBIDDEN_SECRET_MARKERS):
        raise ValueError("Supervisor payload contains forbidden credential material")
    if payload.get("promotion_writes", 0) != 0:
        raise ValueError("Supervisor crossed Promotion boundary")


def validate_candidate(candidate: dict[str, Any]) -> None:
    required = {
        "candidate_id", "source_cycle_id", "formula", "parameters", "orientation",
        "archetype", "primary_statistic", "historical_metrics", "search_exposure",
        "multiple_testing_evidence", "correlations", "historical_date_max",
        "project_contamination_ledger_id", "status",
    }
    if not required.issubset(candidate):
        raise ValueError("Retrospective Candidate contract is incomplete")
    if candidate["status"] != "retrospective_candidate":
        raise ValueError("historical evidence may only create retrospective_candidate")
    validate_safe_payload(candidate)


def validate_fresh_status(status: str) -> None:
    if status not in FRESH_STATES:
        raise ValueError("unsupported Fresh status")
