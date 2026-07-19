#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.engine.historical_agent_experiment.missingness import audit_locked_signals


CANDIDATE_ONE = "fi_f081f972214bf40e8d5ef6d4126180e296b055ce9c0ff7fa0cafa7f2df0d7be4"
CANDIDATE_TWO = "fi_d825122e2a8808463b0c9b098e2a487c7cc373d3b8f0d178ce9d505247e4430e"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Audit locked 2026H1 factor-signal missingness")
    value.add_argument("--dataset-directory", type=Path, required=True)
    value.add_argument("--universe-lock", type=Path, required=True)
    value.add_argument("--round-one-lock", type=Path, required=True)
    value.add_argument("--round-three-lock", type=Path, required=True)
    value.add_argument("--factor-values-root", type=Path, required=True)
    value.add_argument("--signal-root", type=Path, required=True)
    value.add_argument("--qlib-view-directory", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def _candidate(lock: dict, factor_id: str) -> dict:
    matches = [row for row in lock["candidates"]
               if row["selected_trial"]["factor_instance_id"] == factor_id]
    if len(matches) != 1:
        raise ValueError(f"locked candidate {factor_id} is absent or ambiguous")
    return matches[0]


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    universe = json.loads(args.universe_lock.read_text())
    round_one = json.loads(args.round_one_lock.read_text())
    round_three = json.loads(args.round_three_lock.read_text())
    candidate_one = _candidate(round_three, CANDIDATE_ONE)
    candidate_two = _candidate(round_one, CANDIDATE_TWO)
    factor_values = {
        CANDIDATE_ONE: args.factor_values_root / candidate_one["selected_trial"]["factor_values_id"],
        CANDIDATE_TWO: args.factor_values_root / candidate_two["selected_trial"]["factor_values_id"],
    }
    signals = {
        CANDIDATE_ONE: args.signal_root / f"{CANDIDATE_ONE}.parquet",
        CANDIDATE_TWO: args.signal_root / f"{CANDIDATE_TWO}.parquet",
        "equal_weight_combo": args.signal_root / "equal_weight_combo.parquet",
    }
    result = audit_locked_signals(
        dataset_directory=args.dataset_directory,
        universe_lock=universe,
        candidates=[candidate_one, candidate_two],
        qlib_view_directory=args.qlib_view_directory,
        factor_values_directories=factor_values,
        signal_paths=signals,
        source_experiment_id="hae_5e4b11baed63c300d5c3964b8480ad3115f8864e096a1610c5afc5db0ab3fedd",
        source_backtest_result_id="qbr_b8be0692a4b4b897bc89a93596c2f31a4d89b8cea2d7ca1cd76c6dd0929f9dc0",
        output_root=args.output_root,
    )
    summary = {
        "signal_missingness_audit_id": result["audit"]["signal_missingness_audit_id"],
        "historical_backtest_followup_id": result["followup"]["historical_backtest_followup_id"],
        "status": "blocked", "qlib_backtest_calls": 0,
        "original_gate_nan_ratio": result["layer_metrics"]["original_gate_nan_ratio"],
        "expected_grid_missing_ratio": result["layer_metrics"]["expected_grid_nan_ratio"],
        "primary_layer": result["root_cause"]["primary_layer"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
