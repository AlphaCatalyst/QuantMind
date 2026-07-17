from dataclasses import replace

from backend.services.engine.factor_registry.reconciliation import (
    merge_registry_snapshots, publish_reconciliation, reconciliation_payload,
)
from backend.services.engine.factor_registry.snapshot import (
    publish_snapshot, registry_snapshot_id, validate_registry_snapshot,
)

from .artifact import publish_admission_result
from .errors import FreshValidationAdmissionError
from .evaluator import evaluate_admission
from .policy import default_admission_policy
from .sources import collect_candidate_evidence


def reconcile_and_admit(*, ancestor_registry_root, ancestor_snapshot_id,
                        baseline_registry_root, baseline_snapshot_id, baseline_source,
                        external_registry_root, external_snapshot_id, external_source,
                        registry_output_root, admission_output_root, reconciliation_output_root):
    ancestor = validate_registry_snapshot(ancestor_registry_root, ancestor_snapshot_id)
    baseline = validate_registry_snapshot(baseline_registry_root, baseline_snapshot_id)
    external = validate_registry_snapshot(external_registry_root, external_snapshot_id)
    sources, entries, decisions, duplicates, entry_summary, decision_summary = merge_registry_snapshots(
        baseline, external, ancestor.registry_snapshot_id)
    source_by_campaign = {baseline_source.campaign_id: baseline_source,
                          external_source.campaign_id: external_source}
    candidate_entries = [entry for entry in entries if entry.research_evidence and
                         entry.research_evidence.get("campaign_id") in source_by_campaign]
    evidence = [collect_candidate_evidence(entry,
                source_by_campaign[entry.research_evidence["campaign_id"]]) for entry in candidate_entries]
    policy = default_admission_policy()
    evaluated = evaluate_admission(policy, evidence)
    admission = publish_admission_result(admission_output_root, evaluated)
    outcomes = {row.factor_instance_id: row for row in admission.candidates}
    updated = []
    for entry in entries:
        row = outcomes.get(entry.factor_instance_id)
        if row is None:
            updated.append(entry); continue
        updated.append(replace(entry, fresh_validation_admission={
            "policy_id": admission.policy.policy_id, "result_id": admission.result_id,
            "admitted": row.admitted, "reasons": list(row.reasons), "rank": row.rank}))
    result_snapshot_id = registry_snapshot_id(baseline.policy, updated, decisions,
                                               parent_registry_snapshot_ids=sources)
    payload = reconciliation_payload(
        common_ancestor_snapshot_id=ancestor.registry_snapshot_id,
        source_snapshot_ids=sources,
        source_campaign_ids=(baseline_source.campaign_id, external_source.campaign_id),
        source_result_ids=(baseline_source.result_id, external_source.result_id),
        entry_merge_summary=entry_summary, decision_merge_summary=decision_summary,
        duplicate_entries=duplicates, conflicts=(), resulting_snapshot_id=result_snapshot_id)
    reconciliation = publish_reconciliation(reconciliation_output_root, payload)
    snapshot = publish_snapshot(registry_output_root, baseline.policy, updated, decisions,
        parent_registry_snapshot_ids=sources, reconciliation_artifact_id=reconciliation.reconciliation_id)
    if (snapshot.registry_snapshot_id != result_snapshot_id or
            snapshot.reconciliation_artifact_id != reconciliation.reconciliation_id):
        raise FreshValidationAdmissionError("Canonical Registry and reconciliation evidence disagree")
    return {"ancestor": ancestor, "sources": (baseline, external), "admission": admission,
            "reconciliation": reconciliation, "registry": snapshot}


__all__ = ["reconcile_and_admit"]
