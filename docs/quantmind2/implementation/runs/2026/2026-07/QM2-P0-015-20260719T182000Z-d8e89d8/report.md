# QM2-P0-015 Implementation Report

## 1. Task Summary

`partial`. Four external-Agent historical-as-of rounds completed on the
Tushare fixed-100 authority, with immutable candidate locks, bounded parameter
search, next-year evaluation, formal Qlib backtests, pre-holdout selection,
2025 holdout, Artifact Store publication, cold recovery and exact replay.
Isolated 2026H1 signals passed the requested NaN gate at 0%, but formal Qlib
rejected all four strategies because only 98 of the 100 immutable symbols had
effective observations. The universe and Qlib gate were not changed.

## 2. Goal and Scope

- Use only Store-backed `tushare-pro-v1` artifacts and the exact immutable
  fixed-100 lock.
- Execute four fixed Agent rounds with field-level as-of memory isolation.
- Optimize only declared factor windows/internal weights on each research
  period and lock candidates before next-year evaluation.
- Use existing `QlibBacktestService`, `RedisRecordingStrategy`,
  `SimulatorExecutor` and `CnExchange` with TopK 20, `n_drop=5` and weekly
  rebalancing.
- Lock final candidates using only evidence through 2024, then open 2025 and
  2026H1 once without Agent feedback or reselection.
- Publish only `research_registered` experiment entries; perform no promotion.

## 3. Explicit Non-goals

No Tushare download or token use, legacy-data fallback, universe replacement,
Feature/Label change, portfolio optimization, LightGBM work, Fresh Validation
claim, automatic promotion, database migration, API/UI, dependency change,
lockfile change or push.

## 4. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `d8e89d8dac2d5cf1cb43ad2334d89ec10f77dbfa`.
- Worktree: clean; unrelated dirty files: none.
- Store baseline: 17 artifacts / 1,527 blobs, healthy, zero missing and zero
  unreferenced.
- Formal Factor Lab source remained read-only.

## 5. What Changed

- Added a Tushare-authoritative retrospective experiment runtime with fixed
  protocol, Store-only data resolution, historical-as-of memory, DSL compute,
  bounded Trial selection, formal Qlib evaluation, candidate lock, holdout,
  assessment, Registry, cold recovery and exact replay.
- Added seven immutable Tushare experiment Artifact kinds and formal Domain
  validation routing.
- Added a CLI that deliberately has no token option or token environment read.
- Added focused tests for authority, memory isolation, DSL causality, compiled
  public fields, equal weighting, Artifact rules and Qlib rejection evidence.
- Added deterministic recovery from four already-published round locks. This
  was needed after a downstream Qlib precheck interrupted final aggregation;
  recovery performs zero Agent calls and does not repeat parameter search.
- Changed Qlib quality failure handling from whole-experiment termination to a
  structured `rejected` result with null performance metrics. It does not
  alter the quality gate or fabricate missing performance.

## 6. Runtime and Authority Evidence

The runtime materialized the universe, Feature, Label, normalized bars,
benchmark, Qlib view, empty Genesis Registry and sanitized Memory only through
the Artifact Store. It recorded `legacy_reads=0` and
`tushare_network_calls=0`. Fixed-100 identity, ranks 1..100 and parent lock
were verified. Feature calculation is continuous across years and uses only
the four Tushare contract fields.

The first immutable diagnostic protocol made four valid Agent calls but
rejected all proposals after the runtime incorrectly referenced nonexistent
`CompiledFactor.factor_template_id`. That diagnostic remains immutable and is
not research evidence. The corrected formal protocol uses the public
`CompiledFactor.template_id`. Its four rounds used four further calls, so the
task-wide total is exactly eight and was not expanded.

## 7. Four-round Agent Iteration

| Round | Research | Evaluation | Proposed | Admitted | Trials | Mean RankIC | Net excess fixed-100 | Max drawdown |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2019--2020 | 2021 | 3 | 2 | 4 | -0.00213 | -4.41% | -18.28% |
| 2 | 2019--2021 | 2022 | 3 | 2 | 6 | 0.00358 | 3.41% | -14.97% |
| 3 | 2019--2022 | 2023 | 3 | 2 | 2 | 0.00191 | 0.93% | -18.86% |
| 4 | 2019--2023 | 2024 | 2 | 2 | 6 | 0.00331 | 15.99% | -12.00% |

