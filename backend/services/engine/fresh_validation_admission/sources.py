import json
from dataclasses import dataclass
from pathlib import Path

from backend.services.engine.factor_dsl.artifact import sha256_file, validate_values
from backend.services.engine.factor_optimization.canonical import hash_payload as optimization_hash
from backend.services.engine.factor_optimization.identity import result_id as optimization_result_id
from backend.services.engine.research_campaign.artifact import validate_campaign
from backend.services.engine.research_campaign.canonical import hash_payload

from .errors import FreshValidationAdmissionError
from .models import CandidateEvidence


@dataclass(frozen=True)
class CampaignAdmissionSource:
    campaign_root: str
    campaign_id: str
    optimization_root: str
    factor_values_root: str
    snapshot_root: str
    result_id: str


def _read(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as exc:
        raise FreshValidationAdmissionError(f"Admission source is unreadable: {path}") from exc


def _verify_json_inventory(root):
    root = Path(root)
    manifest = _read(root / "manifest.json")
    expected = set(manifest.get("file_hashes", {}))
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*.json") if p.name != "manifest.json"}
    if actual != expected:
        raise FreshValidationAdmissionError("Optimization artifact inventory mismatch")
    for relative, digest in manifest["file_hashes"].items():
        if sha256_file(root / relative) != digest:
            raise FreshValidationAdmissionError("Optimization artifact hash mismatch")
    return manifest


def _completed_proposal(campaign_path, factor_instance_id):
    matches = []
    for result_path in sorted((Path(campaign_path) / "iterations").glob("*/result.json")):
        for proposal in _read(result_path).get("proposals", []):
            if proposal.get("factor_instance_id") == factor_instance_id:
                matches.append(proposal)
    if len(matches) != 1 or matches[0].get("status") != "completed":
        raise FreshValidationAdmissionError("Factor Instance is not uniquely bound to a completed proposal")
    return matches[0]


def _contains_forbidden_evidence_key(value):
    if isinstance(value, dict):
        return any(("label" in str(key).lower() or "frozen" in str(key).lower() or
                    _contains_forbidden_evidence_key(item)) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_evidence_key(item) for item in value)
    return False


def collect_candidate_evidence(entry, source):
    campaign = validate_campaign(source.campaign_root, source.campaign_id)
    campaign_path = Path(campaign["path"])
    result = campaign["result"]
    proposal = _completed_proposal(campaign_path, entry.factor_instance_id)
    evidence = entry.research_evidence or {}
    evidence_lineage = {
        "campaign_id": source.campaign_id,
        "research_goal_id": result["goal_id"],
        "development_evaluation_id": proposal["development"]["development_evaluation_id"],
    }
    decisions = [_read(path) for path in sorted((campaign_path / "iterations").glob("*/decision.json"))]
    proposal_decisions = [decision for decision in decisions if any(
        item.get("proposal_id") == proposal.get("proposal_id") for item in decision.get("proposals", []))]
    if (len(proposal_decisions) != 1 or
            evidence.get("research_decision_id") != proposal_decisions[0].get("decision_id") or
            any(evidence.get(key) != value for key, value in evidence_lineage.items()) or
            entry.template_id != proposal["template_id"] or
            entry.optimization_study_id != proposal["study_id"] or
            entry.optimization_trial_id != proposal["selected_trial_id"]):
        raise FreshValidationAdmissionError("Registry research evidence does not match Campaign lineage")
    if (result.get("validation_evidence_created") is not False or
            result.get("frozen_evidence_created") is not False or
            entry.status.value != "research_registered"):
        raise FreshValidationAdmissionError("Candidate violates research-only quarantine")

    study_root = Path(source.optimization_root) / proposal["study_id"]
    study_manifest = _verify_json_inventory(study_root)
    saved_spec = _read(study_root / "spec.json"); study_summary = _read(study_root / "summary.json")
    trial_summaries = [_read(study_root / "trials" / f"{trial_id}.json")
                       for trial_id in study_manifest.get("trial_ids", [])]
    stable_keys = ("schema_version", "study_id", "template_id", "snapshot_id",
        "factor_dsl_engine_version", "factor_optimization_engine_version", "spec_sha256",
        "status", "trial_count", "succeeded_count", "replayed_count", "failed_count",
        "not_run_count", "eligible_count", "validation_candidate_order", "trial_ids")
    stable = {key: study_manifest.get(key) for key in stable_keys}
    stable["trial_result_summaries"] = trial_summaries
    stable_hash = optimization_hash(stable)
    expected_result = optimization_result_id(proposal["study_id"], trial_summaries,
        tuple(study_manifest.get("validation_candidate_order", ())), stable_hash)
    if (study_manifest.get("spec_sha256") != optimization_hash(saved_spec) or
            study_manifest.get("study_manifest_hash") != stable_hash or
            study_manifest.get("result_id") != expected_result or
            study_summary.get("result_id") != expected_result):
        raise FreshValidationAdmissionError("Optimization Study identity is invalid")
    trial = _read(study_root / "trials" / f"{proposal['selected_trial_id']}.json")
    if (study_manifest.get("study_id") != proposal["study_id"] or
            trial.get("factor_instance_id") != entry.factor_instance_id or
            trial.get("factor_values_id") != proposal["factor_values_id"] or
            trial.get("status") not in {"succeeded", "replayed"}):
        raise FreshValidationAdmissionError("Selected Optimization Trial lineage is invalid")
    values = validate_values(source.snapshot_root, source.factor_values_root, proposal["factor_values_id"])
    values_manifest = _read(Path(source.factor_values_root) / proposal["factor_values_id"] / "manifest.json")
    if (values_manifest.get("factor_instance_id") != entry.factor_instance_id or
            values_manifest.get("factor_template_id") != entry.template_id or
            values_manifest.get("dataset_snapshot_id") != entry.dataset_snapshot_id or
            any("label" in name.lower() or "frozen" in name.lower()
                for name in values_manifest.get("required_features", [])) or
            _contains_forbidden_evidence_key(proposal_decisions[0].get("proposals", []))):
        raise FreshValidationAdmissionError("Candidate contains forbidden label/Frozen lineage")

    development = proposal["development"]
    identity = {key: value for key, value in development.items() if key != "development_evaluation_id"}
    if "der_" + hash_payload(identity) != development["development_evaluation_id"]:
        raise FreshValidationAdmissionError("Development evaluation identity is invalid")
    if (development.get("orientation_source") != "pre_2025_research_period" or
            development.get("orientation_period", [None, None])[1] >= development.get("development_period", [None])[0] or
            development.get("orientation") != entry.orientation):
        raise FreshValidationAdmissionError("Orientation is not frozen before Development")
    quarantine = {
        "development_is_contaminated": True, "contaminated_period": True,
        "adaptive_research_only": True, "is_validation_evidence": False,
        "is_frozen_evidence": False, "predictive_claim": False,
        "eligible_for_registry_promotion": False,
    }
    if any(development.get(key) is not value for key, value in quarantine.items()):
        raise FreshValidationAdmissionError("Development evidence quarantine is invalid")
    metrics = development["development_metrics"]
    trial_metrics = trial.get("metrics") or {}
    summary = {key: metrics.get(key) for key in (
        "date_count_valid", "median_daily_observations", "factor_finite_coverage",
        "mean_rank_ic", "rank_icir", "rank_ic_positive_rate")}
    return CandidateEvidence(
        entry.factor_instance_id, source.campaign_id, proposal["template_id"], proposal["proposal_id"],
        proposal["study_id"], proposal["selected_trial_id"], development["development_evaluation_id"],
        entry.status.value, True, True, True, True, True, True, True,
        values["status"] == "valid", bool(trial_metrics.get("constant_output", False)),
        int(trial_metrics.get("infinity_count", 0)), summary)


__all__ = ["CampaignAdmissionSource", "collect_candidate_evidence"]
