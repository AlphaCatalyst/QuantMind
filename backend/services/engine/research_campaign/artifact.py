import json
import os
import shutil
import uuid
from datetime import datetime, timezone
import re
from pathlib import Path

from .canonical import hash_payload, sha256_file, write_json
from .errors import CampaignArtifactError

SCHEMA_VERSION = "research-campaign-v1"


def campaign_id(goal, budget, config, provider_id, model_id):
    identity = {"goal_id": goal.goal_id, "budget": dict(budget.__dict__), "snapshot_id": config.snapshot_id,
                "development_dataset_id": config.validation_dataset_id,
                "registry_snapshot_before": config.registry_snapshot_id,
                "provider_id": provider_id, "model_id": model_id, "engine": SCHEMA_VERSION}
    return "rc_" + hash_payload(identity)


class CampaignJournal:
    def __init__(self, root, campaign_id_value):
        self.root = Path(root); self.campaign_id = campaign_id_value
        self.path = self.root / ".working" / campaign_id_value
        self.path.mkdir(parents=True, exist_ok=False)
        self.events = []
        self.state = None

    def event(self, event_type, **details):
        states = {"created": "planned", "iteration_started": "agent_proposing", "agent_called": "agent_proposing",
                  "agent_response_rejected": "decision_validating", "decision_accepted": "decision_validating",
                  "proposal_rejected": "decision_validating", "proposal_admitted": "executing",
                  "development_evaluating": "evaluating", "proposal_completed": "evaluating",
                  "registry_snapshot_published": "memory_updating", "completed": "completed", "partial": "partial",
                  "stopped_no_novelty": "stopped_no_novelty", "stopped_budget": "stopped_budget"}
        new_state = states[event_type]
        event = {"event_id": "rce_" + hash_payload({"campaign_id": self.campaign_id,
                 "sequence": len(self.events) + 1, "event_type": event_type, "details": details}),
                 "campaign_id": self.campaign_id, "sequence": len(self.events) + 1,
                 "iteration": details.get("iteration"), "event_type": event_type,
                 "previous_state": self.state, "new_state": new_state,
                 "reason": details.get("reason"), "created_at": datetime.now(timezone.utc).isoformat(), **details}
        self.state = new_state
        self.events.append(event); write_json(self.path / "events.json", self.events)
        write_json(self.path / "state.json", {"campaign_id": self.campaign_id, "state": event_type,
                                                "event_count": len(self.events)})
        return event

    def publish(self, files):
        target = self.root / "campaigns" / self.campaign_id
        if target.exists():
            shutil.rmtree(self.path)
            return validate_campaign(self.root, self.campaign_id, exact_existing=True)
        staging = self.root / "campaigns" / f".{self.campaign_id}.staging-{uuid.uuid4().hex}"
        staging.mkdir(parents=True)
        try:
            for relative, payload in files.items():
                path = staging / relative; path.parent.mkdir(parents=True, exist_ok=True); write_json(path, payload)
            write_json(staging / "events.json", self.events)
            hashes = {p.relative_to(staging).as_posix(): sha256_file(p) for p in sorted(staging.rglob("*.json"))}
            manifest = {"schema_version": SCHEMA_VERSION, "campaign_id": self.campaign_id,
                        "file_hashes": hashes, "event_count": len(self.events)}
            write_json(staging / "manifest.json", manifest)
            target.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, target); staging = None
            shutil.rmtree(self.path)
        finally:
            if staging is not None and staging.exists(): shutil.rmtree(staging)
        return validate_campaign(self.root, self.campaign_id)


def validate_campaign(root, campaign_id_value, exact_existing=False):
    path = Path(root) / "campaigns" / campaign_id_value
    try: manifest = json.loads((path / "manifest.json").read_text())
    except Exception as exc: raise CampaignArtifactError("Campaign manifest unreadable") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("campaign_id") != campaign_id_value:
        raise CampaignArtifactError("Campaign identity/schema mismatch")
    inventory = {p.relative_to(path).as_posix() for p in path.rglob("*.json") if p.name != "manifest.json"}
    if inventory != set(manifest.get("file_hashes", {})):
        raise CampaignArtifactError("Campaign file inventory mismatch")
    for relative, digest in manifest["file_hashes"].items():
        if sha256_file(path / relative) != digest: raise CampaignArtifactError("Campaign file hash mismatch")
    events = json.loads((path / "events.json").read_text())
    if len(events) != manifest["event_count"] or [e["sequence"] for e in events] != list(range(1, len(events)+1)):
        raise CampaignArtifactError("Campaign event journal mismatch")
    result = json.loads((path / "result.json").read_text())
    if not re.fullmatch(r"^rc_[0-9a-f]{64}$", campaign_id_value) or not re.fullmatch(r"^rcr_[0-9a-f]{64}$", result.get("result_id", "")):
        raise CampaignArtifactError("Campaign/Result ID format is invalid")
    limits = {"iterations": 3, "agent_calls": 4, "admitted_proposals": 8, "total_trials": 64,
              "failed_proposals": 8, "failed_trials": 16}
    if any(not isinstance(result.get(key), int) or not 0 <= result[key] <= maximum for key, maximum in limits.items()):
        raise CampaignArtifactError("Campaign result exceeds frozen budget")
    if (result.get("development_is_contaminated") is not True or result.get("validation_evidence_created") is not False or
            result.get("frozen_evidence_created") is not False or any(result.get(key) != 0 for key in
            ("promotion_candidate_added", "approved_added", "active_added"))):
        raise CampaignArtifactError("Campaign result violates research-only quarantine")
    memory = json.loads((path / "memory.json").read_text())
    for development in memory.get("development_results", []):
        required = {"development_is_contaminated": True, "is_validation_evidence": False,
                    "is_frozen_evidence": False, "predictive_claim": False,
                    "adaptive_research_only": True, "eligible_for_registry_promotion": False}
        if any(development.get(key) is not value for key, value in required.items()):
            raise CampaignArtifactError("Development evidence quarantine is invalid")
    for decision_path in path.glob("iterations/*/decision.json"):
        decision = json.loads(decision_path.read_text())
        if not re.fullmatch(r"^rd_[0-9a-f]{64}$", decision.get("decision_id", "")):
            raise CampaignArtifactError("ResearchDecision ID is invalid")
    return {"campaign_id": campaign_id_value, "path": str(path), "result": result,
            "events": events, "exact_existing": exact_existing}
