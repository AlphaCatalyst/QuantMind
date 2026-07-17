import pandas as pd

from backend.services.engine.factor_dsl.executor import _evaluate
from backend.services.engine.factor_dsl.identity import factor_template_id
from backend.services.engine.factor_dsl.parser import parse_template

from .errors import FreshValidationError


def compute_locked_factor_values(frame, candidate_lock):
    """Evaluate only the templates and parameter bindings frozen in the cohort lock."""
    ordered = frame.sort_values(["symbol", "trade_date"], kind="mergesort").reset_index(drop=True).copy()
    ordered["trade_date"] = pd.to_datetime(ordered["trade_date"])
    if ordered.duplicated(["symbol", "trade_date"]).any():
        raise FreshValidationError("Fresh source contains duplicate factor keys")
    outputs = {}
    for evidence in candidate_lock["candidate_evidence"]:
        template = parse_template(evidence["template"])
        if factor_template_id(template) != evidence["template_id"]:
            raise FreshValidationError("Locked Factor Template identity changed")
        values = _evaluate(template.expression, ordered, evidence["parameters"])
        if not isinstance(values, pd.Series):
            raise FreshValidationError("Locked Factor did not produce a series")
        output = ordered[["symbol", "trade_date"]].copy()
        output["factor_value"] = values.astype(float)
        outputs[evidence["factor_instance_id"]] = output
    return outputs
