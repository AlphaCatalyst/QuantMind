import math
from typing import Dict, Set

from .enums import NodeKind, ParameterType, ValueKind
from .errors import AdmissionError
from .identity import ENGINE_VERSION, factor_instance_id, factor_template_id
from .models import CompiledFactor, ExpressionNode, FactorTemplate, SnapshotContract

MAX_NODES = 64
MAX_DEPTH = 16
MAX_FEATURE_TERMINALS = 16
MAX_PARAMETERS = 8
MAX_ROLLING_WINDOW = 252
NUMERIC_TYPES = {"double", "float", "float32", "float64", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"}
BINARY = {NodeKind.ADD, NodeKind.SUBTRACT, NodeKind.MULTIPLY, NodeKind.DIVIDE}
UNARY = {NodeKind.NEGATE, NodeKind.ABSOLUTE}
ROLLING = {NodeKind.ROLLING_MEAN, NodeKind.ROLLING_STD, NodeKind.ROLLING_MIN, NodeKind.ROLLING_MAX}


def _bind(template, overrides):
    definitions = {p.name: p for p in template.parameters}
    extra = set(overrides) - set(definitions)
    if extra:
        raise AdmissionError(f"unknown parameter bindings: {sorted(extra)}")
    bound = {}
    for name, p in definitions.items():
        value = overrides.get(name, p.default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AdmissionError(f"parameter {name} must be finite numeric")
        if p.parameter_type is ParameterType.INTEGER and not isinstance(value, int):
            raise AdmissionError(f"parameter {name} must be integer")
        if not p.minimum <= value <= p.maximum:
            raise AdmissionError(f"parameter {name} outside declared bounds")
        if p.step is not None:
            quotient = (value - p.minimum) / p.step
            if abs(quotient - round(quotient)) > 1e-9:
                raise AdmissionError(f"parameter {name} violates step")
        bound[name] = value
    return bound, definitions


def compile_template(template: FactorTemplate, contract: SnapshotContract, parameter_bindings=None):
    if contract.dataset_kind not in template.dataset_kinds:
        raise AdmissionError(f"template does not admit dataset kind {contract.dataset_kind}")
    bound, definitions = _bind(template, parameter_bindings or {})
    features, used_parameters = [], set()
    node_count = 0
    max_depth = 0

    def scalar(node, depth):
        nonlocal node_count, max_depth
        shape, warmup = visit(node, depth)
        if shape is not ValueKind.SCALAR:
            raise AdmissionError(f"{node.kind.value} argument must be scalar")
        if node.kind is NodeKind.CONSTANT:
            return node.fields["value"]
        if node.kind is NodeKind.PARAMETER:
            return bound[node.fields["name"]]
        raise AdmissionError("window, periods and clip bounds accept only constant or parameter scalar nodes")

    def visit(node, depth):
        nonlocal node_count, max_depth
        node_count += 1
        max_depth = max(max_depth, depth)
        if node_count > MAX_NODES or depth > MAX_DEPTH:
            raise AdmissionError("expression exceeds node or depth budget")
        kind = node.kind
        if kind is NodeKind.FEATURE:
            name = node.fields["name"]
            features.append(name)
            if len(features) > MAX_FEATURE_TERMINALS:
                raise AdmissionError("expression exceeds feature terminal budget")
            if contract.feature_roles.get(name) != "feature":
                role = contract.feature_roles.get(name, "missing")
                raise AdmissionError(f"feature {name!r} is not an admitted research feature (role={role})")
            if contract.feature_types.get(name) not in NUMERIC_TYPES:
                raise AdmissionError(f"feature {name!r} does not have an admitted numeric type")
            return ValueKind.SERIES, 0
        if kind is NodeKind.PARAMETER:
            name = node.fields["name"]
            if name not in definitions:
                raise AdmissionError(f"undeclared parameter: {name}")
            used_parameters.add(name)
            return ValueKind.SCALAR, 0
        if kind is NodeKind.CONSTANT:
            return ValueKind.SCALAR, 0
        if kind in BINARY:
            left, lw = visit(node.fields["left"], depth + 1)
            right, rw = visit(node.fields["right"], depth + 1)
            return (ValueKind.SERIES if ValueKind.SERIES in (left, right) else ValueKind.SCALAR), max(lw, rw)
        if kind in UNARY:
            return visit(node.fields["operand"], depth + 1)
        if kind is NodeKind.CLIP:
            shape, warmup = visit(node.fields["operand"], depth + 1)
            lower = scalar(node.fields["lower"], depth + 1)
            upper = scalar(node.fields["upper"], depth + 1)
            if lower >= upper:
                raise AdmissionError("clip lower must be less than upper")
            return shape, warmup
        if kind in (NodeKind.LAG, NodeKind.DELTA):
            shape, warmup = visit(node.fields["operand"], depth + 1)
            if shape is not ValueKind.SERIES:
                raise AdmissionError(f"{kind.value} requires a series operand")
            periods = scalar(node.fields["periods"], depth + 1)
            if not isinstance(periods, int) or periods <= 0 or periods >= contract.date_count:
                raise AdmissionError(f"{kind.value} periods must be a positive integer below dataset date count")
            return shape, warmup + periods
        if kind in ROLLING:
            shape, warmup = visit(node.fields["operand"], depth + 1)
            if shape is not ValueKind.SERIES:
                raise AdmissionError(f"{kind.value} requires a series operand")
            window = scalar(node.fields["window"], depth + 1)
            if not isinstance(window, int) or not 2 <= window <= MAX_ROLLING_WINDOW or window > contract.date_count:
                raise AdmissionError(f"{kind.value} window must be integer in [2, min(252, dataset dates)]")
            return shape, warmup + window - 1
        if kind in (NodeKind.CS_RANK, NodeKind.CS_ZSCORE):
            shape, warmup = visit(node.fields["operand"], depth + 1)
            if shape is not ValueKind.SERIES:
                raise AdmissionError(f"{kind.value} requires a series operand")
            return shape, warmup
        raise AdmissionError(f"unhandled node: {kind.value}")

    output_kind, warmup = visit(template.expression, 1)
    if output_kind is not ValueKind.SERIES:
        raise AdmissionError("factor output must be a series")
    warnings = tuple(f"declared parameter {name} is unused" for name in sorted(set(definitions) - used_parameters))
    tid = factor_template_id(template)
    iid = factor_instance_id(tid, contract.snapshot_id, bound)
    return CompiledFactor(tid, iid, contract.snapshot_id, ENGINE_VERSION, template, bound,
                          tuple(sorted(set(features))), output_kind, node_count, max_depth, warmup, warnings)
