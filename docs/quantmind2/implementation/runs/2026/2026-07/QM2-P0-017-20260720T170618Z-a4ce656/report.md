# QM2-P0-017 Implementation Report

## 1. Task Summary

`completed_uncommitted`. Strategy Parameter Optimization v1 executed the
frozen 96-Trial grid on four immutable Unified Signals, selected one
research-only parameter candidate per signal using only 2019--2024 annual
CSI300 evidence, and reported 2025/2026H1 only after Candidate Lock.

## 2. Goal and Scope

- Search only TopK, n_drop and Qlib trade-date rebalance interval.
- Keep Universe, signal, weighting, lag, open execution, costs, CSI300 and
  lifecycle semantics fixed.
- Preserve separate Study, Trial, formal Strategy Result, Candidate Lock and
  Optimization Result identities.
- Publish to the Store, cold recover and exact replay with zero execution
  calls.

## 3. Explicit Non-goals

No Agent, Factor structure/parameter optimization, signal transform/weight
change, universe/benchmark/cost/price/lag/risk search, LightGBM, Promotion,
approval, activation, database, API or UI.

## 4. Preflight State

- Repository: QuantMind main; branch `master`.
- Base commit: `a4ce6560b482e20ebf1357daff37a393ce970b99`.
- Worktree: clean; unrelated dirty files: none.
- Active authority: `tushare-pro-v1`; Fixed-100 Universe
  `tu100_078e...2c526`; Qlib View `tqv_c489ef...941ff`.
- Source Strategy Registry: `srr_a2d226...ea503`.

## 5. Architecture and Runtime Flow

```text
four locked Unified Signals
→ strict StrategyOptimizationSpec
→ 96 deterministic PlannedStrategyTrials
→ existing QlibBacktestService / RedisRecordingStrategy /
  SimulatorExecutor / CnExchange
→ formal StrategyBacktestResult per Trial
→ six annual metrics + eligibility
→ frozen lexicographic ordering per Signal
→ four StrategyParameterCandidateLocks
→ retrospective-only 2025 and 2026H1
→ StrategyOptimizationResult and research Registry
→ Artifact Store
```

The optimization service does not copy Qlib execution logic. It calls the
existing `FormalQlibRunner`, which passes TopK, n_drop and trade-date rebalance
interval into the existing service while preserving open, one-session lag,
CSI300 and CnExchange cost configuration.

## 6. Search Space and Trial Enumeration

- TopK: 10, 20, 30.
- n_drop: 0, 5, 10.
- Rebalance interval: 1, 5, 10 Qlib trade dates.
- `n_drop >= topk` is rejected before Trial construction. Consequently
  TopK10/n_drop10 creates no Trial.
- 24 legal combinations per signal; 96 total; 96 completed and eligible.

Each Trial includes one full 2019--2024 Qlib execution plus six annual Qlib
segments. The annual segments are intentional: annual transaction cost and
turnover are observed from formal execution rather than allocated from a
full-period aggregate. The final cache contains 680 formal result records:
96 × 7 selection-period executions plus 4 × 2 post-lock reports.

An initial execution completed and cached 112 calls before it was stopped to
make the already-governed Fixed Universe Lifecycle Policy explicit for
2026H1. The resumed execution made 568 new calls and exact-reused the first
112. It did not rewrite Store objects or alter research-period results.

## 7. Candidate Ordering and Locks

The immutable ordering is: positive excess-year count, median annual net
excess, worst annual net excess, Sharpe, drawdown magnitude, turnover, cost
and Trial ID. 2025 and 2026H1 fields do not exist in the ordering function.

| Signal | TopK | n_drop | Rebalance | Positive excess years | Median annual excess | Worst year | Sharpe | Max DD | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Factor 1 (`usa_a4dad…`) | 20 | 0 | 5 | 5 | 14.48% | -10.67% | 0.692 | -28.83% | 435.70 |
| Factor 2 (`usa_5399…`) | 20 | 5 | 5 | 4 | 17.61% | -23.78% | 0.791 | -14.75% | 213.46 |
| Factor 3 (`usa_839f…`) | 30 | 5 | 10 | 4 | 15.67% | -24.75% | 0.586 | -19.70% | 75.06 |
| Equal weight (`usa_4c824…`) | 20 | 5 | 10 | 4 | 19.70% | -20.63% | 0.771 | -19.02% | 105.00 |

