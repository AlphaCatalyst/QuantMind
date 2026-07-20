# QM2-P0-016 Implementation Report

## 1. Task Summary

`completed_uncommitted`. Unified Signal and Strategy Layer v1 now converts
locked Tushare Factor values into immutable signals, fixed portfolio targets
and Store-lineaged formal Qlib strategy results without Agent, Optimization,
model or Promotion activity.

## 2. Goal and Scope

- Add strict `FactorSignalInput`, `UnifiedSignalSpec`, `StrategySpec` and
  `StrategyExecutionPlan` contracts.
- Implement orientation-aware cross-sectional transforms, fixed/equal
  combination and require-all missingness.
- Build deterministic TopK Dropout desired targets under the fixed strategy.
- Import existing formal Qlib evidence only through verified Artifact Store
  lineage and separate targets from actual positions/trades.
- Publish four new artifact kinds, cold recover, exact replay and register only
  research-diagnostic completed backtests.

## 3. Explicit Non-goals

No Agent calls, Factor or Strategy parameter search, combination-weight
learning, LightGBM, risk model, simplified backtester, live trading, Fresh
Validation, Promotion, approved/active strategy, database/API/UI, dependency,
lockfile, configuration, amend or push.

## 4. Preflight State

- Repository: QuantMind main repository; branch `master`.
- Base commit: `33703db03949f9b0fa676faa6bb08bdd3901461d`.
- Worktree: clean; unrelated dirty files: none.
- Active data authority: `tushare-pro-v1`.
- Formal source Qlib artifact:
  `tqb_ea39d0378a835a3b609dacef769e4bf47708be004c703243d44375c95075d768`.
- Factor Lab remained read-only.

## 5. What Changed and Why

- `unified_signal` adds strict parsing, deterministic identity, four frozen
  transformations, three fixed combination modes, require-all missingness,
  quality evidence and atomic immutable artifacts.
- `values_are_oriented` records a source semantic discovered in the real
  Tushare round-lock artifacts: their stored values already contain the locked
  direction. This prevents double orientation while retaining the formal
  orientation in lineage.
- `strategy_layer` adds strict fixed-V1 strategy admission, execution plans,
  deterministic desired targets, existing-Qlib score adaptation, result and
  benchmark canonicality, and a research-only Registry.
- Artifact Store and Runtime now know the four new kinds and can resolve the
  two historical Store source kinds needed by this layer.
- Two CLIs expose validate/build/inspect and plan/target/backtest/result flows;
  their only runtime mode is `store_required`.

## 6. Runtime Flow

```text
verified Tushare round locks
→ FactorSignalInput
→ orientation/source-orientation gate
→ cross-sectional transform
→ fixed/equal combination
→ UnifiedSignalArtifact
→ fixed StrategySpec and ExecutionPlan
→ deterministic PortfolioTargetArtifact
→ verified historical formal-Qlib result
→ StrategyBacktestResult
→ StrategyResearchRegistry
```

The formal Qlib result retains the existing chain:
`QlibBacktestService → RedisRecordingStrategy → SimulatorExecutor →
CnExchange`. No simplified execution path was added.

## 7. Real Signal Evidence

The three selected Factors remain research diagnostics. Four Unified Signals
were produced. The final equal-weight signal is
`usa_4c824a58d0a17cb0aebea30bbc2197ae8246843b2aaae14a49fc1c091789fab0`.
Against the historical reference over 2019-01-02..2026-06-23:

- rows: 180,241;
- finite cells: 180,231;
- NaN pattern equal: true;
- maximum absolute difference: 0;
- exact finite-cell equality: true.

## 8. Strategy and Portfolio Targets

The fixed contract is TopK 20, n_drop 5, five-session weekly rebalance, equal
target weights, open execution, one-session lag and CSI300. Lifecycle admission
prevents inactive or non-tradable names from receiving new target weight.

The Portfolio Target is desired intent, not an executed position. The source
Qlib results contain actual positions and NAV but no formal pre-trade target
weights, orders or trades. Target-to-actual-target equality is therefore
`not_verifiable_from_source_qlib_result`; no position was relabeled as a target.

## 9. Historical Diagnostic Results

| Signal | Result ID | Net return | Annualized | Sharpe | Max drawdown | CSI300 excess |
|---|---|---:|---:|---:|---:|---:|
| `fi_d877…` | `sbr_6c31a5f8…4e189` | 91.90% | 9.50% | 0.362 | -33.75% | 26.24% |
| `fi_e0fb…` | `sbr_2f708e69…0b5f6` | 72.47% | 7.88% | 0.406 | -21.06% | 6.80% |
| `fi_8f557…` | `sbr_1a3f3d43…bbf93` | 25.86% | 3.25% | 0.088 | -24.94% | -39.80% |
| equal weight | `sbr_75d24a99…d7e1ee` | 82.45% | 8.73% | 0.474 | -19.07% | 16.79% |

