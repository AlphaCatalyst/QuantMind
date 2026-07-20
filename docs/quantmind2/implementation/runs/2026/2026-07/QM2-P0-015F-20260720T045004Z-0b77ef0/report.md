# QM2-P0-015F Implementation Report

## 1. Task Summary

`completed`. The fixed-100 identity remains unchanged, two 2026H1 absences
were proven to be pre-period delistings, explicit lifecycle semantics replaced
the incorrect assumption that all 100 locked members must be observable in
every interval, 2019--2025 parity passed, and all four frozen 2026H1 strategies
completed through the formal Qlib chain.

## 2. Goal and Scope

- Distinguish locked, active, observable, tradable and signal-eligible sets.
- Preserve the original 100-member lock, three candidate signals, equal-weight
  combination, TopK 20, n_drop 5, weekly rebalance and CnExchange costs.
- Audit the exact absent members from immutable Tushare authority artifacts.
- Recover the isolated 2026H1 formal Qlib results without replacement or fill.
- Publish immutable lifecycle, parity, backtest and Store replay evidence.

## 3. Explicit Non-goals

No Agent call, Optimization, candidate reselection, parameter or orientation
change, universe replacement, market/signal fill, Tushare network call,
Feature/Label rebuild, portfolio optimization, Fresh Validation, Promotion,
LightGBM, API, database migration, UI, dependency/lockfile change or push.

## 4. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `0b77ef01166d27d7e30b9aa95b97c2bae311df78`.
- Worktree: clean; unrelated dirty files: none.
- Original experiment: `tha_2b367621...76383b`.
- Store: 43 artifacts / 1,580 blobs, healthy.
- Factor Lab remained read-only; its formal `/tmp` tree currently retains only
  compiled residue, consistent with the pre-existing source-retention issue.

## 5. Lifecycle Reality Audit

| symbol | ts_code | status | list date | delist date | last market/daily | last adj factor | last daily basic | reason |
|---|---|---|---|---|---|---|---|---|
| SH600837 | 600837.SH | D | 1994-02-24 | 2025-03-04 | 2025-02-05 | 2025-03-03 | 2025-02-05 | DELISTED_BEFORE_PERIOD |
| SH601989 | 601989.SH | D | 2009-12-16 | 2025-09-05 | 2025-08-12 | 2025-09-05 | 2025-08-12 | DELISTED_BEFORE_PERIOD |

Both symbols remain in the lock and Qlib instrument file. Their Qlib
observable intervals end on 2025-02-05 and 2025-08-12 respectively. The
absence is not Tushare source loss, symbol mapping error or Qlib omission.

## 6. What Changed and Why

- Added `FixedUniverseLifecyclePolicyV1`, lifecycle audit and daily membership
  accounting. The policy freezes capacity at `topk + n_drop = 25` before
  observing 2026H1 results.
- Added three explicit request metadata fields used only by the signal-quality
  layer. Ordinary Qlib requests retain the existing environment/default gate;
  only a complete lifecycle contract may use its pre-frozen capacity gate.
- Prevented lifecycle metadata from leaking into Qlib `BaseStrategy` kwargs.
- Changed fixed-100 benchmark construction so missing constituent observations
  are excluded from the daily equal-weight denominator instead of filled with
  zero. The prior 2019--2025 outputs remain numerically identical.
- Added a Store-only follow-up runtime, CLI, formal artifact kind/validator,
  cold recovery, exact replay and focused tests.
- Updated Project Memory to distinguish the immutable partial P0-015 evidence
  from this separate retrospective follow-up.

## 7. Formal Lifecycle Contract

Policy ID: `fulp_60672b83992c16796af70683eafa9607a8d7ab3cc4cc6438059f8f25100a632a`.

Relations are `tradable ⊆ observable ⊆ active ⊆ locked` and
`signal-eligible ⊆ observable`. Locked count is always 100. During 2026H1,
active count is 98, observable and tradable counts range from 96 to 98, and
the maximum observable-denominator signal NaN ratio is 0% for every strategy.
The two delisted members are structurally inactive, not signal NaNs.

Existing Qlib/CnExchange does not invent a forced liquidation price. A
non-observable or suspended member cannot receive a new trade; an existing
position remains subject to Qlib availability, valuation and exchange rules.
The formal 2026H1 run begins after both delistings and therefore opens with no
such positions. A general forced-exit policy for a delisting during an active
backtest remains explicitly unresolved rather than fabricated here.

## 8. 2019--2025 Parity

All 28 combinations of four locked signal paths and seven annual periods were
executed through `QlibBacktestService → RedisRecordingStrategy →
SimulatorExecutor → CnExchange`. Signal bytes are unchanged. Position rows
match after deterministic `(date, symbol, side)` ordering, with numeric
tolerance `1e-12`; the only raw-list differences were floating serialization
at about `1e-17` and nondeterministic row order. Gross/net return, both
benchmarks, both net excess measures, turnover, cost and maximum drawdown all
match within `1e-12`. Parity status is `passed`.

## 9. 2026H1 Formal Qlib Results

Period: 2026-01-05 through 2026-06-23. CSI300 return is +4.27%; lifecycle-aware
fixed-100 return is -12.05%. Signal NaN is 0% on observable cells for all rows.

