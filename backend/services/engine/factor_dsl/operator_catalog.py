from dataclasses import dataclass
from typing import Tuple

from .enums import NodeKind


@dataclass(frozen=True)
class OperatorDefinition:
    kind: NodeKind
    arguments: Tuple[str, ...]
    series_required: bool
    time_direction: str


OPERATOR_CATALOG = (
    OperatorDefinition(NodeKind.ADD, ("left", "right"), False, "point_in_time"),
    OperatorDefinition(NodeKind.SUBTRACT, ("left", "right"), False, "point_in_time"),
    OperatorDefinition(NodeKind.MULTIPLY, ("left", "right"), False, "point_in_time"),
    OperatorDefinition(NodeKind.DIVIDE, ("left", "right"), False, "point_in_time"),
    OperatorDefinition(NodeKind.NEGATE, ("operand",), False, "point_in_time"),
    OperatorDefinition(NodeKind.ABSOLUTE, ("operand",), False, "point_in_time"),
    OperatorDefinition(NodeKind.CLIP, ("operand", "lower", "upper"), False, "point_in_time"),
    OperatorDefinition(NodeKind.LAG, ("operand", "periods"), True, "trailing_only"),
    OperatorDefinition(NodeKind.DELTA, ("operand", "periods"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_MEAN, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_STD, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_MIN, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_MAX, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_SUM, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_CORR, ("left", "right", "window"), True, "trailing_only_pairwise_finite"),
    OperatorDefinition(NodeKind.ROLLING_MEDIAN, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_QUANTILE, ("operand", "window", "quantile"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_SKEW, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.ROLLING_ARGMAX_AGE, ("operand", "window"), True, "trailing_only"),
    OperatorDefinition(NodeKind.CS_RANK, ("operand",), True, "same_date_only"),
    OperatorDefinition(NodeKind.CS_ZSCORE, ("operand",), True, "same_date_only"),
)
