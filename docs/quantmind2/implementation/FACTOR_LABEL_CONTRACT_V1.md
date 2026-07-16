# Factor Label Contract v1

## Production reality

The executable authority is `docker/training/train.py:load_data`, called by
`docker/training/train.py:main`; the local orchestrator writes
`target_horizon_days` into its YAML input. The default horizon is one observed
trading row. Metadata `label_formula` strings are descriptive and are not the
executed label authority.

At observation date T, source `open`, `close`, and `factor` are first cast to
float32. The raw label is:

`(close[T+H] * factor[T+H]) / (open[T+1] * factor[T+1]) - 1`

For v1, H=1: the factor observed after T predicts the next observed row's open
to close return. It joins Factor Values on `(symbol, observation_trade_date)`,
not on entry or exit date. Rows with non-positive/unavailable next open or
unavailable future close are null and excluded.

The production code retains next-open extreme observations and assigns weight
0.5 rather than dropping them. Although the source intends 19.5% for `688` and
`300`, real symbols are prefixed (`SH688...`, `SZ300...`), so that branch is
currently unreachable and the effective threshold is 9.5% for every admitted
symbol. Validation preserves this behavior instead of silently correcting it.

The model label is the raw return grouped by observation date, MAD-clipped at
five median absolute deviations, then z-scored with sample standard deviation
through `backend/shared/feature_preprocess.py`. MAD zero/all-null groups become
zero. `model_label` is the default validation target; `raw_label` and
`sample_weight` remain separately materialized. IC is unweighted in v1.

## Contract and PIT boundary

`LabelContract` binds formula, observation/entry/exit time, horizon, adjustment,
tradability, missing, transform, dtype and default label column. The immutable
ID is `lc_f4cc31c4ebddf9f14623c639fd040be2bf7dcde5c2ad3bc8e98a6bf74205b744`.
Label generation is separate from DSL and Optimization. Feature code cannot
receive label columns. Adjustment-factor point-in-time provenance upstream is
not proven by this task; v1 proves parity with current source bytes and current
training behavior, not vendor PIT correctness.

Parity tests cover the float32 conversion, formula, horizon boundary, missing
last row, transform, weights, deterministic identity and effective prefix
behavior. The immutable Label Snapshot records source inventory and file
hashes; source drift changes the validation Dataset identity.
