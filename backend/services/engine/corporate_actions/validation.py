from __future__ import annotations

import json
from pathlib import Path

from .enums import EvidenceCompleteness
from .raw_artifact import validate_corporate_action_artifact


REQUIRED_FILES = {
    "tushare_corporate_action_raw": {
        "requests.json", "events.parquet", "announcements.parquet", "quality.json",
    },
    "security_corporate_action_event": {
        "normalized_events.json", "evidence_assessment.json",
    },
    "fixed_universe_benchmark_contract": {"benchmark_contract.json"},
    "fixed_universe_benchmark_revision": {
        "event_cashflows.parquet", "event_positions.parquet", "benchmark_daily.parquet",
        "metric_revision.json", "canonicality.json",
    },
    "historical_backtest_benchmark_followup": {
        "metric_revision.json", "canonicality.json",
    },
}


def validate_domain_artifact(root: Path, expected_id: str, kind: str) -> dict:
    result = validate_corporate_action_artifact(root, expected_id, expected_kind=kind)
    manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest["file_hashes"]) != REQUIRED_FILES[kind]:
        raise ValueError("corporate-action required file inventory mismatch")
    if kind == "tushare_corporate_action_raw":
        quality = json.loads((Path(root) / "quality.json").read_text(encoding="utf-8"))
        if quality.get("safe_errors_only") is not True:
            raise ValueError("raw corporate-action error evidence is unsafe")
    elif kind == "security_corporate_action_event":
        payload = json.loads((Path(root) / "normalized_events.json").read_text(encoding="utf-8"))
        events = payload.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("normalized corporate-action events are absent")
        required = {
            "event_id", "symbol", "event_type", "announcement_date",
            "last_tradable_date", "effective_date", "settlement_date",
            "cash_per_share", "replacement_symbol", "conversion_ratio",
            "residual_cash_per_share", "source_artifact_id", "source_record_id",
            "evidence_hash", "evidence_completeness",
        }
        if any(set(event) != required for event in events):
            raise ValueError("normalized corporate-action event schema mismatch")
        if any(event["evidence_completeness"] not in {
            member.value for member in EvidenceCompleteness
        } for event in events):
            raise ValueError("corporate-action evidence completeness is invalid")
    elif kind == "fixed_universe_benchmark_contract":
        contract = json.loads((Path(root) / "benchmark_contract.json").read_text(encoding="utf-8"))
        if (
            contract.get("weighting") != "equal_weight"
            or contract.get("replacement_policy") != "no_locked_universe_replacement"
            or contract.get("settlement_asset_membership")
            != "settlement_asset_is_not_a_new_locked_member"
        ):
            raise ValueError("Fixed Universe Benchmark Contract governance mismatch")
    return result

