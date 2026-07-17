from __future__ import annotations

import json
from pathlib import Path

from backend.services.engine.artifact_store.enums import ArtifactKind
from backend.services.engine.factor_registry import active_factors, list_by_status, promotion_candidates

from .adapters import load_registry_snapshot_store
from .errors import ResearchStateRecoveryError
from .models import ArtifactRuntimeContext, RecoveredResearchState


CANONICAL_REGISTRY_ID = "frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5"


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
) -> RecoveredResearchState:
    registry, _ = load_registry_snapshot_store(context, CANONICAL_REGISTRY_ID)
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
        CANONICAL_REGISTRY_ID,
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
