# Implementation Report — QM2-R1-002

## 1. Task Result

Completed. The previously requested PIT Fundamental task with the same ID was
cancelled before implementation. This task implemented and executed the
multi-family Momentum research contract without Tushare network access,
financial features, Strategy Optimization, Promotion or production changes.

## 2. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `5d6442c9ac6ad805c156ac41a8c3ad59755bd03e`
- Worktree: clean
- Unrelated dirty files: none
- No Tushare token was required or read.

## 3. Momentum Research Baseline

The research reused the immutable Tushare Fixed-100 normalized bars, labels,
CSI300 benchmark and Qlib view. Existing comparison binds the three original
weak Factors and the canonical QM2-R1-001 candidate, for four-factor signal
correlation evidence. No retired data source was read.

## 4. Momentum Feature Catalog

Catalog `mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c`
contains exactly 36 features. Dataset
`mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c`
contains 180,241 rows for 100 symbols from 2019-01-02 through 2026-06-23.

## 5. Feature Families

The Catalog covers nine families: absolute, skip-recent, relative, residual,
path-quality, risk-adjusted, acceleration, breakout and amount-confirmation
momentum. The canonical run admitted candidates from eight families; absolute
momentum was in the round-1 allowlist but the accepted proposal used
skip-recent momentum.

## 6. Feature Contracts

Every Feature binds formula, economic meaning, source columns, lookback,
minimum observations, lag, adjustment, missing-data, PIT, expected-direction
and allowed-operator semantics. Adjusted close is used for stock returns,
benchmark beta/state is lagged, amount is unadjusted, warm-up remains null and
no forward/back/zero fill occurs.

## 7. Feature Quality

All 36 features pass >=90% finite coverage on the real research interval;
Infinity and PIT violation counts are zero. The matrix is deterministically
sorted and has no duplicate symbol/date keys.

## 8. Feature Redundancy

Twelve feature pairs exceed absolute Spearman correlation 0.97. They are
reported with correlation and retention reason. Economically distinct fixed
horizons or normalization semantics remain separately named; Agent and final
correlation gates receive the redundancy evidence.

## 9. Family Diversity

The final revision explored eight distinct families and capped family
admission at three. An immutable first attempt stopped after three rounds with
only five families; it was not overwritten. Revision 2 supersedes it and
requires at least six explored families before no-novelty/no-improvement early
stop can fire.

## 10. Experiment Protocol

External Agent provider/model is `openai_codex_cli/gpt-5.6-terra`. Limits are
six rounds, two calls per round, four proposals, three admissions, eight Trials
per Template, 24 Trials per round, and global 12/18/144 call/template/Trial
caps. DSL limits are three Features, three parameters and depth seven. Qlib is
fixed at TopK20, n_drop5, five-session rebalance, equal weight, lag one, open
execution and CSI300. Strategy Optimization calls are zero.

## 11. Round 1

Theme: absolute and skip-recent momentum. One real Agent call produced one
proposal; one Template and three Trials were admitted. One candidate passed
standalone eligibility.

## 12. Round 2

Theme: relative and residual momentum. One call produced three proposals;
three Templates and ten Trials were admitted. No candidate passed all gates.

## 13. Round 3

Theme: path quality. One call produced four proposals; three Templates and
three Trials were admitted and one was rejected by admission control. No
candidate passed all gates.

## 14. Round 4

Theme: risk-adjusted momentum. One call produced three proposals; three
Templates and twelve Trials were admitted. This round brought explored-family
coverage above the six-family minimum. No candidate passed all gates.

## 15. Round 5

Theme: acceleration, breakout and amount confirmation. One call produced
three proposals; three Templates and nine Trials were admitted. No candidate
passed all gates.

## 16. Round 6

Not executed. After round 5, family diversity was satisfied and two
consecutive rounds had not improved the frozen ordering. The early-stop
contract forbids opening an additional round after that condition.

## 17. Early-stop Result

