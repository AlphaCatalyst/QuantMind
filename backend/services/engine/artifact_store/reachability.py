from __future__ import annotations

from datetime import datetime, timezone

from .canonical import hash_payload
from .models import ResearchArtifactReachabilityPlan


def build_reachability_plan(
    *,
    root_ids: tuple[str, ...],
    lineage_by_artifact_id: dict[str, tuple[str, ...]],
    available_artifact_ids: tuple[str, ...],
    optional_artifact_ids: tuple[str, ...] = (),
) -> ResearchArtifactReachabilityPlan:
    available = set(available_artifact_ids)
    optional = set(optional_artifact_ids)
    reachable: set[str] = set()
    missing: set[str] = set()
    unresolved: set[str] = set()
    visiting: set[str] = set()

    def visit(identity: str) -> None:
        if identity in visiting:
            unresolved.add(f"cycle:{identity}")
            return
        if identity in reachable or identity in missing:
            return
        visiting.add(identity)
        if identity not in available:
            if identity not in optional:
                missing.add(identity)
            visiting.remove(identity)
            return
        reachable.add(identity)
        for dependency in sorted(lineage_by_artifact_id.get(identity, ())):
            if dependency not in lineage_by_artifact_id and dependency not in available:
                if dependency not in optional:
                    unresolved.add(f"{identity}->{dependency}")
                continue
            visit(dependency)
        visiting.remove(identity)

    for root in sorted(set(root_ids)):
        visit(root)
    stable = {
        "root_ids": sorted(set(root_ids)),
        "reachable_artifact_ids": sorted(reachable),
        "missing_artifact_ids": sorted(missing),
        "unresolved_references": sorted(unresolved),
        "optional_artifact_ids": sorted(optional),
    }
    return ResearchArtifactReachabilityPlan(
        "rap_" + hash_payload(stable),
        tuple(stable["root_ids"]), tuple(stable["reachable_artifact_ids"]),
        tuple(stable["missing_artifact_ids"]), tuple(stable["unresolved_references"]),
        tuple(stable["optional_artifact_ids"]),
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
