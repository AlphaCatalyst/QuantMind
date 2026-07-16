import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.services.engine.factor_validation.errors import FrozenAccessError, ValidationSpecError
from backend.services.engine.factor_validation.frozen import evaluate_frozen
from backend.services.engine.factor_validation.labels import build_production_labels, label_contract_id, production_label_contract
from backend.services.engine.factor_validation.metrics import calculate_split_metrics, selection_eligibility, train_orientation
from backend.services.engine.factor_validation.models import FrozenTestAccessContext
from backend.services.engine.factor_validation.parser import parse_validation_spec


def test_production_label_formula_horizon_dtype_missing_and_determinism():
    dates = pd.date_range("2024-01-02", periods=3)
    rows = []
    for symbol, base in (("SH600000", 10.0), ("SZ300001", 20.0)):
        for index, day in enumerate(dates):
            rows.append({"symbol": symbol, "trade_date": day, "open": base + index,
                         "close": base + index + .5, "factor": 2.0})
    contract = production_label_contract(1)
    output = build_production_labels(pd.DataFrame(rows), contract)
    first = output[(output.symbol == "SH600000") & (output.trade_date == dates[0])].iloc[0]
    assert first.raw_label == pytest.approx((11.5 * 2) / (11 * 2) - 1)
    assert first.entry_trade_date == dates[1] == first.exit_trade_date
    assert output.groupby("symbol").tail(1).raw_label.isna().all()
    assert output.raw_label.dtype == "float64"
    assert label_contract_id(contract) == label_contract_id(production_label_contract(1))


def test_production_prefix_limit_branch_matches_reality():
    frame = pd.DataFrame([
        {"symbol": "SZ300001", "trade_date": "2024-01-01", "open": 10, "close": 10, "factor": 1},
        {"symbol": "SZ300001", "trade_date": "2024-01-02", "open": 11, "close": 11, "factor": 1},
    ])
    result = build_production_labels(frame, production_label_contract())
    assert result.iloc[0].sample_weight == .5  # Effective 9.5%, not intended prefix-blind 19.5%.


def _metric_frames(sign=1, constant=False, dates=5, symbols=30):
    values, labels = [], []
    for day in pd.date_range("2024-01-01", periods=dates):
        for index in range(symbols):
            value = 1.0 if constant else float(index)
            values.append({"symbol": f"S{index:03d}", "trade_date": day, "factor_value": value})
            labels.append({"symbol": f"S{index:03d}", "trade_date": day, "model_label": sign * float(index)})
    return pd.DataFrame(values), pd.DataFrame(labels)


def test_daily_ic_rank_ic_coverage_and_positive_rate():
    values, labels = _metric_frames()
    metrics = calculate_split_metrics(values, labels)
    assert metrics.date_count_total == metrics.date_count_valid == 5
    assert metrics.mean_ic == pytest.approx(1); assert metrics.mean_rank_ic == pytest.approx(1)
    assert metrics.ic_positive_rate == metrics.rank_ic_positive_rate == 1
    assert metrics.factor_finite_coverage == metrics.label_finite_coverage == 1
    assert metrics.icir is None and metrics.rank_icir is None


def test_rank_ic_ties_nan_insufficient_and_constant():
    values, labels = _metric_frames(constant=True)
    values.loc[0, "factor_value"] = np.nan
    metrics = calculate_split_metrics(values, labels)
    assert metrics.constant_output is True and metrics.mean_ic is None and metrics.mean_rank_ic is None
    small_values, small_labels = _metric_frames(symbols=19)
    assert calculate_split_metrics(small_values, small_labels).date_count_valid == 0


def test_train_only_orientation_and_eligibility():
    values, labels = _metric_frames(sign=-1, dates=110, symbols=100)
    raw = calculate_split_metrics(values, labels)
    assert train_orientation(raw) == -1
    oriented = calculate_split_metrics(values, labels, orientation=-1)
    requirements = {"train_minimum_valid_rank_ic_dates": 100, "validation_minimum_valid_rank_ic_dates": 100,
                    "train_minimum_median_daily_observations": 100, "validation_minimum_median_daily_observations": 100,
                    "minimum_factor_finite_coverage": .5}
    # Perfect stability intentionally has null ICIR and therefore cannot pass the stated gate.
    eligible, reasons = selection_eligibility(oriented, oriented, requirements)
    assert not eligible and "validation_rank_icir_unavailable" in reasons


