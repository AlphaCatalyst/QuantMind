from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from backend.services.engine.tushare_cutover.canonical import hash_payload

from .models import AUTHORIZED_OPERATORS, PRIMITIVES, WINDOWS


class FeatureGrammarError(ValueError):
    pass


@dataclass(frozen=True)
class AstAudit:
    primitives: tuple[str, ...]
    windows: tuple[int, ...]
    operator_count: int
    depth: int
    structural_fingerprint: str


def _children(node: dict) -> list[dict]:
    kind = node.get("type")
    if kind in {"add", "subtract", "multiply", "safe_divide"}:
        return [node.get("left"), node.get("right")]
    if kind in {"negate", "abs", "clip", "lag", "delta", "rolling_mean",
                "rolling_std", "rolling_min", "rolling_max"}:
        return [node.get("operand")]
    return []


def audit_ast(ast: dict) -> AstAudit:
    if not isinstance(ast, dict):
        raise FeatureGrammarError("FEATURE_AST_INVALID")
    primitives: set[str] = set()
    windows: set[int] = set()
    operators = 0

    def visit(node: Any, depth: int) -> int:
        nonlocal operators
        if not isinstance(node, dict) or not isinstance(node.get("type"), str):
            raise FeatureGrammarError("FEATURE_AST_INVALID")
        kind = node["type"]
        if kind == "feature":
            name = node.get("name")
            if name not in PRIMITIVES:
                raise FeatureGrammarError("FEATURE_PRIMITIVE_NOT_AUTHORIZED")
            primitives.add(name)
            return depth
        if kind == "constant":
            value = node.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
                raise FeatureGrammarError("FEATURE_CONSTANT_INVALID")
            return depth
        if kind not in AUTHORIZED_OPERATORS:
            raise FeatureGrammarError("FEATURE_OPERATOR_NOT_AUTHORIZED")
        operators += 1
        if kind in {"lag", "delta"}:
            periods = node.get("periods")
            if periods not in WINDOWS:
                raise FeatureGrammarError("FEATURE_WINDOW_NOT_AUTHORIZED")
            windows.add(periods)
        if kind.startswith("rolling_"):
            window = node.get("window")
            if window not in WINDOWS:
                raise FeatureGrammarError("FEATURE_WINDOW_NOT_AUTHORIZED")
            windows.add(window)
        if kind == "clip":
            lower, upper = node.get("lower"), node.get("upper")
            if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)) or lower >= upper:
                raise FeatureGrammarError("FEATURE_CLIP_INVALID")
        children = _children(node)
        if any(child is None for child in children):
            raise FeatureGrammarError("FEATURE_AST_INVALID")
        return max([depth] + [visit(child, depth + 1) for child in children])

    depth = visit(ast, 1)
    if not primitives or len(primitives) > 4:
        raise FeatureGrammarError("FEATURE_PRIMITIVE_LIMIT")
    if len(windows) > 2:
        raise FeatureGrammarError("FEATURE_WINDOW_PARAMETER_LIMIT")
    if depth > 6:
        raise FeatureGrammarError("FEATURE_AST_DEPTH_LIMIT")
    if operators > 8:
        raise FeatureGrammarError("FEATURE_OPERATOR_COUNT_LIMIT")
    fingerprint = hash_payload(ast)
    return AstAudit(tuple(sorted(primitives)), tuple(sorted(windows)), operators, depth, fingerprint)


def _series(node: dict, frame: pd.DataFrame) -> pd.Series:
    kind = node["type"]
    if kind == "feature":
        return pd.to_numeric(frame[node["name"]], errors="coerce")
    if kind == "constant":
        return pd.Series(float(node["value"]), index=frame.index)
    if kind in {"add", "subtract", "multiply", "safe_divide"}:
        left, right = _series(node["left"], frame), _series(node["right"], frame)
        if kind == "add":
            return left + right
        if kind == "subtract":
            return left - right
        if kind == "multiply":
            return left * right
        denominator = right.where(right.abs() > 1e-12)
        return (left / denominator).replace([np.inf, -np.inf], np.nan)
    value = _series(node["operand"], frame)
    if kind == "negate":
        return -value
    if kind == "abs":
        return value.abs()
    if kind == "clip":
        return value.clip(float(node["lower"]), float(node["upper"]))
    grouped = value.groupby(frame["symbol"], sort=False)
    if kind == "lag":
        return grouped.shift(int(node["periods"]))
    if kind == "delta":
        return value - grouped.shift(int(node["periods"]))
    window = int(node["window"])
    rolling = grouped.rolling(window, min_periods=window)
    if kind == "rolling_mean":
        result = rolling.mean()
    elif kind == "rolling_std":
        result = rolling.std(ddof=0)
    elif kind == "rolling_min":
        result = rolling.min()
    elif kind == "rolling_max":
        result = rolling.max()
    else:
        raise FeatureGrammarError("FEATURE_OPERATOR_NOT_AUTHORIZED")
    return result.reset_index(level=0, drop=True).sort_index()


def evaluate_ast(ast: dict, frame: pd.DataFrame) -> pd.Series:
    audit_ast(ast)
    if not frame.sort_values(["symbol", "trade_date"]).index.equals(frame.index):
        raise FeatureGrammarError("FEATURE_INPUT_ORDER_INVALID")
    return _series(ast, frame).replace([np.inf, -np.inf], np.nan)


def expression(ast: dict) -> str:
    return json.dumps(ast, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
