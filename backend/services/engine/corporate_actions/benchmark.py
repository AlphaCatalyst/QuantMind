from __future__ import annotations

from .enums import EvidenceCompleteness
from .errors import CorporateActionEvidenceInsufficient
from .models import FixedUniverseBenchmarkContractV2, SecurityCorporateActionEvent
from .settlement import UNRESOLVED_CODE


def require_canonical_revision(events: tuple[SecurityCorporateActionEvent, ...]) -> None:
    if not events or any(
        event.evidence_completeness is not EvidenceCompleteness.COMPLETE for event in events
    ):
        raise CorporateActionEvidenceInsufficient(UNRESOLVED_CODE)


__all__ = ["FixedUniverseBenchmarkContractV2", "require_canonical_revision"]
