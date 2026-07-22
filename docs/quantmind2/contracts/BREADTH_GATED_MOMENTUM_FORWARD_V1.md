# Breadth-Gated Momentum Forward Protocol v1

Status: implemented, research-only
Task: `QM2-R1-010`

## Frozen source

The only signal is Signal D Artifact
`lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262`:

```text
0.5*cs_zscore(momentum_120_20)+0.5*cs_zscore(residual_momentum_60)
```

Its orientation, features and weights are immutable. The R1-009 classification
is `regime_specific_factor`; this protocol does not alter the classification,
create a Candidate, or write a Factor/Strategy Registry.

## Breadth and PIT timing

The protocol reuses `momentum_factor_iteration.regimes.build_regimes` without a
second definition. Raw breadth is the share of Fixed-100 members above their
own 20-session moving average. The formal builder maps that raw series with a
one-session shift and compares it with expanding, past-only 1/3 and 2/3
quantiles after 504 sessions. Warm-up remains `unavailable`.

The gate is written economically as:

```text
gate_on[t] = breadth_regime[t-1] == narrow_or_weak
```

In runtime terms, the value returned by `build_regimes` at session `t` already
contains the raw `t-1` breadth. The consumer therefore tests the returned
`breadth_regime[t] == "narrow"` directly. Shifting the returned state again is
forbidden because it would create a two-session lag. `neutral` and `broad`
never activate the gate; thresholds, persistence and active states are not
searched.

## Fixed paths

- U: Signal D always on; TopK 20, `n_drop=5`, 10-session rebalance,
  equal weight, signal lag 1, open execution, CSI300 benchmark.
- G: the same strategy. At a scheduled rebalance, a gate-off state clears all
  risk holdings and holds zero-return cash. The state does not switch between
  scheduled rebalances.
- R: CSI300 return over the exact gate intervals used by G and zero otherwise.

`conditional_selection_alpha = G net return - R return`. The bounded
diagnostic executor models the existing `CnExchange` commission, minimum
commission, stamp duty, transfer fee and default impact parameters against the
same 1,000,000 initial capital used by formal research runs. It is mechanism
evidence, not a replacement for an official Qlib conclusion.

## Historical versus Fresh

The 2021, 2022, 2023, 2024, 2025 and 2026-01-05 through 2026-06-23 reports are
retrospective, contaminated and not Fresh evidence. Fresh evidence starts at
2026-06-24, never backfills an earlier observation, and may use earlier data
only as rolling-feature warm-up.

The immutable Fresh Lock binds the source signal, Gate Spec, Fixed-100,
Tushare authority, three paths, metrics, minimum sample policy and
`no_backfill=true`. It must exist in the Store before an incremental call.

Only `daily`, `adj_factor`, `daily_basic`, `trade_cal` and `index_daily` are
incremented. Credentials are read exclusively from `TUSHARE_TOKEN`; no CLI
token option, credential value, prefix, suffix or hash is persisted.

## Minimum evidence and status

All of the following are required before support or rejection can be assessed:

- at least 60 Fresh trading days;
- at least five completed 10-session holding windows;
- at least 20 gate-on trading days;
- at least three gate-on rebalance dates.

Below the boundary, status is `fresh_evidence_accumulating`. Once met, support
requires positive conditional selection alpha, mean gate-on RankIC and gate-on
Q10-universe plus no worse absolute maximum drawdown for G than U. Rejection
requires non-positive conditional selection alpha and Q10-universe. Remaining
cases are inconclusive. None authorizes Promotion.

## Immutable artifacts and replay

Gate Spec, historical diagnostic, Fresh Lock, incremental snapshot, Fresh
observation and Fresh assessment are separate immutable Artifact Store kinds.
Provider corrections publish a new revision; the initially observed revision
is retained. Exact replay only materializes and validates Store evidence and
must make zero Agent, Optimization, Tushare, network, Qlib, Registry and
Promotion calls and create zero artifacts or blobs.