Candidate Lock IDs are `spcl_151237...37531`, `spcl_099b05...10fbc`,
`spcl_d4760d...7abe0` and `spcl_9228c1...85c4e`. They mean parameter candidate
locked, not validated, approved, active or production-ready.

## 8. Baseline Comparison

| Signal | Config | 2019--2024 Net | CSI300 excess | Sharpe | Max DD | Turnover | Cost |
|---|---|---:|---:|---:|---:|---:|---:|
| Factor 1 | baseline 20/5/5 | 114.72% | 82.21% | 0.557 | -33.75% | 205.24 | 297,203 |
| Factor 1 | candidate 20/0/5 | 146.79% | 114.28% | 0.692 | -28.83% | 435.70 | 704,499 |
| Factor 2 | baseline/candidate 20/5/5 | 111.94% | 79.43% | 0.791 | -14.75% | 213.46 | 291,493 |
| Factor 3 | baseline 20/5/5 | 54.74% | 22.23% | 0.401 | -24.94% | 214.30 | 228,155 |
| Factor 3 | candidate 30/5/10 | 79.74% | 47.23% | 0.586 | -19.70% | 75.06 | 83,811 |
| Equal weight | baseline 20/5/5 | 91.31% | 58.80% | 0.671 | -19.07% | 208.52 | 267,617 |
| Equal weight | candidate 20/5/10 | 104.27% | 71.76% | 0.771 | -19.02% | 105.00 | 136,516 |

Factor 1 improves return, Sharpe and drawdown but more than doubles turnover
and cost. Factor 2 selects the baseline. Factor 3 and equal weight improve the
research metrics while materially reducing turnover.

## 9. Retrospective 2025 and 2026H1

These periods were already exposed in predecessor tasks. They are
`retrospective_report_only`, not sample-out, unseen or independent holdout.

| Signal | Config | 2025 net excess | 2026H1 net excess | 2025 Max DD | 2026H1 Max DD |
|---|---|---:|---:|---:|---:|
| Factor 1 | 20/0/5 | -23.85% | -15.98% | -8.36% | -13.55% |
| Factor 2 | 20/5/5 | -29.16% | -13.53% | -9.38% | -10.11% |
| Factor 3 | 30/5/10 | -23.45% | -11.53% | -6.66% | -10.50% |
| Equal weight | 20/5/10 | -18.48% | -8.91% | -6.10% | -5.86% |

All four candidates underperform CSI300 in both later periods. The locked
Fixed Universe Lifecycle Policy is explicit for 2026H1; it does not replace
delisted members, fill signals or change the Universe identity.

## 10. Parameter Sensitivity and Conclusions

| Signal | TopK sensitivity | n_drop sensitivity | Rebalance sensitivity | Stability |
|---|---:|---:|---:|---|
| Factor 1 | max neighbor loss 4.35 pp | 8.28 pp | 11.34 pp | parameter_unstable |
| Factor 2 | 2.52 pp | 4.75 pp | 8.81 pp | parameter_unstable |
| Factor 3 | 6.59 pp | 6.97 pp | 7.81 pp | parameter_unstable |
| Equal weight | 1.78 pp | 4.07 pp | 13.61 pp | parameter_unstable |

- Rebalance interval has the largest pooled effect. Mean full-period CSI300
  excess is 2.15% for daily, 59.75% for five sessions and 54.66% for ten.
- Higher turnover does not improve results in aggregate; daily execution has
  the highest mean turnover (850.81) and lowest mean excess.
- Factor 3 is least unstable by the frozen neighbor-loss measure (7.81 pp).
  Equal weight is most dependent on a particular rebalance interval (13.61
  pp), followed by Factor 1 (11.34 pp).
- Candidate improvements are not robustly continued: every later-period
  CSI300 excess is negative. None is eligible for automatic Strategy
  Validation or Promotion. They may only be inputs to the explicitly separate
  future risk/validation task.
