from pathlib import Path

import numpy as np
import pandas as pd

from backend.services.engine.factor_optimization.eligibility import evaluate_eligibility, validation_candidate_order
from backend.services.engine.factor_optimization.enums import TrialStatus
from backend.services.engine.factor_optimization.metrics import compute_mechanical_metrics
from backend.services.engine.factor_optimization.models import FactorOptimizationTrial, QualityGate


def _write_values(path, values):
    path.mkdir(); pd.DataFrame({"symbol": ["A","B","A","B"], "trade_date": pd.to_datetime(["2024-01-01"]*2+["2024-01-02"]*2), "factor_value": values}).to_parquet(path/"values.parquet", index=False)


def test_metrics_full_warmup_low_constant_all_null_and_infinity(tmp_path):
    cases = {"full":[1.,2.,3.,4.], "warmup":[np.nan,np.nan,3.,4.], "constant":[1.,1.,1.,1.], "allnull":[np.nan]*4, "inf":[1.,np.inf,3.,4.]}
    metrics = {}
    for name, values in cases.items():
        path=tmp_path/name; _write_values(path,values); metrics[name]=compute_mechanical_metrics(path,1)
    assert metrics["full"].finite_coverage == 1 and metrics["full"].median_daily_finite_symbols == 2
    assert metrics["warmup"].warmup_date_count == 1 and metrics["warmup"].daily_coverage_minimum == 0
    assert metrics["constant"].constant_output
    assert metrics["allnull"].non_null_count == 0
    assert metrics["inf"].infinity_count == 1 and metrics["inf"].finite_coverage == 0.75


def test_eligibility_and_frozen_candidate_ordering_tie_breaker(tmp_path):
    path=tmp_path/"values"; _write_values(path,[1.,2.,3.,4.]); metrics=compute_mechanical_metrics(path,0)
    gate=QualityGate(minimum_median_daily_finite_symbols=2,minimum_date_count=2,minimum_symbol_count=2)
    assert evaluate_eligibility("succeeded",metrics,gate)==(True,())
    trials=[]
    for trial_id in ("fot_b","fot_a"):
        trials.append(FactorOptimizationTrial(trial_id,0,{},"fi",TrialStatus.SUCCEEDED,"fv","h",metrics,True,(),None))
    assert validation_candidate_order(trials)==("fot_a","fot_b")


def test_ineligibility_reasons_are_mechanical(tmp_path):
    path=tmp_path/"values"; _write_values(path,[1.,1.,1.,1.]); metrics=compute_mechanical_metrics(path,0)
    eligible,reasons=evaluate_eligibility("replayed",metrics,QualityGate(minimum_date_count=2,minimum_symbol_count=2))
    assert not eligible and "constant_output" in reasons
