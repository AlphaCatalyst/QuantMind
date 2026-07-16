import numpy as np
import pandas as pd

from backend.services.engine.market_data.feature_snapshot import load_feature_matrix

from .artifact import publish_values, validate_values
from .enums import NodeKind
from .errors import ExecutionError
from .models import ExecutionResult
from .quality import factor_quality


def _evaluate(node, frame, parameters):
    kind = node.kind
    if kind is NodeKind.FEATURE:
        return frame[node.fields["name"]].astype(float)
    if kind is NodeKind.PARAMETER:
        return parameters[node.fields["name"]]
    if kind is NodeKind.CONSTANT:
        return node.fields["value"]
    if kind in (NodeKind.ADD, NodeKind.SUBTRACT, NodeKind.MULTIPLY, NodeKind.DIVIDE):
        left = _evaluate(node.fields["left"], frame, parameters)
        right = _evaluate(node.fields["right"], frame, parameters)
        if kind is NodeKind.ADD: return left + right
        if kind is NodeKind.SUBTRACT: return left - right
        if kind is NodeKind.MULTIPLY: return left * right
        if np.isscalar(right):
            return np.nan if abs(right) <= 1e-12 else left / right
        denominator = right.astype(float)
        return left / denominator.where(denominator.abs() > 1e-12)
    if kind is NodeKind.NEGATE:
        return -_evaluate(node.fields["operand"], frame, parameters)
    if kind is NodeKind.ABSOLUTE:
        return abs(_evaluate(node.fields["operand"], frame, parameters))
    if kind is NodeKind.CLIP:
        value = _evaluate(node.fields["operand"], frame, parameters)
        lower = _evaluate(node.fields["lower"], frame, parameters)
        upper = _evaluate(node.fields["upper"], frame, parameters)
        return value.clip(lower=lower, upper=upper) if isinstance(value, pd.Series) else min(max(value, lower), upper)
    if kind in (NodeKind.LAG, NodeKind.DELTA):
        value = _evaluate(node.fields["operand"], frame, parameters)
        periods = int(_evaluate(node.fields["periods"], frame, parameters))
        grouped = value.groupby(frame["symbol"], sort=False)
        return grouped.shift(periods) if kind is NodeKind.LAG else value - grouped.shift(periods)
    if kind in (NodeKind.ROLLING_MEAN, NodeKind.ROLLING_STD, NodeKind.ROLLING_MIN, NodeKind.ROLLING_MAX):
        value = _evaluate(node.fields["operand"], frame, parameters)
        window = int(_evaluate(node.fields["window"], frame, parameters))
        grouped = value.groupby(frame["symbol"], sort=False)
        if kind is NodeKind.ROLLING_MEAN:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).mean())
        if kind is NodeKind.ROLLING_STD:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).std(ddof=0))
        if kind is NodeKind.ROLLING_MIN:
            return grouped.transform(lambda x: x.rolling(window, min_periods=window).min())
        return grouped.transform(lambda x: x.rolling(window, min_periods=window).max())
    value = _evaluate(node.fields["operand"], frame, parameters)
    grouped = value.groupby(frame["trade_date"], sort=False)
    if kind is NodeKind.CS_RANK:
        return grouped.transform(lambda x: x.rank(method="average", pct=True) if x.notna().sum() >= 2 else pd.Series(np.nan, index=x.index))
    if kind is NodeKind.CS_ZSCORE:
        def zscore(x):
            if x.notna().sum() < 2:
                return pd.Series(np.nan, index=x.index)
            std = x.std(ddof=0)
            return pd.Series(np.nan, index=x.index) if not np.isfinite(std) or std == 0 else (x - x.mean()) / std
        return grouped.transform(zscore)
    raise ExecutionError(f"unhandled node {kind.value}")


def execute_compiled(compiled, snapshot_root, output_root):
    try:
        frame = load_feature_matrix(snapshot_root, compiled.snapshot_id, feature_columns=compiled.required_features)
        frame = frame.sort_values(["trade_date", "symbol"], kind="mergesort").reset_index(drop=True)
        if frame.duplicated(["symbol", "trade_date"]).any():
            raise ExecutionError("Dataset Snapshot contains duplicate factor keys")
        values = _evaluate(compiled.template.expression, frame, compiled.bound_parameters)
        if not isinstance(values, pd.Series):
            raise ExecutionError("compiled factor did not produce a series")
        output = frame[["symbol", "trade_date"]].copy()
        output["factor_value"] = values.astype(float)
        quality = factor_quality(output, compiled.warmup_periods)
        quality["compiler_warnings"] = list(compiled.warnings)
        values_id, path, manifest, replayed = publish_values(output, compiled, quality, output_root)
        validate_values(snapshot_root, output_root, values_id)
        return ExecutionResult(values_id, str(path), manifest, replayed)
    except ExecutionError:
        raise
    except Exception as exc:
        raise ExecutionError(str(exc)) from exc
