import json
import re
from pathlib import Path

from .errors import ValidationSpecError
from .models import FactorValidationSpec


_ID = re.compile(r"^(vd|fos|fot)_[0-9a-f]{64}$")


def parse_validation_spec(value):
    if isinstance(value, (str, bytes, Path)):
        value = json.loads(Path(value).read_text()) if isinstance(value, Path) or (isinstance(value, str) and not value.lstrip().startswith("{")) else json.loads(value)
    required = {"schema_version", "name", "description", "validation_dataset_id", "optimization_study_ids",
                "trial_ids", "metrics", "minimum_requirements", "candidate_selection", "frozen_test_policy"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValidationSpecError("validation spec fields must be exact")
    if value["schema_version"] != "1.0.0": raise ValidationSpecError("unsupported validation spec version")
    if not isinstance(value["name"], str) or not value["name"]: raise ValidationSpecError("name is required")
    if not isinstance(value["description"], str) or not value["description"]: raise ValidationSpecError("description is required")
    if not _ID.fullmatch(value["validation_dataset_id"]): raise ValidationSpecError("invalid validation_dataset_id")
    studies, trials = value["optimization_study_ids"], value["trial_ids"]
    if not isinstance(studies, list) or len(studies) != 2 or len(set(studies)) != 2 or any(not _ID.fullmatch(x) for x in studies):
        raise ValidationSpecError("exactly two unique Study IDs are required")
    if not isinstance(trials, list) or len(trials) != 14 or len(set(trials)) != 14 or any(not _ID.fullmatch(x) for x in trials):
        raise ValidationSpecError("exactly fourteen unique Trial IDs are required")
    expected_metrics = {"ic", "rank_ic", "icir", "positive_rate", "coverage"}
    if set(value["metrics"]) != expected_metrics: raise ValidationSpecError("metrics contract mismatch")
    req = value["minimum_requirements"]
    req_fields = {"train_minimum_valid_rank_ic_dates", "validation_minimum_valid_rank_ic_dates",
                  "train_minimum_median_daily_observations", "validation_minimum_median_daily_observations",
                  "minimum_factor_finite_coverage"}
    if not isinstance(req, dict) or set(req) != req_fields: raise ValidationSpecError("minimum requirements fields mismatch")
    if any(isinstance(req[x], bool) or not isinstance(req[x], int) or req[x] < 1 for x in req_fields if x != "minimum_factor_finite_coverage"):
        raise ValidationSpecError("date and observation gates must be positive integers")
    coverage = req["minimum_factor_finite_coverage"]
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)) or not 0 <= coverage <= 1:
        raise ValidationSpecError("coverage gate must be in [0,1]")
    selection = value["candidate_selection"]
    if not isinstance(selection, dict) or set(selection) != {"ordering", "top_k"} or selection["ordering"] != "validation_predictive_order_v1" or selection["top_k"] != 3:
        raise ValidationSpecError("candidate selection contract mismatch")
    frozen = value["frozen_test_policy"]
    if not isinstance(frozen, dict) or set(frozen) != {"protocol_id", "one_time", "candidate_source", "reselection"}:
        raise ValidationSpecError("frozen policy fields mismatch")
    if not isinstance(frozen["protocol_id"], str) or not frozen["protocol_id"] or frozen["one_time"] is not True or frozen["candidate_source"] != "published_selection" or frozen["reselection"] != "forbidden":
        raise ValidationSpecError("frozen policy contract mismatch")
    return FactorValidationSpec(value["schema_version"], value["name"], value["description"], value["validation_dataset_id"],
                                tuple(studies), tuple(trials), tuple(value["metrics"]), req, selection, frozen)


def spec_payload(spec):
    return {"schema_version": spec.schema_version, "name": spec.name, "description": spec.description,
            "validation_dataset_id": spec.validation_dataset_id, "optimization_study_ids": list(spec.optimization_study_ids),
            "trial_ids": list(spec.trial_ids), "metrics": list(spec.metrics),
            "minimum_requirements": dict(spec.minimum_requirements), "candidate_selection": dict(spec.candidate_selection),
            "frozen_test_policy": dict(spec.frozen_test_policy)}
