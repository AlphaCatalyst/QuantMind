"""QuantGPT meta-evolution adapter constrained to QuantMind executable factors."""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.engine.research.quantgpt_expression_guard import (
    SupportedFactorExpression,
    factor_expression_key,
    normalize_factor_expression,
    parse_supported_factor_expression,
    validate_quantgpt_candidate_expression,
)


_DEFAULT_SEEDS = (
    "rank(close / ts_mean(close, 20))",
    "rank(ts_delta(close, 5) / ts_shift(close, 5))",
    "rank(ts_corr(rank(close), rank(volume), 10))",
)
_MEAN_WINDOWS = (5, 10, 20, 40, 60, 120)
_MOMENTUM_WINDOWS = (2, 3, 5, 10, 20, 40)
_VOLATILITY_WINDOWS = (5, 10, 20, 40, 60)
_CORRELATION_WINDOWS = (5, 10, 20, 40, 60)
_TRANSFORM_WINDOWS = (5, 10, 20, 40)


@dataclass(frozen=True)
class QuantGPTEvolutionCandidate:
    expression: str
    source_strategy: str
    reason: str


@dataclass(frozen=True)
class QuantGPTEvolutionResult:
    strategy: str
    quantgpt_strategy: str
    candidates: list[QuantGPTEvolutionCandidate]


def generate_quantgpt_evolution_candidates(
    *,
    seed_expressions: list[str],
    max_candidates: int,
    strategy: str,
    exclude_keys: set[str] | None = None,
    iteration_history: list[dict[str, Any]] | None = None,
) -> QuantGPTEvolutionResult:
    """Generate QuantGPT-guided candidates that the current evaluator can run."""
    normalized_strategy = str(strategy or "").strip()
    if normalized_strategy not in {
        "quantgpt_meta_evolution",
        "quantgpt_crossover_only",
    }:
        raise ValueError("unsupported QuantGPT evolution strategy")

    exclude_keys = exclude_keys or set()
    parsed_seeds = _parse_seed_expressions(seed_expressions)
    if not parsed_seeds:
        parsed_seeds = _parse_seed_expressions(list(_DEFAULT_SEEDS))

    history = _normalize_iteration_history(iteration_history or [])
    quantgpt_strategy = "recombine"
    if normalized_strategy == "quantgpt_meta_evolution":
        quantgpt_strategy = _select_meta_strategy(parsed_seeds, history)

    raw_candidates: list[QuantGPTEvolutionCandidate] = []
    if normalized_strategy == "quantgpt_crossover_only":
        raw_candidates.extend(_build_crossover_candidates(parsed_seeds, history))
    elif quantgpt_strategy == "recombine":
        raw_candidates.extend(_build_crossover_candidates(parsed_seeds, history))
    if normalized_strategy != "quantgpt_crossover_only":
        if quantgpt_strategy == "simplify":
            raw_candidates.extend(_build_simplify_candidates(parsed_seeds))
        elif quantgpt_strategy == "explore":
            raw_candidates.extend(_build_explore_candidates(parsed_seeds))
        else:
            raw_candidates.extend(_build_exploit_candidates(parsed_seeds, history))

    unique: list[QuantGPTEvolutionCandidate] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        try:
            parsed = validate_quantgpt_candidate_expression(candidate.expression)
        except ValueError:
            continue
        if parsed.key in seen or parsed.key in exclude_keys:
            continue
        seen.add(parsed.key)
        unique.append(
            QuantGPTEvolutionCandidate(
                expression=parsed.expression,
                source_strategy=candidate.source_strategy,
                reason=candidate.reason,
            )
        )
        if len(unique) >= max(1, max_candidates):
            break

    return QuantGPTEvolutionResult(
        strategy=normalized_strategy,
        quantgpt_strategy=quantgpt_strategy,
        candidates=unique,
    )


def _parse_seed_expressions(expressions: list[str]) -> list[SupportedFactorExpression]:
    parsed: list[SupportedFactorExpression] = []
    for expression in expressions:
        candidate = parse_supported_factor_expression(expression)
        if candidate is not None and candidate.key not in {item.key for item in parsed}:
            parsed.append(candidate)
    return parsed


