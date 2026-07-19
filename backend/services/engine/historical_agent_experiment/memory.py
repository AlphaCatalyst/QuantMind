from __future__ import annotations

from typing import Any, Iterable, Mapping

from .canonical import hash_payload


FORBIDDEN_KEYS = {
    "daily_ic", "daily_rank_ic", "daily_labels", "label_rows", "fresh_metrics",
    "frozen_metrics", "holdout_2025", "holdout_2026h1", "source_path", "artifact_path",
}


def _walk(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {"daily_series_included", "holdout_feedback_included",
                              "fresh_or_frozen_evidence_included"} and item is False:
                continue
            if normalized in FORBIDDEN_KEYS or "frozen" in normalized or "fresh" in normalized:
                raise ValueError("historical as-of memory contains a forbidden field: " + ".".join((*path, str(key))))
            _walk(item, (*path, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _walk(item, (*path, str(index)))


def build_as_of_memory(*, round_number: int, research_end: str, allowed_features: Iterable[str],
                       prior_templates: Iterable[Mapping[str, Any]],
                       prior_feedback: Iterable[Mapping[str, Any]],
                       structure_fingerprints: Iterable[str]) -> dict:
    payload = {
        "schema_version": "historical-as-of-research-memory-v1",
        "round_number": int(round_number), "research_end": research_end,
        "visibility_cutoff": research_end,
        "allowed_features": sorted(set(allowed_features)),
        "prior_templates": list(prior_templates),
        "prior_aggregate_feedback": list(prior_feedback),
        "known_structure_fingerprints": sorted(set(structure_fingerprints)),
        "daily_series_included": False, "holdout_feedback_included": False,
        "fresh_or_frozen_evidence_included": False,
    }
    _walk(payload)
    return {**payload, "memory_id": "harm_" + hash_payload(payload)}


def validate_as_of_memory(memory: Mapping[str, Any], *, expected_round: int,
                          expected_research_end: str) -> bool:
    _walk(memory)
    if memory.get("schema_version") != "historical-as-of-research-memory-v1":
        raise ValueError("historical as-of memory schema mismatch")
    if memory.get("round_number") != expected_round or memory.get("research_end") != expected_research_end:
        raise ValueError("historical as-of memory window mismatch")
    if any(memory.get(key) is not False for key in (
            "daily_series_included", "holdout_feedback_included", "fresh_or_frozen_evidence_included")):
        raise ValueError("historical as-of memory disclosure flags are unsafe")
    identity = {key: value for key, value in memory.items() if key != "memory_id"}
    if memory.get("memory_id") != "harm_" + hash_payload(identity):
        raise ValueError("historical as-of memory identity mismatch")
    return True
