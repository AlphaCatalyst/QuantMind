import math

from backend.services.engine.factor_dsl.enums import ParameterType

from .errors import OptimizationSpecError
from .models import SearchSpace


def _valid_value(value, definition):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise OptimizationSpecError(f"search value for {definition.name} must be finite numeric")
    if definition.parameter_type is ParameterType.INTEGER and not isinstance(value, int):
        raise OptimizationSpecError(f"search value for {definition.name} must be integer")
    if not definition.minimum <= value <= definition.maximum:
        raise OptimizationSpecError(f"search value for {definition.name} is outside Template bounds")
    if definition.step is not None:
        quotient = (value - definition.minimum) / definition.step
        if abs(quotient - round(quotient)) > 1e-9:
            raise OptimizationSpecError(f"search value for {definition.name} violates Template step")
    return int(value) if definition.parameter_type is ParameterType.INTEGER else float(value)


def parse_search_space(payload, definition):
    if not isinstance(payload, dict) or "kind" not in payload:
        raise OptimizationSpecError("search space must be an object with kind")
    kind = payload["kind"]
    if kind == "integer_range":
        if set(payload) != {"kind", "minimum", "maximum", "step"}:
            raise OptimizationSpecError("integer_range fields are strict")
        if definition.parameter_type is not ParameterType.INTEGER:
            raise OptimizationSpecError("integer_range is only valid for integer parameters")
        minimum, maximum, step = payload["minimum"], payload["maximum"], payload["step"]
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (minimum, maximum, step)) or step <= 0 or minimum > maximum:
            raise OptimizationSpecError("integer_range bounds/step are invalid")
        values = tuple(_valid_value(x, definition) for x in range(minimum, maximum + 1, step)
                       if definition.minimum <= x <= definition.maximum)
        if not values:
            raise OptimizationSpecError("integer_range intersection is empty")
        source = {"kind": kind, "minimum": minimum, "maximum": maximum, "step": step}
    elif kind == "explicit_values":
        if set(payload) != {"kind", "values"} or not isinstance(payload["values"], list) or not payload["values"]:
            raise OptimizationSpecError("explicit_values fields are strict and non-empty")
        values = tuple(_valid_value(x, definition) for x in payload["values"])
        if len(values) != len(set(values)):
            raise OptimizationSpecError("explicit search values must be unique")
        source = {"kind": kind, "values": list(values)}
    else:
        raise OptimizationSpecError(f"unsupported search space kind: {kind}")
    return SearchSpace(kind, values, source)