def _normalize_iteration_history(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for item in items:
        expression = normalize_factor_expression(str(item.get("expression") or ""))
        if not expression or parse_supported_factor_expression(expression) is None:
            continue
        try:
            score = float(item.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        history.append({"expression": expression, "score": score})
    return history


def _select_meta_strategy(
    seeds: list[SupportedFactorExpression],
    history: list[dict[str, Any]],
) -> str:
    modules = _load_quantgpt_modules()
    if modules is None or not history:
        return "exploit"
    try:
        metrics = modules["analyze_trajectory"](history)
        current = history[-1]
        current_score = float(current.get("score") or 0.0)
        current_expression = str(current.get("expression") or seeds[0].expression)
        strategy = modules["select_strategy"](
            metrics,
            current_score=current_score,
            nesting_depth=_nesting_depth(current_expression),
        )
        return str(getattr(strategy, "value", strategy))
    except Exception:
        return "exploit"


def _load_quantgpt_modules() -> dict[str, Any] | None:
    repo_path = Path(os.getenv("QUANTGPT_REPO_PATH", "/data/codebase/stock/QuantGPT"))
    if repo_path.exists():
        repo_str = str(repo_path)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
    try:
        trajectory_module = importlib.import_module("quantgpt.trajectory_analyzer")
        meta_module = importlib.import_module("quantgpt.meta_evolution")
        mutation_module = importlib.import_module("quantgpt.mutation_engine")
    except Exception:
        return None
    return {
        "analyze_trajectory": trajectory_module.analyze_trajectory,
        "select_strategy": meta_module.select_strategy,
        "MutationEngine": mutation_module.MutationEngine,
    }


def _build_exploit_candidates(
    seeds: list[SupportedFactorExpression],
    history: list[dict[str, Any]],
) -> list[QuantGPTEvolutionCandidate]:
    best_expression = _best_history_expression(history) or seeds[0].expression
    diagnosis = _diagnose_with_quantgpt(best_expression, history)
    parsed = parse_supported_factor_expression(best_expression) or seeds[0]
    candidates: list[QuantGPTEvolutionCandidate] = []
    if parsed.kind in {"mean", "hybrid"}:
        base = parsed.mean_window or 20
        field = parsed.field or "close"
        for window in _window_neighborhood(base, _MEAN_WINDOWS, 2, 252):
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=f"rank({field} / ts_mean({field}, {window}))",
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
    if parsed.kind in {"momentum", "tanh_momentum", "hybrid"}:
        base = parsed.momentum_window or 5
        for window in _window_neighborhood(base, _MOMENTUM_WINDOWS, 1, 120):
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=(
                        f"rank(ts_delta(close, {window}) / ts_shift(close, {window}))"
                    ),
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=(
                        "rank(tanh(ts_delta(close, "
                        f"{window}) / ts_shift(close, {window})))"
                    ),
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
    if parsed.kind == "volatility":
        base = parsed.volatility_window or 20
        for window in _window_neighborhood(base, _VOLATILITY_WINDOWS, 2, 252):
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=f"rank(ts_std(close, {window}))",
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
    if parsed.kind == "correlation":
        base = parsed.correlation_window or 10
        for window in _window_neighborhood(base, _CORRELATION_WINDOWS, 2, 252):
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=f"rank(ts_corr(rank(close), rank(volume), {window}))",
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
    if parsed.kind in {"ts_rank", "decay_linear", "rolling_zscore", "where_mean"}:
        base = parsed.mean_window or 20
        field = parsed.field or "close"
        for window in _window_neighborhood(base, _TRANSFORM_WINDOWS, 2, 252):
            if parsed.kind == "ts_rank":
                expression = f"rank(ts_rank({field}, {window}))"
            elif parsed.kind == "decay_linear":
                expression = f"rank(decay_linear({field}, {window}))"
            elif parsed.kind == "rolling_zscore":
                expression = f"rank(zscore({field}, {window}))"
            else:
                expression = (
                    "rank(where(close > ts_mean(close, "
                    f"{window}), close / ts_mean(close, {window}), 0))"
                )
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=expression,
                    source_strategy="quantgpt_exploit",
                    reason=diagnosis,
                )
            )
    candidates.extend(_build_crossover_candidates(seeds, history))
    return candidates


def _build_crossover_candidates(
    seeds: list[SupportedFactorExpression],
    history: list[dict[str, Any]],
) -> list[QuantGPTEvolutionCandidate]:
    parsed = list(seeds)
    for item in sorted(history, key=lambda row: float(row.get("score") or 0), reverse=True):
        expression = str(item.get("expression") or "")
        candidate = parse_supported_factor_expression(expression)
        if candidate is not None and candidate.key not in {item.key for item in parsed}:
            parsed.append(candidate)

    mean_windows = [
        item.mean_window for item in parsed if item.kind in {"mean", "hybrid"}
    ] or [20]
    momentum_windows = [
        item.momentum_window for item in parsed if item.kind in {"momentum", "hybrid"}
    ] or [5]
    candidates: list[QuantGPTEvolutionCandidate] = []
    for mean_window in mean_windows[:4]:
        for momentum_window in momentum_windows[:4]:
            if mean_window is None or momentum_window is None:
                continue
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=(
                        "rank((close / ts_mean(close, "
                        f"{mean_window})) * (ts_delta(close, {momentum_window}) / "
                        f"ts_shift(close, {momentum_window})))"
                    ),
                    source_strategy="quantgpt_recombine",
                    reason="QuantGPT meta-evolution selected recombination",
                )
            )
    return candidates


