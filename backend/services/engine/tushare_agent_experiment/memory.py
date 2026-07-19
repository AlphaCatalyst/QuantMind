from __future__ import annotations

from typing import Any, Mapping

from backend.services.engine.tushare_cutover.canonical import hash_payload


FORBIDDEN = {
    "daily_ic",
    "daily_rank_ic",
    "daily_labels",
    "label_rows",
    "holdout_2025",
    "holdout_2026h1",
    "future_qlib_result",
    "single_stock_return",
}


def _validate_fields(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN or "frozen" in normalized or "future" in normalized:
                raise ValueError("historical as-of memory contains forbidden field: " + ".".join((*path, str(key))))
            _validate_fields(item, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_fields(item, (*path, str(index)))


def build_memory(
    *,
    round_number: int,
    research_end: str,
    sanitized_source: Mapping[str, Any],
    prior_templates: list[dict],
    prior_feedback: list[dict],
    fingerprints: set[str],
) -> dict:
    if sanitized_source.get("historical_metrics_invalidated_by_data_authority_cutover") is not True:
        raise ValueError("sanitized memory does not invalidate old authority metrics")
    payload = {
        "schema_version": "tushare-historical-as-of-memory-v1",
        "provider_id": "tushare-pro-v1",
        "round_number": round_number,
        "visibility_cutoff": research_end,
        "historical_metrics_invalidated_by_data_authority_cutover": True,
        "allowed_features": [
            "liq_volume_ratio_5",
            "mom_ret_1d",
            "style_beta_20",
            "style_idio_vol_20",
        ],
        "retained_cross_authority_categories": list(sanitized_source["retained_categories"]),
        "prior_templates": prior_templates,
        "prior_aggregate_feedback": prior_feedback,
        "known_structure_fingerprints": sorted(fingerprints),
        "daily_series_included": False,
        "holdout_feedback_included": False,
        "label_rows_included": False,
        "old_metrics_included": False,
    }
    _validate_fields(payload)
    return payload | {"memory_id": "tham_" + hash_payload(payload)}


def validate_memory(memory: Mapping[str, Any], round_number: int, research_end: str) -> bool:
    _validate_fields(memory)
    if memory.get("round_number") != round_number or memory.get("visibility_cutoff") != research_end:
        raise ValueError("historical as-of memory window mismatch")
    for field in ("daily_series_included", "holdout_feedback_included", "label_rows_included", "old_metrics_included"):
        if memory.get(field) is not False:
            raise ValueError("historical as-of memory disclosure flag is unsafe")
    stable = {key: value for key, value in memory.items() if key != "memory_id"}
    if memory.get("memory_id") != "tham_" + hash_payload(stable):
        raise ValueError("historical as-of memory identity mismatch")
    return True