Round 2 improved on Round 1, Round 3 regressed, and Round 4 recovered. The
Agent consumed only aggregate published feedback, but rounds 2--4 were not
strictly or continuously better than Round 1. The formal assessment is
`mixed`.

## 8. Final Candidate Lock and Annual RankIC

Selection used only 2021--2024 evidence and locked three candidates before
opening either holdout.

| Factor | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026H1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| liquidity-normalized momentum | -0.00218 | 0.01230 | 0.00033 | -0.00069 | 0.00553 | 0.01752 | -0.00107 | -0.00396 |
| liquidity-persistence beta penalty | 0.00205 | 0.01401 | -0.00966 | 0.00522 | 0.01112 | -0.00365 | 0.00024 | 0.00118 |
| peak-volatility-adjusted momentum | 0.01388 | -0.00384 | 0.00456 | 0.00194 | 0.00475 | -0.00481 | -0.00114 | -0.00218 |

The liquidity-persistence factor has the most positive RankIC years (six of
eight), while liquidity-normalized momentum ranked first under the frozen
pre-holdout selection rule. Their full-history Spearman factor correlation is
0.0127; correlations with peak-volatility-adjusted momentum are 0.4639 and
-0.4156.

## 9. Annual Net Returns

| Strategy | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026H1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| equal-weight combination | 23.15% | 2.66% | 5.64% | -2.78% | 12.86% | 38.93% | 4.23% | rejected |
| liquidity-normalized momentum | 31.46% | 22.74% | 12.66% | -11.32% | -9.31% | 35.35% | 1.62% | rejected |
| liquidity-persistence beta penalty | 24.13% | 1.72% | 13.22% | -3.17% | 13.08% | 33.32% | -7.41% | rejected |
| peak-volatility-adjusted momentum | 7.04% | 2.32% | 3.01% | -7.11% | 15.77% | 22.53% | -4.32% | rejected |

In 2025 the combination remained positive but underperformed CSI300 by 17.52
percentage points and fixed-100 by 2.85 points. It therefore did not preserve
benchmark-relative holdout performance.

## 10. Long-range Risk and Return

| Strategy | Net return | Annual return | Excess CSI300 | Excess fixed-100 | Sharpe | Max drawdown | Calmar | Turnover | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| equal-weight combination | 82.45% | 8.73% | 16.79% | 2.22% | 0.474 | -19.07% | 0.458 | 259.87 | 354,796 |
| liquidity-normalized momentum | 91.90% | 9.50% | 26.24% | 11.67% | 0.362 | -33.75% | 0.281 | 254.98 | 388,439 |
| liquidity-persistence beta penalty | 72.47% | 7.88% | 6.80% | -7.77% | 0.406 | -21.06% | 0.374 | 264.80 | 379,644 |
| peak-volatility-adjusted momentum | 25.86% | 3.25% | -39.80% | -54.37% | 0.088 | -24.94% | 0.130 | 266.19 | 292,641 |

These are available-range 2019--2026H1 runs whose aggregate precheck passed;
they do not replace the rejected isolated 2026H1 result. The combination did
not beat the best single Factor's total return, but materially improved its
drawdown and Calmar ratio.

## 11. Robustness and Concentration

The frozen weekly TopK-20 combination remained positive under 2x costs but
lost fixed-100 excess. Daily variants were materially worse; TopK-10/daily was
negative even at 1x cost. TopK-30/weekly had the best diagnostic result, but it
was not used to change the frozen strategy.

For the combination, the best ten days contributed 44.28 percentage points;
removing them leaves an 18.41% return. The best annual return was 2024 at
38.93%, and the worst was 2022 at -2.78%. Monthly win rate was 55.56%; the
worst month was 2020-02 at -6.50%. Formal Qlib output exposes positions but no
per-stock realized PnL attribution, so `top_10_stocks_contribution/share` is
not claimed and remains a known evidence gap.

## 12. 2026H1 Boundary

