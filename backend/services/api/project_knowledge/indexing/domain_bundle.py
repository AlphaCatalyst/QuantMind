"""Manifest v1 to Ledger Domain mapping with explicit evidence gaps."""

from __future__ import annotations

from datetime import datetime

from backend.services.engine.project_knowledge.domain.enums import (
    CanonicalStatus,
    CompletionLevel,
    ConsistencyStatus,
    ImplementationRunStatus,
    VerificationLevel,
)
from backend.services.engine.project_knowledge.domain.models import ImplementationRun

from .models import (
    DomainBundleBuild,
    EvidenceGap,
    GitConsistencyEvidence,
    ParsedImplementationManifest,
    RepositoryBinding,
    ResolvedImplementationRun,
)


_RUN_STATUS = {
    "completed_committed": ImplementationRunStatus.COMPLETED_COMMITTED,
    "completed_uncommitted": ImplementationRunStatus.COMPLETED_COMMITTED,
    "partial_uncommitted": ImplementationRunStatus.PARTIAL_COMMITTED,
    "failed": ImplementationRunStatus.FAILED,
    "blocked": ImplementationRunStatus.BLOCKED,
    "in_progress": ImplementationRunStatus.RUNNING,
}
_COMPLETION = {
    "complete": CompletionLevel.COMPLETE,
    "partial": CompletionLevel.PARTIAL,
    "none": CompletionLevel.NONE,
}
_VERIFICATION = {
    "not_run": VerificationLevel.NOT_VERIFIED,
    "structural": VerificationLevel.STATIC_CHECKS,
    "targeted_tests": VerificationLevel.TARGETED_TESTS,
    "integration": VerificationLevel.INTEGRATION_TESTS,
    "full_suite": VerificationLevel.FULL_RELEVANT_TESTS,
}


def _time(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


class DomainBundleBuilder:
    """Build only values justified by formal Manifest/Git fields.

    Manifest v1 cannot express a complete Task or most child identities. Those
    facts are reported as gaps; no defaults or prose-derived values are used.
    """

    def __init__(self, binding: RepositoryBinding) -> None:
        self.binding = binding

    def build(
        self,
        parsed: ParsedImplementationManifest,
        evidence: GitConsistencyEvidence,
    ) -> DomainBundleBuild:
        if not evidence.consistent or evidence.containing_commit is None:
            return DomainBundleBuild(
                None,
                None,
                (EvidenceGap("GIT_INCONSISTENT", "git", "mandatory Git evidence failed"),),
            )
        payload = parsed.payload
        gaps = [
            EvidenceGap(
                "MANIFEST_V1_TASK_STATUS_MISSING",
                "task.status",
                "Manifest v1 has Run status but no independent Task status",
            ),
            EvidenceGap(
                "MANIFEST_V1_TASK_CREATED_AT_MISSING",
                "task.created_at",
                "Manifest v1 has Run start time but no Task creation time",
            ),
        ]
        conditional_gaps = (
            ("changed_files", "MANIFEST_V1_CHANGED_FILE_STRUCTURE_MISSING", "change type and before/after hashes"),
            ("changed_symbols", "MANIFEST_V1_CHANGED_SYMBOL_STRUCTURE_MISSING", "identity, file, symbol type and change type"),
            ("tests_executed", "MANIFEST_V1_TEST_ID_MISSING", "test execution ID"),
            ("artifacts", "MANIFEST_V1_ARTIFACT_ID_MISSING", "artifact business ID"),
            ("component_refs", "MANIFEST_V1_COMPONENT_IMPACT_MISSING", "component impact type"),
            ("architecture_decision_refs", "MANIFEST_V1_ADR_RELATION_MISSING", "ADR relation"),
            ("known_limitations", "MANIFEST_V1_LIMITATION_STRUCTURE_MISSING", "limitation ID, severity and status"),
            ("next_recommended_tasks", "MANIFEST_V1_RECOMMENDATION_STRUCTURE_MISSING", "recommendation ID, priority and reason"),
        )
        for field, code, missing in conditional_gaps:
            if payload[field]:
                gaps.append(EvidenceGap(code, field, f"Manifest v1 lacks {missing}"))
        if payload["corrects_run_id"] is not None:
            gaps.append(
                EvidenceGap(
                    "MANIFEST_V1_RELATIONSHIP_STRUCTURE_MISSING",
                    "corrects_run_id",
                    "relationship ID, reason and created time are absent",
                )
            )

        try:
            run = ImplementationRun(
                implementation_run_id=parsed.run_id,
                task_id=payload["task_id"],
                repository_root=self.binding.repository_id,
                branch=payload["branch"],
                base_commit=payload["base_commit"],
                result_commit=evidence.resolved_result_commit,
                task_status=_RUN_STATUS[payload["task_status"]],
                completion_level=_COMPLETION[payload["completion_level"]],
                verification_level=_VERIFICATION[payload["verification_level"]],
                workspace_dirty_before=payload["workspace_dirty_before"],
                workspace_dirty_after=payload["workspace_dirty_after"],
                started_at=_time(payload["started_at"]),
                completed_at=_time(payload["completed_at"]),
                agent_type=payload["agent_type"],
                manifest_schema_version=payload["manifest_schema_version"],
                manifest_path=parsed.manifest_path,
                manifest_hash=payload["manifest_payload_hash"],
                report_path=parsed.report_path,
                report_hash=payload["report_hash"],
                source_bundle_hash=payload["source_bundle_hash"],
                git_diff_hash=payload["git_diff_hash"],
                consistency_status=ConsistencyStatus.CONSISTENT,
                canonical_status=CanonicalStatus.NONCANONICAL,
            )
        except (KeyError, TypeError, ValueError) as exc:
            gaps.append(
                EvidenceGap(
                    "MANIFEST_V1_RUN_DOMAIN_INVALID",
                    "implementation_run",
                    "resolved Manifest fields do not form a valid Domain Run",
                )
            )
            return DomainBundleBuild(None, None, tuple(gaps))

        resolved = ResolvedImplementationRun(
            parsed.source_status,
            evidence.resolved_status or run.task_status.value,
            evidence.containing_commit,
            run,
        )
        # A complete Task cannot be constructed, therefore no writable bundle
        # is returned. This is deliberate evidence preservation, not a stub.
        return DomainBundleBuild(resolved, None, tuple(gaps))