The combination has the lowest drawdown and highest Sharpe, but does not beat
the best single Factor's total return or CSI300 excess. No result changed a
strategy parameter.

## 10. Canonicality and Registry

Absolute and CSI300-relative strategy evidence is canonical because the prior
termination audit proves all strategies were flat before the relevant events.
Fixed-100 2025/full-period benchmark and excess remain noncanonical and
unusable for decisions. All inputs remain `research_diagnostic`; all results
are usable for research only, not parameter optimization or Promotion.

Registry `srr_a2d226d4ca751100256a3d6332ed5576c29c40c53a3a78a634fbdffef74ea503`
contains four `backtest_completed`, zero approved and zero active entries.

## 11. Artifact Store, Cold Recovery and Replay

- Current Store Inventory:
  `sai_bc858a8dada523a3dda9f3d0cae14ae49b6f7b79023cdf0ff16a876eae72da78`.
- Inventory at verification: 71 artifacts / 1,679 unique blobs.
- Integrity: healthy; Missing 0; Unreferenced 0.
- Final current graph: four signals, four targets, four results and one
  Registry; all 13 cold-materialized and then warm-resolved successfully.
- Exact replay: all 13 were exact existing, new blobs 0, Qlib calls 0, Agent
  calls 0, Optimization trials 0 and Promotion writes 0.

Earlier same-task superseded development artifacts remain immutable Store
records; the final Registry references only the IDs listed in this report.

## 12. Files Changed

Production changes are limited to new `unified_signal` and `strategy_layer`
packages plus additive Artifact Store/Runtime kind validation. Two CLIs, three
focused tests, two contracts, Project Memory and this Run are included. No
existing Qlib, training, inference, Factor, Dataset, termination, corporate
action, dependency, lockfile, database, API or configuration behavior changed.

## 13. API, Database, Configuration and Security

- External API: none.
- Database/migrations: none.
- Runtime configuration: unchanged.
- Dependencies/lockfiles: unchanged.
- Secrets: none read or stored.
- Data authority gate rejects non-Tushare lineage with
  `LEGACY_MARKET_DATA_AUTHORITY_FORBIDDEN`.

## 14. Tests Executed

- Focused signal/strategy plus opt-in real Store/Qlib-lineage test: 12 passed.
- Relevant Artifact Store/Runtime, Tushare experiment/lifecycle, termination,
  Manifest/Indexer and Context regression: recorded in the final Manifest.
- Real signal parity, 13-artifact cold recovery and exact replay: passed.
- `py_compile`, all QuantMind 2.0 JSON parsing, Context Bootstrap and
  `git diff --check`: recorded in the final Manifest.

No dependency was installed and no external service, database, Agent,
Optimizer or Qlib execution was invoked by the replay.

## 15. Known Limitations

- Formal source results do not expose pre-trade target weights, so target to
  actual-target equality cannot be proven from existing evidence.
- Orders and trades are empty in the reused source result; actual positions and
  NAV are retained and are not reconstructed.
- Fixed-100 affected comparison remains noncanonical pending governed
  settlement evidence.
- Strategy Parameter Optimization, LightGBM, risk model, API/UI and production
  admission are not implemented here.
- Tushare authority remains locked through 2026-06-23.

## 16. Compatibility, Rollback and Remaining Work

The change is additive and preserves existing LightGBM, Qlib and Tushare
artifacts. Rollback is one commit revert plus ceasing to reference the new
Store descriptors; immutable evidence must not be overwritten. No current
strategy is production-ready.

## 17. Git / Workspace State

- One independent commit: `feat(qm2): add unified signal and strategy layer`.
- No amend and no push.
- Post-commit Planner must be validated and indexable with zero evidence gaps
  and warnings.

## 18. Artifact Index

- Equal signal: `usa_4c824a58...9fab0`.
- Result IDs: `sbr_6c31a5f8...4e189`, `sbr_2f708e69...0b5f6`,
  `sbr_1a3f3d43...bbf93`, `sbr_75d24a99...d7e1ee`.
- Registry: `srr_a2d226d4...ea503`.
- Inventory: `sai_bc858a8d...72da78`.

## 19. Recommended Next Task

Only `QM2-P0-017 — Strategy Parameter Optimization v1` may follow. It may
search TopK, n_drop and rebalance frequency only after explicit authorization.
