from __future__ import annotations

import json
from pathlib import Path

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.factor_registry import active_factors, list_by_status, promotion_candidates

from .adapters import load_registry_snapshot_store
from .errors import ResearchStateRecoveryError
from .models import ArtifactRuntimeContext, RecoveredResearchState


def _canonical_registry_id(repository_root: Path) -> str:
    path = Path(repository_root) / "docs/quantmind2/context/current_state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["current_canonical_registry_snapshot_id"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ResearchStateRecoveryError("current canonical Registry control is unreadable") from exc


def _one_control(root: Path, collection: str, pattern: str) -> dict:
    matches = sorted((root / collection).glob(pattern))
    if len(matches) != 1:
        raise ResearchStateRecoveryError(
            f"Git control collection {collection} must contain exactly one artifact"
        )
    try:
        return json.loads(matches[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchStateRecoveryError("Git control artifact is unreadable") from exc


def recover_research_state(
    context: ArtifactRuntimeContext,
    repository_root: Path,
    canonical_registry_id: str | None = None,
) -> RecoveredResearchState:
    registry_id = canonical_registry_id or _canonical_registry_id(repository_root)
    registry, _ = load_registry_snapshot_store(context, registry_id)
    controls = Path(repository_root) / "docs/quantmind2/research/fresh_validation"
    lock = _one_control(controls, "candidate-locks", "fvcl_*.json")
    protocol = _one_control(controls, "protocols", "fvp_*.json")
    ledger = _one_control(controls, "exposure-ledger", "rdel_*.json")
    watermark = _one_control(controls, "watermarks", "fdw_*.json")
    campaigns = tuple(
        sorted(item.artifact_id for item in context.store.list_by_kind(
            ArtifactKind.RESEARCH_CAMPAIGN.value
        ))
    )
    studies = tuple(
        sorted(item.artifact_id for item in context.store.list_by_kind(
            ArtifactKind.FACTOR_OPTIMIZATION.value
        ))
    )
    validation = context.store.list_by_kind(ArtifactKind.FACTOR_VALIDATION_RESULT.value)
    frozen = context.store.list_by_kind(ArtifactKind.FROZEN_TEST_RESULT.value)
    admission = context.store.list_by_kind(ArtifactKind.FRESH_VALIDATION_ADMISSION.value)
    if not (len(validation) == len(frozen) == len(admission) == 1):
        raise ResearchStateRecoveryError("current Store research state is ambiguous")
    return RecoveredResearchState(
        registry_id,
        len(registry.entries),
        campaigns,
        studies,
        validation[0].artifact_id,
        frozen[0].artifact_id,
        admission[0].artifact_id,
        lock["candidate_lock_id"],
        protocol["protocol_id"],
        ledger["exposure_ledger_id"],
        watermark["watermark_id"],
        watermark["status"],
        watermark["eligible_date_count"],
        len(promotion_candidates(registry)),
        len(list_by_status(registry, "approved")),
        len(active_factors(registry)),
    )


def recover_campaign_graph(context: ArtifactRuntimeContext, campaign_id: str) -> dict:
    """Recover one Campaign and its immutable result graph without source staging."""
    from .adapters import replay_research_campaign, resolve_development_result
    from .resolver import resolve_artifact
    campaign = replay_research_campaign(context, campaign_id).resolved
    root = campaign.materialized_root
    memory = json.loads((root / "memory.json").read_text(encoding="utf-8"))
    decisions = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("iterations/*/decision.json"))
    ]
    studies = tuple(memory.get("optimization_studies", ()))
    development = tuple(memory.get("development_results", ()))
    factor_values = tuple(sorted({item["factor_values_id"] for item in development}))
    for study_id in studies:
        resolve_artifact(context, ArtifactKind.FACTOR_OPTIMIZATION.value, study_id)
    for factor_values_id in factor_values:
        resolve_artifact(context, ArtifactKind.FACTOR_VALUES.value, factor_values_id)
    for item in development:
        resolve_development_result(context, item["development_evaluation_id"])
    registry_id = memory["registry_snapshot_after"]
    registry, registry_ref = load_registry_snapshot_store(context, registry_id)
    return {
        "new_campaign_id": campaign_id,
        "campaign_descriptor_id": campaign.reference.descriptor_id,
        "new_decision_id": decisions[0]["decision_id"] if decisions else None,
        "new_template_id": memory.get("templates", [None])[0] if memory.get("templates") else None,
        "new_study_id": studies[0] if studies else None,
        "new_factor_values_ids": list(factor_values),
        "new_development_result_id": development[0]["development_evaluation_id"] if development else None,
        "new_registry_id": registry_id,
        "registry_descriptor_id": registry_ref.reference.descriptor_id,
        "registry_entry_count": len(registry.entries),
        "promotion_candidate_count": len(promotion_candidates(registry)),
        "approved_count": len(list_by_status(registry, "approved")),
        "active_count": len(active_factors(registry)),
        "runtime_evidence": context.evidence.safe_summary(),
    }
