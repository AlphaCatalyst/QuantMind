from backend.services.engine.factor_dsl.canonical import node_payload

from .canonical import canonical_bytes, hash_payload


def _shape(node):
    value = node_payload(node)
    kind = value["type"]
    if kind == "feature": return {"type": kind, "name": value["name"]}
    if kind == "parameter": return {"type": kind, "role": "search_parameter"}
    if kind == "constant": return value
    result = {"type": kind}
    for key, child in value.items():
        if key != "type": result[key] = _shape_payload(child)
    if kind in {"add", "multiply"}:
        children = sorted((result["left"], result["right"]), key=canonical_bytes)
        result["left"], result["right"] = children
    return result


def _shape_payload(value):
    if isinstance(value, dict):
        kind = value.get("type")
        if kind == "parameter": return {"type": kind, "role": "search_parameter"}
        if kind == "feature": return {"type": kind, "name": value["name"]}
        result = {key: _shape_payload(child) for key, child in value.items()}
        if kind in {"add", "multiply"}:
            children = sorted((result["left"], result["right"]), key=canonical_bytes)
            result["left"], result["right"] = children
        return result
    return value


def structural_fingerprint(template):
    return "nfp_" + hash_payload(_shape(template.expression))
