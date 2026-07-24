from __future__ import annotations


def feature_agent_schema() -> dict:
    node_ref = {"$ref": "#/$defs/node"}
    base = {"type": "object", "additionalProperties": False}
    node = {
        "anyOf": [
            base | {"properties": {"type": {"const": "feature"}, "name": {"type": "string"}},
                    "required": ["type", "name"]},
            base | {"properties": {"type": {"const": "constant"}, "value": {"type": "number"}},
                    "required": ["type", "value"]},
            *[
                base | {
                    "properties": {
                        "type": {"const": kind}, "left": node_ref, "right": node_ref,
                    },
                    "required": ["type", "left", "right"],
                }
                for kind in ("add", "subtract", "multiply", "safe_divide")
            ],
            *[
                base | {
                    "properties": {"type": {"const": kind}, "operand": node_ref},
                    "required": ["type", "operand"],
                }
                for kind in ("negate", "abs")
            ],
            base | {
                "properties": {
                    "type": {"const": "clip"}, "operand": node_ref,
                    "lower": {"type": "number"}, "upper": {"type": "number"},
                },
                "required": ["type", "operand", "lower", "upper"],
            },
            *[
                base | {
                    "properties": {
                        "type": {"const": kind}, "operand": node_ref,
                        "periods": {"type": "integer", "enum": [5, 10, 20, 40, 60, 120]},
                    },
                    "required": ["type", "operand", "periods"],
                }
                for kind in ("lag", "delta")
            ],
            *[
                base | {
                    "properties": {
                        "type": {"const": kind}, "operand": node_ref,
                        "window": {"type": "integer", "enum": [5, 10, 20, 40, 60, 120]},
                    },
                    "required": ["type", "operand", "window"],
                }
                for kind in ("rolling_mean", "rolling_std", "rolling_min", "rolling_max")
            ],
        ]
    }
    string_array = {"type": "array", "items": {"type": "string"}}
    proposal = base | {
        "properties": {
            "feature_proposal_id": {"type": "string"},
            "feature_name": {"type": "string"},
            "feature_family": {"type": "string"},
            "economic_or_market_interpretation": {"type": "string"},
            "canonical_expression": {"type": "string"},
            "canonical_ast": node_ref,
            "input_primitives": string_array,
            "window_parameters": {"type": "array", "items": {"type": "integer"}},
            "default_parameters": {
                "type": "object", "additionalProperties": False,
                "properties": {}, "required": [],
            },
            "expected_scale": {"type": "string"},
            "expected_sign": {"type": "string"},
            "expected_persistence": {"type": "string"},
            "expected_failure_modes": string_array,
            "difference_from_existing_features": {"type": "string"},
            "complexity_statement": {"type": "string"},
        },
        "required": [
            "feature_proposal_id", "feature_name", "feature_family",
            "economic_or_market_interpretation", "canonical_expression", "canonical_ast",
            "input_primitives", "window_parameters", "default_parameters", "expected_scale",
            "expected_sign", "expected_persistence", "expected_failure_modes",
            "difference_from_existing_features", "complexity_statement",
        ],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "additionalProperties": False,
        "properties": {
            "decision_id": {"type": "string"},
            "proposals": {"type": "array", "maxItems": 3, "items": proposal},
        },
        "required": ["decision_id", "proposals"], "$defs": {"node": node},
    }
