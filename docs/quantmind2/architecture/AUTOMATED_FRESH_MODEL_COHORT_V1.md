# Automated Fresh Model Cohort Observation v1

Status: accepted implementation contract for `QM2-R2-009`.

## Boundary

The component observes exactly the two immutable `QM2-R2-008` L1
retrospective Model Candidates. It does not create Features, tune models or
strategies, change Candidate or Registry state, promote research, or trade.
The executable Label is `technical_return_1d`: signal at T, adjusted open
entry at T+1, and adjusted close exit at T+1. Runtime identity drift is a hard
`EXECUTABLE_LABEL_IDENTITY_MISMATCH`.

## Cohort and data

`ModelFreshCandidateCohortV1` is published before the first Fresh market read
and freezes two Candidate/Fresh-Lock pairs, the L1 Label, daily RankIC, HAC lag
10, BH FDR 10%, three model seeds, monthly retraining, minimum evidence, and
TopK20/drop5/rebalance10. The formal start is the first official A-share open
date strictly after 2026-07-23; it is calendar-derived, never hardcoded.

Incremental collection uses only Tushare `daily`, `adj_factor`,
`daily_basic`, `trade_cal`, and `index_daily`. Each successful increment is an
immutable first-seen Snapshot with schema, mapping, adjustment, calendar,
lifecycle, duplicate, missing-value, checksum, endpoint, and call evidence.
An interrupted run consumes an unprocessed Store Snapshot before any new
network request.

## Model observation

Bundle B retains all 20 frozen Terminal Features and six frozen Primitives.
Bundle C re-applies the frozen label-free selection rule using training data
only. Existing LightGBM parameters, 200 rounds, no early stopping, and three
equal-weight seeds are unchanged. Predictions are cross-sectional rank
signals with lag one. Training and label cutoffs must precede the prediction
being observed.

Fresh evidence remains `fresh_evidence_accumulating` until both Cohort members
have at least 60 trading days, five completed holding windows, three rebalance
periods, two monthly retraining events, 90% coverage, and zero PIT violations.
Only then may the fixed two-hypothesis HAC/BH assessment run. No result grants
Registry or Promotion authority.

## Operations and replay

The project-local heartbeat is idempotent and Store-backed. Snapshot,
training, seed model, prediction, mature label, strategy, assessment, and
heartbeat artifacts are checkpoints. Exact replay and cold inspection perform
zero external calls, computations, or writes. The project supplies a scheduler
entry contract but does not install or load `launchd`, cron, or another system
scheduler.