def _build_simplify_candidates(
    seeds: list[SupportedFactorExpression],
) -> list[QuantGPTEvolutionCandidate]:
    candidates: list[QuantGPTEvolutionCandidate] = []
    for seed in seeds:
        if seed.kind == "hybrid":
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=f"rank(close / ts_mean(close, {seed.mean_window or 20}))",
                    source_strategy="quantgpt_simplify",
                    reason="QuantGPT meta-evolution selected simplification",
                )
            )
            candidates.append(
                QuantGPTEvolutionCandidate(
                    expression=(
                        "rank(ts_delta(close, "
                        f"{seed.momentum_window or 5}) / "
                        f"ts_shift(close, {seed.momentum_window or 5}))"
                    ),
                    source_strategy="quantgpt_simplify",
                    reason="QuantGPT meta-evolution selected simplification",
                )
            )
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=expression,
            source_strategy="quantgpt_simplify",
            reason="QuantGPT meta-evolution selected simplification",
        )
        for expression in _DEFAULT_SEEDS
    )
    return candidates


def _build_explore_candidates(
    seeds: list[SupportedFactorExpression],
) -> list[QuantGPTEvolutionCandidate]:
    candidates = [
        QuantGPTEvolutionCandidate(
            expression=f"rank(close / ts_mean(close, {window}))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _MEAN_WINDOWS
    ]
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=f"rank(volume / ts_mean(volume, {window}))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _MEAN_WINDOWS[:5]
    )
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=f"rank(ts_delta(close, {window}) / ts_shift(close, {window}))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _MOMENTUM_WINDOWS
    )
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=f"rank(tanh(ts_delta(close, {window}) / ts_shift(close, {window})))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _MOMENTUM_WINDOWS[:4]
    )
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=f"rank(ts_std(close, {window}))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _VOLATILITY_WINDOWS
    )
    candidates.extend(
        QuantGPTEvolutionCandidate(
            expression=f"rank(ts_corr(rank(close), rank(volume), {window}))",
            source_strategy="quantgpt_explore",
            reason="QuantGPT meta-evolution selected exploration",
        )
        for window in _CORRELATION_WINDOWS
    )
    for field in ("amount", "vwap"):
        candidates.extend(
            QuantGPTEvolutionCandidate(
                expression=f"rank({field} / ts_mean({field}, {window}))",
                source_strategy="quantgpt_explore",
                reason="QuantGPT meta-evolution selected exploration",
            )
            for window in _MEAN_WINDOWS[:4]
        )
    for window in _TRANSFORM_WINDOWS:
        candidates.extend(
            [
                QuantGPTEvolutionCandidate(
                    expression=f"rank(ts_rank(close, {window}))",
                    source_strategy="quantgpt_explore",
                    reason="QuantGPT meta-evolution selected exploration",
                ),
                QuantGPTEvolutionCandidate(
                    expression=f"rank(decay_linear(close, {window}))",
                    source_strategy="quantgpt_explore",
                    reason="QuantGPT meta-evolution selected exploration",
                ),
                QuantGPTEvolutionCandidate(
                    expression=f"rank(zscore(close, {window}))",
                    source_strategy="quantgpt_explore",
                    reason="QuantGPT meta-evolution selected exploration",
                ),
                QuantGPTEvolutionCandidate(
                    expression=(
                        "rank(where(close > ts_mean(close, "
                        f"{window}), close / ts_mean(close, {window}), 0))"
                    ),
                    source_strategy="quantgpt_explore",
                    reason="QuantGPT meta-evolution selected exploration",
                ),
            ]
        )
    candidates.extend(
        [
            QuantGPTEvolutionCandidate(
                expression="rank(zscore(volume))",
                source_strategy="quantgpt_explore",
                reason="QuantGPT meta-evolution selected exploration",
            ),
            QuantGPTEvolutionCandidate(
                expression="rank(scale(volume))",
                source_strategy="quantgpt_explore",
                reason="QuantGPT meta-evolution selected exploration",
            ),
        ]
    )
    candidates.extend(_build_crossover_candidates(seeds, []))
    return candidates


def _diagnose_with_quantgpt(
    expression: str,
    history: list[dict[str, Any]],
) -> str:
    modules = _load_quantgpt_modules()
    if modules is None:
        return "QuantGPT mutation engine unavailable; used guarded window mutation"
    best_score = 0.0
    if history:
        best_score = max(float(item.get("score") or 0.0) for item in history)
    try:
        engine = modules["MutationEngine"](
            expression,
            {"backtest_summary": {"ic_mean": best_score / 1000.0, "ic_ir": best_score / 100.0}},
            best_score,
        )
        diagnosis = engine.diagnose_failure()
        return str(getattr(diagnosis.strategy, "value", diagnosis.strategy))
    except Exception:
        return "QuantGPT mutation diagnosis failed; used guarded window mutation"


def _best_history_expression(history: list[dict[str, Any]]) -> str | None:
    if not history:
        return None
    best = max(history, key=lambda item: float(item.get("score") or 0.0))
    expression = str(best.get("expression") or "")
    return expression if parse_supported_factor_expression(expression) else None


def _window_neighborhood(
    base: int,
    anchors: tuple[int, ...],
    lower: int,
    upper: int,
) -> list[int]:
    values = [base, max(lower, base // 2), min(upper, base * 2), *anchors]
    unique: list[int] = []
    for value in values:
        if lower <= value <= upper and value not in unique:
            unique.append(value)
    return unique


def _nesting_depth(expression: str) -> int:
    depth = 0
    max_depth = 0
    for char in expression:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth -= 1
    return max_depth
