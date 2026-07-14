"""Pure helpers for single relationships and direct reverse conflicts."""

from __future__ import annotations

from collections.abc import Iterable

from .enums import RunRelationshipType
from .errors import InvalidRunRelationshipError


_RELATIONSHIP_SEMANTICS = {
    RunRelationshipType.FINALIZES: "source records finalization work for target without changing target",
    RunRelationshipType.CORRECTS: "source corrects target by adding new immutable evidence",
    RunRelationshipType.SUPERSEDES: "source replaces target for future use without deleting target",
    RunRelationshipType.DEPENDS_ON: "source requires target as prior implementation evidence",
    RunRelationshipType.RETRIES: "source is a new run retrying target after a terminal outcome",
    RunRelationshipType.CONTINUES: "source continues incomplete work recorded by target",
}


def relationship_semantics(relationship_type: RunRelationshipType) -> str:
    try:
        return _RELATIONSHIP_SEMANTICS[RunRelationshipType(relationship_type)]
    except (KeyError, ValueError) as exc:
        raise InvalidRunRelationshipError("unsupported relationship type", field="relationship_type") from exc


def has_direct_reverse_conflict(candidate, existing) -> bool:
    """Return true for a direct two-node reverse edge, regardless of edge kind."""
    return (
        candidate.source_run_id == existing.target_run_id
        and candidate.target_run_id == existing.source_run_id
    )


def validate_direct_relationship(candidate, existing_relationships: Iterable = ()):  # noqa: ANN001
    """Validate one edge and reject only directly reversed existing edges.

    Complete graph cycle detection and uniqueness belong to the future
    Repository layer.
    """
    if candidate.source_run_id == candidate.target_run_id:
        raise InvalidRunRelationshipError("source and target runs must differ", field="target_run_id")
    for existing in existing_relationships:
        if has_direct_reverse_conflict(candidate, existing):
            raise InvalidRunRelationshipError("direct reverse relationship conflicts", field="relationship_id")
    return candidate