All three Factors and their equal-weight combination have 0% signal NaN from
2026-01-05 through 2026-06-23. Existing Qlib nevertheless rejects this
isolated interval at `valid symbols insufficient (98 < 100)`. Two immutable
universe members lack effective interval observations. The implementation
records `FORMAL_QLIB_SIGNAL_QUALITY_REJECTED` with null returns; it does not
drop, replace, fill or lower the 100-symbol gate. Consequently 2026H1 return,
excess and risk continuation are unknown.

## 13. Research Conclusions

1. Rounds 2--4 did not continuously improve; classification is `mixed`.
2. Aggregate feedback influenced later structures, but the metric path is not
   monotonic evidence of reliable failure absorption.
3. Liquidity-persistence beta penalty is most stable by positive RankIC-year
   count; liquidity-normalized momentum is the frozen selection leader.
4. Peak-volatility-adjusted momentum should stop under this protocol because
   it has the weakest long-range benchmark-relative result and negative 2025
   and 2026H1 RankIC.
5. 2025 did not retain benchmark-relative alpha for the combination.
6. 2026H1 portfolio continuation is unknown because formal Qlib rejected the
   interval; Factor RankIC is negative for two candidates and weakly positive
   for one.
7. Equal weighting improved return/drawdown ratio, not total return.
8. Available-range combination net excess is positive versus CSI300 and
   fixed-100, but 2025 excess is negative versus both.
9. Returns are meaningfully concentrated in the best ten days and 2024, yet
   remain positive after removing the best ten days.
10. Three candidates qualify only as retrospective `research_registered`
    evidence. The failed 2025 benchmark test and unavailable isolated 2026H1
    Qlib result do not support promotion or a Fresh Validation claim.

## 14. Artifacts, Store and Replay

- Final experiment: `tha_2b3676218af9693cf6bfcf0ab47d102db0cc865f94f0e5b54de6fba26d76383b`.
- Protocol: `thp_3cc5e05d01e96b90bfcd1bea8a0edcee215cb792b2317c359098af871fcf2160`.
- Execution: 4 formal Agent calls, 18 Trials, 34 uncached formal Qlib attempts,
  zero production/promotion writes. Task-wide Agent calls including the
  immutable diagnostic: 8.
- Final Store: 43 artifacts / 1,580 blobs, healthy, Missing 0, Unreferenced 0.
- Thirteen protocol artifacts cold-restored and Domain-validated.
- Exact replay: `exact_existing=true`; Agent, Optimization, Qlib, Registry,
  Tushare network, legacy reads, new artifacts and new blobs all zero.

## 15. API, Database, Configuration, Dependencies and Security

No API, database schema/migration, running service configuration, dependency
file or lockfile changed. No dependency was installed. The CLI accepts no
token, and neither source nor generated implementation evidence contains a
Tushare credential. No production Registry state was written.

## 16. Tests Executed

- Focused experiment tests: 13 passed with `--no-cov`.
- Context, Tushare experiment/cutover, Codex-Agent, parameter-contract and
  Artifact Store import/integrity regression: 71 passed.
- Real formal run: completed through 2025; isolated 2026H1 Qlib rejected as
  recorded above.
- Store cold recovery/integrity and exact replay: passed.
- Python compilation and `git diff --check`: passed.
- Context bootstrap, JSON parsing, secret scan and post-commit Planner are
  recorded in the final Manifest after execution.

## 17. Known Limitations and Remaining Work

- No isolated formal 2026H1 portfolio metrics or per-stock contribution
  attribution exist.
- Qlib's fixed-100 expected-symbol contract and an immutable member with no
  effective interval observations need a separately authorized architecture
  decision; the current task deliberately leaves both unchanged.
- Qlib model-resolution attempted local PostgreSQL and logged a connection
  warning before using the explicitly supplied signal. Market data, strategy,
  executor and exchange remained the formal local Qlib chain.
- The Store is single-host filesystem infrastructure.
- No next task is authorized by this task contract.

## 18. Compatibility, Rollback and Git State

New Artifact kinds are additive. Existing QuantMind LightGBM, Qlib strategy,
executor, exchange and risk code are unchanged. Rollback is deletion of this
task's code/context commit; immutable Store artifacts remain historical
evidence and must not be overwritten. The task uses one commit, no amend and
no push. Suggested commit: `feat(qm2): rerun agent experiment on tushare`.
