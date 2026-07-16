# Factor Validation v1

## Scope and data

Factor Validation consumes the two immutable QM2-P0-005 Studies and all 14
Trials. It does not add parameters, rerun Optimization, alter templates, train
LightGBM, run Qlib, compute portfolios, Sharpe or trading returns, or promote a
Factor to Registry.

The real dataset is
`vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62`.
It binds 300 symbols common to annual 2021–2026 Legacy sources, the four actual
feature terminals, production label inputs and contract, source inventory,
split rules and output hashes. Its compatible feature-only Snapshot is
`ds_dd1defb79ddf2a81f057be9e34715cb04df340204d68338f73ab1ad4692e338f`.
Factor warmup may consume earlier feature-only history. Earlier labels never
cross a split boundary.

| Split | Effective dates | Dates | Role |
|---|---:|---:|---|
| Train | 2022-01-04..2023-12-28 | 483 | orientation and quality only |
| Validation | 2024-01-02..2024-12-30 | 241 | eligibility and ordering |
| Quarantined development | 2025-01-02..2025-12-30 | 242 | excluded from formal evidence |
| Frozen Test | 2026-01-05..2026-06-23 | 111 | independent confirmation only |

The last observed date in every year is purged because the H=1 label crosses
the boundary or is incomplete: 2023-12-29, 2024-12-31, 2025-12-31 and
2026-06-24. Embargo is one observed trading date. Maximum candidate lookback is
20; warmup uses feature history but never prior-split labels. The 2025 period is
quarantined because it was used for DSL/template/Optimization development.

## Metrics and selection

Factor and label align one-to-one on `(symbol, trade_date)`. No row-order join,
forward fill or missing-label zero fill is permitted. Every date needs at least
20 finite pairs. IC is Pearson; RankIC is average-rank then Pearson. Constant
cross-sections and insufficient dates yield null. ICIR is `mean/std` with
population standard deviation and is not annualized.

Orientation is +1 or -1 from Train mean RankIC only and is fixed for Validation
and Frozen. Admission requires at least 100 valid Train and Validation RankIC
dates, median 100 observations, factor finite coverage 0.5, nonconstant Train,
non-null Validation RankICIR, positive oriented Validation mean RankIC and
positive rate above 0.5.

Four trials passed. Validation-only order was:

1. `fot_4d78ce9...edf2`
2. `fot_566b3358...e7ec`
3. `fot_187f3394...e12d`
4. `fot_ea31b7ae...6f72`

Top three were frozen in selection
`fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c`.
The complete result is
`fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0`.
All 14 Trial records preserve original Study/Trial/Template/parameters plus new
Snapshot-bound Instance and Values identities, raw/oriented Train and
Validation metrics, reasons, rank and selection flag.

These are predictive statistics on one bounded sample, not proof of alpha,
future return, tradability or Registry eligibility. Registry promotion remains
deferred to QM2-P0-007.
