"""Versioned Manifest-to-Ledger Domain mapping without prose invention."""

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
from backend.services.engine.project_knowledge.domain import (
    ArchitectureDecisionReference,
    ChangedFile,
    ChangedSymbol,
    ComponentReference,
    ImplementationArtifact,
    ImplementationTask,
    LedgerDomainError,
    Limitation,
    RecommendedTask,
    RunRelationship,
    TestExecution,
)

from .errors import ManifestParseError
from .manifest_v2 import validate_manifest_v2_payload

from .models import (
    DomainBundleBuild,
    EvidenceGap,
    GitConsistencyEvidence,
    ParsedImplementationManifest,
    RepositoryBinding,
    ResolvedImplementationRun,
    ImplementationDomainBundle,
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
        if parsed.schema_version == "2.0.0":
            return self._build_v2(parsed, evidence)
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

    def build_source_v2(self, payload) -> ImplementationDomainBundle:  # noqa: ANN001
        """Validate a pre-commit v2 payload through real Domain constructors."""
        validate_manifest_v2_payload(payload)
        return self._v2_bundle(
            payload,
            task_status=payload["run"]["task_status"],
            result_commit=payload["run"]["result_commit"],
            consistency_status=payload["run"]["consistency_status"],
        )

    def _build_v2(
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
        try:
            bundle = self._v2_bundle(
                parsed.payload,
                task_status=evidence.resolved_status,
                result_commit=evidence.resolved_result_commit,
                consistency_status="consistent",
            )
        except (LedgerDomainError, KeyError, TypeError, ValueError) as exc:
            return DomainBundleBuild(
                None,
                None,
                (
                    EvidenceGap(
                        "MANIFEST_V2_DOMAIN_INVALID",
                        "domain_bundle",
                        f"Manifest v2 does not form valid Domain objects: {type(exc).__name__}",
                    ),
                ),
            )
        resolved = ResolvedImplementationRun(
            parsed.source_status,
            evidence.resolved_status or bundle.run.task_status.value,
            evidence.containing_commit,
            bundle.run,
        )
        return DomainBundleBuild(resolved, bundle, ())

    def _v2_bundle(
        self,
        payload,
        *,
        task_status,
        result_commit,
        consistency_status,
    ) -> ImplementationDomainBundle:  # noqa: ANN001
        repository = payload["repository"]
        task_data = payload["task"]
        run_data = payload["run"]
        integrity = payload["integrity"]
        if repository["repository_id"] != self.binding.repository_id:
            raise ManifestParseError("Manifest repository_id differs from trusted binding")

        task = ImplementationTask(
            task_id=task_data["task_id"],
            parent_task_id=task_data["parent_task_id"],
            title=task_data["title"],
            objective=task_data["objective"],
            scope=tuple(task_data["scope"]),
            explicit_non_goals=tuple(task_data["explicit_non_goals"]),
            status=task_data["status"],
            created_at=_time(task_data["created_at"]),
        )
        run = ImplementationRun(
            implementation_run_id=run_data["implementation_run_id"],
            task_id=run_data["task_id"],
            repository_root=repository["repository_id"],
            branch=run_data["branch"],
            base_commit=run_data["base_commit"],
            result_commit=result_commit,
            task_status=task_status,
            completion_level=run_data["completion_level"],
            verification_level=run_data["verification_level"],
            workspace_dirty_before=run_data["workspace_dirty_before"],
            workspace_dirty_after=run_data["workspace_dirty_after"],
            started_at=_time(run_data["started_at"]),
            completed_at=_time(run_data["completed_at"]),
            agent_type=run_data["agent_type"],
            manifest_schema_version=run_data["manifest_schema_version"],
            manifest_path=run_data["manifest_path"],
            manifest_hash=integrity["manifest_payload_sha256"],
            report_path=run_data["report_path"],
            report_hash=integrity["report_sha256"],
            source_bundle_hash=run_data["source_bundle_hash"],
            git_diff_hash=run_data["git_diff_hash"],
            consistency_status=consistency_status,
            canonical_status=run_data["canonical_status"],
        )
        run_id = run.implementation_run_id
        return ImplementationDomainBundle(
            task=task,
            run=run,
            relationships=tuple(
                RunRelationship(
                    item["relationship_id"], item["source_run_id"],
                    item["target_run_id"], item["relationship_type"],
                    item["reason"], _time(item["created_at"]),
                )
                for item in payload["relationships"]
            ),
            changed_files=tuple(
                ChangedFile(
                    run_id, item["path"], item["change_type"],
                    item["before_hash"], item["after_hash"], item["previous_path"],
                )
                for item in payload["changed_files"]
                if item["path"] != run_data["manifest_path"]
            ),
            changed_symbols=tuple(
                ChangedSymbol(
                    run_id, item["file_path"], item["qualified_name"],
                    item["symbol_type"], item["change_type"],
                )
                for item in payload["changed_symbols"]
            ),
            tests=tuple(
                TestExecution(
                    item["test_execution_id"], run_id, item["command"],
                    item["purpose"], item["status"], item["passed_count"],
                    item["failed_count"], item["skipped_count"],
                    item["not_run_reason"], item["artifact_uri"], item["artifact_hash"],
                )
                for item in payload["tests"]
            ),
            artifacts=tuple(
                ImplementationArtifact(
                    item["artifact_id"], run_id, item["artifact_type"],
                    item["path_or_uri"], item["content_hash"],
                    item["schema_version"], item["size_bytes"],
                )
                for item in payload["artifacts"]
            ),
            component_refs=tuple(
                ComponentReference(run_id, item["component_id"], item["impact_type"])
                for item in payload["component_references"]
            ),
            adr_refs=tuple(
                ArchitectureDecisionReference(run_id, item["adr_id"], item["relation"])
                for item in payload["adr_references"]
            ),
            limitations=tuple(
                Limitation(
                    item["limitation_id"], run_id, item["severity"],
                    item["component_id"], item["description"], item["status"],
                )
                for item in payload["limitations"]
            ),
            recommended_tasks=tuple(
                RecommendedTask(
                    item["recommendation_id"], run_id, item["next_task_id"],
                    item["priority"], item["reason"],
                )
                for item in payload["recommended_tasks"]
            ),
        )