- All strategies must remain research-only.

## 11. Artifact Store, Recovery and Replay

- Study: `sos_e504d537b1a28f87db183fa3bb99cd3dc20601a4df0e59b26b155e933fa10687`.
- Result: `sor_2c7803f0226f6988bc421bf7b02ff8b1e3c7c65912c629b33dffdcee0f4b8628`.
- Registry: `srr_58f3e4551f89e0dbc7cb80a5c2d59ad257746737e04b41fbd6f4c123e4023d13`.
- Inventory: `sai_a0dbf127c51db8bf71e0ab2e3922bdd0f64c4fa5f7d423ab9aca3c484c0cf5f5`.
- Inventory state: 270 artifacts, 2,468 blobs, healthy, Missing 0,
  Unreferenced 0.
- Cold Store materialization covers the Study, 96 Trials, 96 formal Strategy
  Results and four Candidate Locks.
- Exact replay: `exact_existing=true`, Qlib/Agent/Factor Optimization calls 0,
  new artifacts/blobs 0 and Promotion writes 0.

## 12. Files and Symbols Changed

Production additions are under `backend/services/engine/strategy_optimization`.
Artifact Store/Runtime gain four additive kinds. Strategy Result validation
admits only the explicit contaminated optimization evidence class, while the
Strategy Registry admits two research-only parameter states. The CLI is
`tools/quantmind2/strategy_optimization.py`; focused unit, Store and opt-in
real-Qlib tests are included. Contracts and Project Memory are updated.

Important symbols: `StrategyOptimizationSpec`, `PlannedStrategyTrial`,
`parse_optimization_spec`, `plan_trials`, `execute_study`, `segment_metrics`,
`rank_trials`, `parameter_sensitivity`, `publish_formal_strategy_result` and
`validate_strategy_optimization_artifact`.

## 13. API, Database, Configuration, Security and Lineage

- API/database/migration/runtime configuration: none.
- Project dependencies and lockfiles: unchanged. Tests used the existing
  offline cached Python/Qlib runtime; no project dependency was added.
- Secrets and network market-data calls: none.
- Data lineage is Tushare-only and content-addressed. Legacy authority raises
  `LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN`.
- No Agent or Frozen Test is accessible from this service.

## 14. Tests Executed

- Focused optimization, Store, Strategy Layer and Context tests: 37 passed.
- Opt-in real Qlib optimization graph: one passed; the opt-in variable was set
  and the test executed rather than skipping.
- Broad Artifact Runtime/Store, Dataset Snapshot, Legacy Provider, Tushare,
  Unified Signal, Strategy and Context regression: 131 passed.
- Manifest v2, Ledger Indexer and Context contract tests: 42 passed.
- Context Bootstrap: 42 repository checks passed.
- Exact replay, Store inventory/integrity, JSON, py_compile and Git checks are
  recorded in Manifest v2.

## 15. Known Limitations

- Research-period selection is retrospectively contaminated and cannot make a
  predictive claim.
- 2025 and 2026H1 were previously exposed and are report-only, not independent
  holdouts.
- All four candidates are parameter-unstable and fail to continue CSI300
  outperformance in both later periods.
- The sensitivity measure is a deterministic one-dimension neighbor test, not
  a causal parameter attribution model.
- Fixed-100 affected benchmark evidence remains noncanonical and is never an
  optimization target.
- No risk constraint, Strategy Validation, Fresh Forward Strategy Evaluation,
  approval or active strategy exists.

## 16. Compatibility, Rollback and Remaining Work

The change is additive and leaves Unified Signals, Factors, LightGBM, Qlib and
all predecessor artifacts immutable. Rollback is a single commit revert plus
ceasing to reference the new Store graph; Store evidence must not be deleted
or overwritten. No production migration is required.

## 17. Git / Workspace State

- One independent commit is required: `feat(qm2): add strategy parameter optimization`.
- No amend and no push.
- Post-commit Planner must be validated/indexable with zero evidence gaps and
  warnings; final worktree must be clean.

## 18. Recommended Next Task

Only `QM2-P0-018 — Strategy Risk and Validation Gate v1`.