`two_consecutive_rounds_without_ranking_improvement`; five rounds, five real
Agent calls, 13 admitted Templates, 37 Factor Optimization Trials and 92 formal
Qlib calls. No repair call was required in the canonical revision.

## 18. Candidate Eligibility

One candidate passed the standalone data, RankIC, CSI300 excess, trading,
concentration, stability and four-factor-correlation gates. Final candidate
locking additionally requires at least two eligible families. Because only one
family qualified, final lock count is zero. No threshold was relaxed.

## 19. Parameter Stability

All 13 admitted candidates recorded four direct-neighbor checks. A neighbor is
stable only when RankIC direction agrees and CSI300 excess is within 15
percentage points of the selected Trial. Thirteen met the >=50% standalone
stability threshold; this did not override other eligibility gates.

## 20. Candidate Ordering

Ordering uses only 2019--2024 evidence: positive RankIC and excess Fold counts,
median/worst RankIC and excess, parameter stability, return excluding best ten
days, drawdown, turnover, four-factor correlation, AST depth and Instance ID.
2025/2026H1 fields cannot affect ordering.

## 21. Final Candidate Locks

Zero. The two-family final gate is intentionally stricter than standalone
Candidate eligibility. No `momentum_factor_candidate_lock` was published and
Registry entry count remains zero.

## 22. Four-fold Metrics

Every admitted candidate was evaluated using four independent selections:
2019--2020→2021, 2019--2021→2022, 2019--2022→2023 and 2019--2023→2024.
Evaluation-year evidence never selected its own parameters.

## 23. Regime Metrics

All candidates received trend (bull/bear/sideways), volatility
(low/normal/high) and breadth (broad/neutral/narrow) diagnostics. Regime inputs
and expanding quantile thresholds are lagged and past-only. They are diagnostic
only and unavailable to Agent/DSL as inputs.

## 24. 2025 Report

Not opened because no candidate locked. This is the required conditional
behavior; 2025 was not used for selection or Agent feedback.

## 25. 2026H1 Report

Not opened because no candidate locked. The period was not used for selection,
parameter changes or Agent feedback.

## 26. Momentum Ensembles

Not created. The contract requires at least two locked candidates before
building new equal-weight momentum or old/new 50/50 ensembles.

## 27. Existing-factor Comparison

The final Experiment records the common Qlib strategy contract, source
evidence for the old three-factor results, the canonical R1-001 Experiment and
Candidate Lock, old annual CSI300 results, and empty new lock/ensemble sections.
Fixed-100-relative metrics are explicitly unused.

## 28. Turnover and Costs

All four-Fold selected signals were formally executed in Qlib. Eligibility
requires median turnover <=40 and non-null formal transaction cost in all four
Folds. No simplified backtest result is treated as formal evidence.

## 29. Return Concentration

Eligibility requires median best-ten-days contribution <=35%. Return excluding
the best ten days participates in ordering. No unlocked candidate receives a
later-period concentration report.

## 30. Factor Correlation

Every candidate was compared by 2019--2024 Spearman signal correlation with
the original three Factors and the canonical R1-001 factor. All 13 were below
the standalone 0.85 maximum; correlation did not override failed predictive or
family-lock gates.

## 31. Agent Learning Assessment

The immutable assessment classifies the iteration as `overfitting`: there was
one standalone eligible result, but insufficient cross-family breadth for a
lock. Rounds did not continuously improve. Agent Memory contained only
aggregate prior-round feedback and excluded daily labels/IC, stock
contributions, 2025/2026H1 and Fixed-100-relative evidence.

## 32. Registry

Entry, promotion-candidate, approved and active counts are zero. The only
permitted lock status would have been `research_registered`; no Promotion or
production state transition occurred.

## 33. Artifact Store

The task added seven canonical revision-2 artifacts and 20 blobs, plus retained
seven artifacts/22 blobs from the immutable superseded first attempt. Final
Store state is 299 artifacts and 2,550 blobs, healthy, Missing 0 and
Unreferenced 0. Final inventory is
`sai_aef39654d03476d168fcceb9bf4cf2f467395a7d0d64706ba63ced4c022f7e5c`.