def _valid_spec():
    return {"schema_version": "1.0.0", "name": "real_14_trials", "description": "validation",
            "validation_dataset_id": "vd_" + "a" * 64,
            "optimization_study_ids": ["fos_" + "b" * 64, "fos_" + "c" * 64],
            "trial_ids": ["fot_" + f"{index:064x}" for index in range(14)],
            "metrics": ["ic", "rank_ic", "icir", "positive_rate", "coverage"],
            "minimum_requirements": {"train_minimum_valid_rank_ic_dates": 100,
              "validation_minimum_valid_rank_ic_dates": 100, "train_minimum_median_daily_observations": 100,
              "validation_minimum_median_daily_observations": 100, "minimum_factor_finite_coverage": .5},
            "candidate_selection": {"ordering": "validation_predictive_order_v1", "top_k": 3},
            "frozen_test_policy": {"protocol_id": "qm2-frozen-2026-v1", "one_time": True,
                                   "candidate_source": "published_selection", "reselection": "forbidden"}}


def test_validation_spec_strict_schema_and_fourteen_trials():
    assert len(parse_validation_spec(_valid_spec()).trial_ids) == 14
    bad = _valid_spec(); bad["extra"] = True
    with pytest.raises(ValidationSpecError): parse_validation_spec(bad)
    bad = _valid_spec(); bad["trial_ids"] = bad["trial_ids"][:-1]
    with pytest.raises(ValidationSpecError): parse_validation_spec(bad)


def test_frozen_context_and_published_selection_are_required(tmp_path):
    with pytest.raises(FrozenAccessError): evaluate_frozen(None, dataset_root=tmp_path, validation_root=tmp_path, factor_values_root=tmp_path)
    context = FrozenTestAccessContext("p", "vd_" + "a" * 64, "fvs_" + "b" * 64, "final", "test")
    with pytest.raises(FrozenAccessError): evaluate_frozen(context, dataset_root=tmp_path, validation_root=tmp_path, factor_values_root=tmp_path)


def test_frozen_protocol_rejects_different_candidate_set_before_label_access(tmp_path):
    validation = tmp_path / "validation"; selections = validation / "selections" / ("fvs_" + "b" * 64)
    selections.mkdir(parents=True)
    (selections / "selection.json").write_text(json.dumps({"validation_dataset_id": "vd_" + "a" * 64, "candidates": []}))
    protocol = validation / "frozen_protocols" / "p"; protocol.mkdir(parents=True)
    (protocol / "lock.json").write_text(json.dumps({"candidate_selection_id": "fvs_" + "c" * 64,
        "validation_dataset_id": "vd_" + "a" * 64, "frozen_result_id": "fvt_" + "d" * 64}))
    context = FrozenTestAccessContext("p", "vd_" + "a" * 64, "fvs_" + "b" * 64, "final", "test")
    with pytest.raises(FrozenAccessError, match="different immutable candidate set"):
        evaluate_frozen(context, dataset_root=tmp_path / "missing", validation_root=validation, factor_values_root=tmp_path)


def _imports(path):
    tree = ast.parse(path.read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom): names.append(node.module or "")
    return names


def test_optimizer_and_dsl_have_no_validation_or_label_imports():
    root = Path(__file__).parents[1] / "engine"
    for package in (root / "factor_optimization", root / "factor_dsl"):
        for path in package.glob("*.py"):
            assert not any("factor_validation" in name for name in _imports(path))


def test_only_frozen_evaluator_reads_frozen_label_artifact():
    package = Path(__file__).parents[1] / "engine" / "factor_validation"
    readers = []
    for path in package.glob("*.py"):
        text = path.read_text()
        if 'pd.read_parquet(root / "label_snapshot" / "frozen_labels.parquet"' in text: readers.append(path.name)
    assert readers == ["frozen.py"]
