from __future__ import annotations

from typing import Any

from backend.services.engine.factor_dsl import parse_template
from backend.services.engine.research_campaign.canonical import canonical_bytes
from backend.services.engine.research_campaign.novelty import structural_fingerprint
from backend.services.engine.tushare_cutover.canonical import hash_payload


def _equivalent_shape(node: Any) -> Any:
    if isinstance(node, list):
        return [_equivalent_shape(item) for item in node]
    if not isinstance(node, dict):
        return node
    kind = node.get("type")
    if kind == "parameter":
        return {"type": "parameter", "role": "search_parameter"}
    if kind in {"feature", "constant"}:
        return dict(node)
    result = {key: _equivalent_shape(value) for key, value in node.items()}
    if kind in {"add", "multiply"}:
        children = sorted((result["left"], result["right"]), key=canonical_bytes)
        result["left"], result["right"] = children
    return result


def equivalence_fingerprint(template_payload: dict) -> tuple[str, bool]:
    expression = template_payload["expression"]
    orientation_flip = expression.get("type") == "negate"
    if orientation_flip:
        expression = expression["operand"]
    return "efp_" + hash_payload(_equivalent_shape(expression)), orientation_flip


def assess_template(
    template_payload: dict,
    *,
    known_structural: set[str],
    known_equivalent: set[str],
) -> dict:
    template = parse_template(template_payload)
    structural = structural_fingerprint(template)
    equivalent, orientation_flip = equivalence_fingerprint(template_payload)
    exact = structural in known_structural or equivalent in known_equivalent
    return {
        "structural_fingerprint": structural,
        "equivalence_fingerprint": equivalent,
        "orientation_flip_normalized": orientation_flip,
        "exact_duplicate": exact,
        "admitted": not exact,
        "rejection_reason": "equivalent_or_existing_structure" if exact else None,
    }