## 34. Cold Recovery

An empty cache recovered and domain-validated the Experiment, Catalog,
Dataset, five Round Results and Assessment: nine artifacts total. Local work
directories are disposable and not authoritative.

## 35. Exact Replay

Experiment `mfi1_87177b7c06420e65159d3f5bdafee8149cdb3290c32f08712cd73e59a4e19dee`
replays exactly with Agent 0, Optimization 0, Qlib 0, network 0, new artifacts
0, new blobs 0, Promotion 0 and healthy Store integrity.

## 36. Files Added

- `backend/services/engine/momentum_factor_iteration/` domain package.
- `backend/services/tests/test_momentum_factor_iteration.py` and real Store
  test module.
- `tools/quantmind2/run_momentum_factor_iteration.py`.
- `docs/quantmind2/contracts/MOMENTUM_FACTOR_ITERATION_V1.md`.
- This Implementation Report and Manifest v2.

## 37. Files Modified

Artifact kind/validator/cache routing and Project Memory Current State,
Handoff, Component Catalog, Roadmap and Known Issues were updated. No data
provider, training, inference, Registry business, Strategy, Qlib, model, API,
database, UI, dependency or lockfile was changed.

## 38. Tests Executed

- Momentum unit tests: 16 passed.
- Real Momentum Store tests: 5 passed.
- Combined Momentum/expanded-factor/Store/runtime targeted regression:
  46 passed, 5 skipped; six unrelated legacy Artifact Runtime real tests fail
  because the post-Tushare-purge Store no longer contains their hard-coded
  pre-cutover artifact IDs. This baseline failure is not changed or hidden.
- Full passing relevant set excluding those known obsolete-ID real cases:
  86 passed and 5 skipped.
- Context Bootstrap: 42 checks passed. Context/Manifest tests: 40 passed.
- All ten CLI commands passed, including catalog/feature construction, plan,
  zero-call execute/replay, validation and every inspection route.
- Manifest v2 validation, JSON parse, `py_compile`, Git diff scope and
  post-commit Planner are recorded separately at final verification.

## 39. Expected vs Actual

- Expected at most 6 rounds; actual 5 due frozen early stop.
- Expected at least 8 Catalog families; actual 9.
- Expected <=36 features; actual 36, all quality-passed.
- Expected <=12 calls/18 Templates/144 Trials; canonical actual 5/13/37.
- Expected conditional locks/reports/ensembles; actual zero because the
  two-family final gate did not pass.
- Expected no network/Strategy search/Promotion; actual all zero.

## 40. Implementation Run

Run `QM2-R1-002-20260721T144440Z-5d6442c` uses Manifest v2, is committed in a
single independent commit, and is subject to the post-commit Planner gate.

## 41. Project Memory Updates

Current State, Handoff, Component Catalog, Roadmap and Known Issues now record
the canonical revision, exact outcome, zero-lock conclusion and protected
research boundaries. The cancelled financial task is not described as
implemented.

## 42. Known Limitations

- This is retrospective adaptive research, not Fresh Validation or a
  predictive claim.
- No cross-family final lock exists; current daily Momentum features are
  insufficient under frozen gates.
- Formal Qlib emits existing optional COS/model-registry warnings (`/data`
  read-only and missing `asyncpg`) while supplied-signal execution completes.
- Round artifacts persist bounded aggregate Candidate feedback; full detailed
  Fold/neighborhood records exist only for a Candidate Lock, and no lock was
  produced in this run.
- Store/runtime are local single-host components with no API/UI/distribution.

## 43. Final Research Conclusion

当前 Fixed-100 日频动量空间仍未找到足够稳定的 Alpha。The system did not
weaken gates, add a seventh round, use later-period evidence, or promote a
result to change that conclusion.

## 44. Git State After

The task uses one commit with message
`feat(qm2): run momentum factor family iteration`. No amend or push is
performed. Final worktree and post-commit Planner state are filled by actual
verification, not assumption.