| Strategy | Gross | Net | Excess CSI300 | Excess fixed-100 | Sharpe | Max DD | Calmar | Turnover | Cost | Monthly win |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| equal-weight combination | -4.56% | -5.84% | -10.11% | +6.22% | -1.143 | -6.98% | -1.829 | 16.93 | 12,729.09 | 16.67% |
| liquidity-normalized momentum (`fi_d877...`) | -11.09% | -12.24% | -16.52% | -0.19% | -1.811 | -16.53% | -1.553 | 16.41 | 11,513.90 | 16.67% |
| liquidity-persistence beta penalty (`fi_e0fb...`) | -8.02% | -9.25% | -13.53% | +2.80% | -1.641 | -10.11% | -1.958 | 16.92 | 12,299.15 | 33.33% |
| peak-volatility-adjusted momentum (`fi_8f55...`) | -7.89% | -9.19% | -13.46% | +2.87% | -1.508 | -12.91% | -1.521 | 17.37 | 12,934.95 | 33.33% |

These are retrospective historical results. They do not constitute Fresh
Validation, candidate approval, activation or production promotion evidence.

## 10. Artifact Store and Replay

- Canonical follow-up revision 2:
  `thf_9f38986394640cab4ca7362ed0f876e02e408fe65c5b941a4c3667c4cd7307b2`.
- Files: lifecycle policy, exact symbol audit, daily member counts Parquet,
  Qlib instrument contract, parity result, 2026H1 backtest and Manifest.
- Revision 2 explicitly supersedes immutable preliminary artifact
  `thf_39155cdb...d498d6`, which omitted per-strategy Calmar and lifecycle
  summaries. No artifact was overwritten.
- Formal revision-2 execution: 32 Qlib calls (28 parity + 4 2026H1), zero Agent,
  Optimization, Tushare-network, legacy-data, reselection or Promotion calls.
- Final inventory `sai_ee866a1b3bed309d8437a41b78508000bb74749874858fa13477a3fad63b78e6`:
  45 artifacts / 1,589 blobs, healthy, Missing 0, Unreferenced 0.
- Cold materialization passed. Exact replay made 0 Qlib calls and created
  0 artifacts / 0 blobs.

## 11. Files Changed

Production changes are limited to the lifecycle follow-up package, explicit
Qlib request/gate metadata, benchmark denominator, artifact kind/validation,
and formal runner plumbing. Tests, one CLI, Project Memory and this immutable
Implementation Run were added or updated. No data, signal, candidate,
parameter, Qlib binary, dependency, lockfile, database or runtime configuration
was changed.

## 12. API, Database, Configuration and Security

- API changes: none.
- Database changes/migrations: none.
- Configuration/environment changes: none.
- Dependencies/lockfiles: unchanged.
- Security: no credential was read or persisted; no Tushare network call was
  made. Store inputs were hash-verified before use.

## 13. Tests Executed

- Focused lifecycle, Tushare experiment/cutover, Artifact Store and historical
  experiment tests: passed.
- Context Bootstrap and machine-readable JSON parsing: passed.
- Manifest v1/v2 and Project Knowledge focused tests: passed after updating the
  current-task assertion.
- Formal Qlib: 28 parity and four 2026H1 calls passed.
- Cold recovery and exact replay: passed; replay calls/creates are zero.
- `py_compile`, `git diff --check` and JSON parsing: passed.
- The unrelated pre-existing `test_engine_qlib_backend` module has three
  failures because it still expects removed public helpers
  `backtest_service.importlib/_resolve_qlib_backend`; this task did not alter
  that interface or weaken those tests.

## 14. Known Limitations

- Tushare authority ends at 2026-06-23; incremental collection and revision
  policy remain unimplemented.
- A general forced-exit/valuation contract for a member delisted while held is
  not defined by existing QuantMind/Qlib code and was not invented here.
- The official Factor Lab `/tmp` source retention problem remains; the current
  path contains only compiled residue.
- Formal Qlib attempts a production database model lookup before honoring the
  explicit signal path; the isolated run logs connection failures but safely
  consumes the formal signal and completes. No database was used.
- Preliminary follow-up remains in Store as immutable superseded evidence.

## 15. Compatibility, Rollback and Remaining Work

Ordinary Qlib requests retain their prior signal-quality gate. Rollback is one
commit revert plus ceasing to reference the new follow-up artifact; immutable
Store artifacts and the original P0-015 evidence must not be deleted or
rewritten. No next task is authorized by this task.

## 16. Git / Workspace State

- One independent commit is required: `fix(qm2): support lifecycle-aware fixed universe`.
- No amend and no push.
- Post-commit Planner must be validated, indexable, with zero evidence gaps
  and warnings.

## 17. Artifact Index

- Lifecycle policy: `fulp_60672b83...a632a`.
- Canonical follow-up: `thf_9f389863...7307b2`.
- Superseded preliminary follow-up: `thf_39155cdb...d498d6`.
- Store Inventory: `sai_ee866a1b...78e6`.
- Original experiment (unchanged): `tha_2b367621...76383b`.
