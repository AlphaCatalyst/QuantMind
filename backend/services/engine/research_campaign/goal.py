import json
import re
from pathlib import Path

from .canonical import hash_payload
from .errors import ResearchCampaignError
from .models import ResearchGoal

_FORBIDDEN = re.compile(r"(?i)(guarantee|maximize frozen|bypass|python|modify registry|auto.?approve|label.*feature)")


def parse_goal(payload):
    if isinstance(payload, (str, Path)):
        payload = json.loads(Path(payload).read_text(encoding="utf-8"))
    fields = {"schema_version", "goal_id", "name", "objective", "dataset_kind", "allowed_features",
              "allowed_operators", "allowed_parameter_roles", "maximum_templates", "maximum_trials",
              "maximum_iterations", "novelty_requirement", "constraints"}
    if not isinstance(payload, dict) or set(payload) != fields or payload["schema_version"] != "1.0.0":
        raise ResearchCampaignError("ResearchGoal fields/schema are invalid")
    identity = {key: payload[key] for key in fields - {"goal_id"}}
    if payload["goal_id"] != "rg_" + hash_payload(identity):
        raise ResearchCampaignError("ResearchGoal identity mismatch")
    for name in ("allowed_features", "allowed_operators", "allowed_parameter_roles", "constraints"):
        if not isinstance(payload[name], list) or not payload[name] or len(payload[name]) != len(set(payload[name])):
            raise ResearchCampaignError(f"ResearchGoal {name} must be a non-empty unique list")
    if any(isinstance(payload[name], bool) or not isinstance(payload[name], int) or payload[name] < 1
           for name in ("maximum_templates", "maximum_trials", "maximum_iterations")):
        raise ResearchCampaignError("ResearchGoal bounds are invalid")
    if _FORBIDDEN.search(json.dumps(payload, ensure_ascii=False)):
        raise ResearchCampaignError("ResearchGoal contains forbidden authority or unsafe objective")
    return ResearchGoal(payload["goal_id"], payload["name"], payload["objective"], payload["dataset_kind"],
        tuple(payload["allowed_features"]), tuple(payload["allowed_operators"]),
        tuple(payload["allowed_parameter_roles"]), payload["maximum_templates"], payload["maximum_trials"],
        payload["maximum_iterations"], payload["novelty_requirement"], tuple(payload["constraints"]))


def goal_payload_without_id(**values):
    return {"schema_version": "1.0.0", **values}


def assign_goal_id(payload):
    body = dict(payload); body.pop("goal_id", None)
    return {**body, "goal_id": "rg_" + hash_payload(body)}
