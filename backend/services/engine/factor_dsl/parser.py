import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Set

from .enums import NodeKind, ParameterType
from .errors import TemplateValidationError
from .models import ExpressionNode, FactorTemplate, ParameterDefinition

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
SECRET_RE = re.compile(r"(?i)(password|passwd|api[_-]?key|access[_-]?token|private[_-]?key)\s*[:=]")
BINARY = {NodeKind.ADD, NodeKind.SUBTRACT, NodeKind.MULTIPLY, NodeKind.DIVIDE}
UNARY = {NodeKind.NEGATE, NodeKind.ABSOLUTE, NodeKind.CS_RANK, NodeKind.CS_ZSCORE}
ROLLING = {NodeKind.ROLLING_MEAN, NodeKind.ROLLING_STD, NodeKind.ROLLING_MIN, NodeKind.ROLLING_MAX}


def _exact(obj: Mapping[str, Any], required: Set[str], optional: Set[str] = frozenset(), where="object"):
    if not isinstance(obj, dict):
        raise TemplateValidationError(f"{where} must be an object")
    missing = required - set(obj)
    extra = set(obj) - required - optional
    if missing or extra:
        raise TemplateValidationError(f"{where} fields invalid: missing={sorted(missing)}, extra={sorted(extra)}")


def _number(value, where, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TemplateValidationError(f"{where} must be a finite number")
    if integer and (not isinstance(value, int) or isinstance(value, bool)):
        raise TemplateValidationError(f"{where} must be an integer")
    return value


def _name(value, where):
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise TemplateValidationError(f"{where} is not a safe identifier")
    return value


def _parse_node(obj, active):
    if not isinstance(obj, dict):
        raise TemplateValidationError("expression node must be an object")
    marker = id(obj)
    if marker in active:
        raise TemplateValidationError("cyclic expression is forbidden")
    active.add(marker)
    try:
        raw_kind = obj.get("type")
        try:
            kind = NodeKind(raw_kind)
        except (ValueError, TypeError):
            raise TemplateValidationError(f"unknown node type: {raw_kind!r}")
        if kind in (NodeKind.FEATURE, NodeKind.PARAMETER):
            _exact(obj, {"type", "name"}, where=kind.value)
            return ExpressionNode(kind, {"name": _name(obj["name"], f"{kind.value}.name")})
        if kind is NodeKind.CONSTANT:
            _exact(obj, {"type", "value"}, where=kind.value)
            return ExpressionNode(kind, {"value": _number(obj["value"], "constant.value")})
        if kind in BINARY:
            _exact(obj, {"type", "left", "right"}, where=kind.value)
            return ExpressionNode(kind, {"left": _parse_node(obj["left"], active), "right": _parse_node(obj["right"], active)})
        if kind in UNARY:
            _exact(obj, {"type", "operand"}, where=kind.value)
            return ExpressionNode(kind, {"operand": _parse_node(obj["operand"], active)})
        if kind is NodeKind.CLIP:
            _exact(obj, {"type", "operand", "lower", "upper"}, where=kind.value)
            return ExpressionNode(kind, {"operand": _parse_node(obj["operand"], active),
                                         "lower": _parse_node(obj["lower"], active), "upper": _parse_node(obj["upper"], active)})
        if kind in (NodeKind.LAG, NodeKind.DELTA):
            _exact(obj, {"type", "operand", "periods"}, where=kind.value)
            return ExpressionNode(kind, {"operand": _parse_node(obj["operand"], active), "periods": _parse_node(obj["periods"], active)})
        if kind in ROLLING:
            _exact(obj, {"type", "operand", "window"}, where=kind.value)
            return ExpressionNode(kind, {"operand": _parse_node(obj["operand"], active), "window": _parse_node(obj["window"], active)})
        raise TemplateValidationError(f"unsupported node type: {kind.value}")
    finally:
        active.remove(marker)


def parse_template(payload) -> FactorTemplate:
    if isinstance(payload, (str, bytes, Path)):
        if isinstance(payload, Path) or (isinstance(payload, str) and not payload.lstrip().startswith("{")):
            payload = json.loads(Path(payload).read_text(encoding="utf-8"))
        else:
            payload = json.loads(payload)
    _exact(payload, {"schema_version", "name", "description", "dataset_kinds", "parameters", "expression", "output"}, where="template")
    if payload["schema_version"] != "1.0.0":
        raise TemplateValidationError("schema_version must be 1.0.0")
    name = _name(payload["name"], "template.name")
    description = payload["description"]
    if not isinstance(description, str) or not description.strip() or len(description) > 2000 or SECRET_RE.search(description):
        raise TemplateValidationError("description is empty, too long, or contains secret-like material")
    kinds = payload["dataset_kinds"]
    if not isinstance(kinds, list) or not kinds or len(kinds) != len(set(kinds)):
        raise TemplateValidationError("dataset_kinds must be a non-empty unique list")
    kinds = tuple(_name(x, "dataset_kind") for x in kinds)
    raw_parameters = payload["parameters"]
    if not isinstance(raw_parameters, list) or len(raw_parameters) > 8:
        raise TemplateValidationError("parameters must be a list with at most 8 entries")
    parameters = []
    names = set()
    for item in raw_parameters:
        _exact(item, {"name", "type", "default", "minimum", "maximum"}, {"step"}, "parameter")
        pname = _name(item["name"], "parameter.name")
        if pname in names:
            raise TemplateValidationError(f"duplicate parameter: {pname}")
        names.add(pname)
        try:
            ptype = ParameterType(item["type"])
        except ValueError:
            raise TemplateValidationError("parameter.type must be integer or number")
        integer = ptype is ParameterType.INTEGER
        default = _number(item["default"], "parameter.default", integer)
        minimum = _number(item["minimum"], "parameter.minimum", integer)
        maximum = _number(item["maximum"], "parameter.maximum", integer)
        step = _number(item["step"], "parameter.step", integer) if "step" in item else None
        if not integer:
            default, minimum, maximum = float(default), float(minimum), float(maximum)
            step = float(step) if step is not None else None
        if minimum > default or default > maximum or minimum == maximum or (step is not None and step <= 0):
            raise TemplateValidationError(f"invalid range/default/step for parameter {pname}")
        parameters.append(ParameterDefinition(pname, ptype, default, minimum, maximum, step))
    _exact(payload["output"], {"name"}, where="output")
    output_name = _name(payload["output"]["name"], "output.name")
    return FactorTemplate("1.0.0", name, description.strip(), kinds, tuple(parameters),
                          _parse_node(payload["expression"], set()), output_name)
