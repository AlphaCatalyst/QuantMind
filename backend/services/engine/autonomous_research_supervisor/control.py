from __future__ import annotations

from typing import Any


def global_stop_decision(*, consecutive_cycles_without_new_feature: int,
                         consecutive_cycles_without_candidate: int,
                         novelty_exhausted: bool,
                         active_fresh_candidates: int,
                         maximum_active_fresh_candidates: int = 20) -> dict[str, Any]:
    if active_fresh_candidates >= maximum_active_fresh_candidates:
        return {"stop": True, "reason": "active_fresh_capacity_reached"}
    if novelty_exhausted:
        return {"stop": True, "reason": "authorized_global_novelty_exhausted"}
    if (
        consecutive_cycles_without_new_feature >= 2
        and consecutive_cycles_without_candidate >= 2
    ):
        return {"stop": True, "reason": "two_empty_research_cycles"}
    return {"stop": False, "reason": None}


def deduplicate_incremental_rows(rows: list[dict[str, Any]],
                                 keys: tuple[str, ...]) -> list[dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        identity = tuple(row.get(key) for key in keys)
        if any(value is None for value in identity):
            raise ValueError("incremental row is missing a deduplication key")
        indexed[identity] = dict(row)
    return [indexed[key] for key in sorted(indexed)]
