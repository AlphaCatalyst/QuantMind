import hashlib
import json
from typing import Any

from .models import ExpressionNode, FactorTemplate, ParameterDefinition


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def parameter_payload(p: ParameterDefinition) -> dict:
    result = {"name": p.name, "type": p.parameter_type.value, "default": p.default,
              "minimum": p.minimum, "maximum": p.maximum}
    if p.step is not None:
        result["step"] = p.step
    return result


def node_payload(node: ExpressionNode) -> dict:
    value = {"type": node.kind.value}
    for key, item in node.fields.items():
        if isinstance(item, ExpressionNode):
            value[key] = node_payload(item)
        else:
            value[key] = item
    return value


def template_payload(template: FactorTemplate) -> dict:
    return {
        "schema_version": template.schema_version,
        "name": template.name,
        "description": template.description,
        "dataset_kinds": list(template.dataset_kinds),
        "parameters": [parameter_payload(p) for p in template.parameters],
        "expression": node_payload(template.expression),
        "output": {"name": template.output_name},
    }


def sha256_id(prefix: str, payload: Any) -> str:
    return prefix + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
