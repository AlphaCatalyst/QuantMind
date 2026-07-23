# QM2-R2-003 Implementation Report

## 1. Task summary

Task `QM2-R2-003 — Autonomous Multi-Campaign Research Program and Global
Search Control v1` implemented a three-Lane autonomous Program, ran formal
`technical_factor_program_001`, and reached the governed zero-survivor
terminal state.

## 2. Goal and scope

The change adds immutable Program/Lane models, evidence partitions, clean-room
seed, global novelty and search exposure, adaptive early-stop controls, Lane
and Union Shortlist Locks, 2021–2024 locked validation, Newey–West/HAC and
Benjamini–Hochberg control, survivor-only Registry/Fresh boundaries, CLI
routing, Artifact kinds, tests, contract and Project Memory.

## 3. Explicit non-goals

No new terminal feature, structure evolution, Strategy or Combined
Optimization, market-data fetch, Tushare call, Fresh evaluation, Promotion,
LightGBM/Qlib replacement, database/API/UI/dependency/lockfile change,
historical Candidate mutation or second Program was performed.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `80c0527f83b2eaab7ad007bbb049f2e1f16ccd2d`
- Worktree: clean
- Unrelated dirty files: none
- Official Factor Lab remained read-only and was not modified.

## 5. R2-002 audit and Program architecture

Campaign 002 remains immutable. It stopped after 4/12 Rounds with two
Families, 12 Proposals and eight Admissions under
`development_improvement_exhausted`; it had not exhausted novelty, Families
or budget. Its sole Holdout failure contributes only a structural fingerprint
to the clean-room seed. No rank, holdout metric or failure performance enters
the new Agent/Planner/Memory inputs.

The new Program reuses Campaign admission/evaluation, canonical DSL, formal
Qlib and the Artifact Store. It schedules three isolated Lane states and
shares only contracts, PIT/data-quality facts and structural/signal novelty.

## 6. Program Spec and evidence partitions

Canonical Program Spec is
`afrp1_5ac295d31336c174b8bb1728f819813b164b3a83093645db6483abf992a150b0`.
All Lane definitions and global budgets were frozen before the first Agent
call.

Adaptive research physically receives only 2019–2020. Locked Validation
2021–2024 is unavailable until every Lane planner and memory closes, selected
parameters freeze and Union Lock publishes. 2025/2026H1 are survivor-only
contaminated reports; Fresh Forward is never read.

## 7. Lane configurations and isolation

- Trend Structure: multi-horizon trend, pullback continuation, path quality,
  momentum acceleration.
- Volume and Trading Confirmation: volume/price confirmation,
  liquidity-normalized trend, volatility-conditioned trend.
- Recovery and Relative Strength: drawdown recovery, residual relative
  strength, simple cross-family hybrid.

Each Lane owns its Memory, Planner, counters, Rounds and Shortlist. The formal
run records zero manual intervention, manual Round planning and manual Lane
switching.

## 8. Adaptive research result

| Counter | Actual | Maximum |
| --- | ---: | ---: |
| Rounds | 15 | 24 |
| Agent calls | 15 | 24 |
| Proposals | 26 | 72 |
| Admissions | 23 | 48 |
| Local rescue Trials | 20 | 96 |
| Adaptive Qlib calls | 61 | 220 |
| Validation objects | 1 | 12 |
| Validation Qlib calls | 4 | 48 |
| Report Qlib calls | 0 | 20 |
| Final Survivors | 0 | 5 |

Each Lane completed five Rounds. Trend used 8 Proposals, 7 Admissions, 6
rescue Trials and 15 Qlib calls; Trading used 9/8/9/25; Recovery used
9/8/5/21. Trend and Recovery produced no eligible Lane shortlist. Trading
produced one.

Improvement stop occurred as
`program_improvement_exhausted_after_minimum_coverage` only after 15 Rounds,
15 calls, six distinct Families, all three Lanes and 23 Admissions exceeded
the frozen minimums.

## 9. Recovery behavior

The tenth persisted Agent response contained an unused declared parameter and
was rejected by the existing parameter/AST contract. Program recovery reused
the persisted response without another Agent call, closed it as a failed
Round and continued. A second resume issue exposed disposable evaluator
work-root reuse and recovery of pre-Development evaluations; the runtime now
uses a checkpoint-scoped clean evaluator cache and restores only evaluations
with a Development Lock. No completed Round or Agent response was lost.

## 10. Global novelty and search exposure

Final Global Novelty Index
`grni1_7cc8116f69f2bcbea12c2a77cd242d6967631ab2ae4a956ecfc1c65abd3746da`
contains 92 structural fingerprints and 10 current-Program signal
fingerprints, with no performance metadata. Its scope explicitly includes R1,
Campaign 001, Campaign 002 and the current Program.

The sole Candidate search-exposure record freezes effective search count 13,
two prior Program Agent calls, five prior Program Proposals, four prior
Admissions, four prior rescue Trials, 73 structural neighbors and zero prior
Program signal neighbors.

## 11. Shortlists and Union Lock

Lane Locks are:

- Trend: `alsl1_3b2dcb67...d9a6f97`, zero objects.
- Trading: `alsl1_88160254...929c36`, one object.
- Recovery: `alsl1_77d33a00...cf17ee`, zero objects.

Union Lock `apusl1_ede68a49...2901c` contains the unchanged Trading object:

```text
cs_rank(momentum_20_5)
*
cs_zscore(delta(amount_confirmed_momentum_60,
                periods=confirmation_change_window))
```

Its selected parameter is `confirmation_change_window=10`, orientation `+1`.
The Lock records all planners/memories/parameters frozen and validation reads
equal to zero.

## 12. Locked Validation

| Year | RankIC | CSI300 excess | Net return | Sharpe | Max drawdown | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 0.002685 | 14.91% | 8.69% | 0.3200 | -16.44% | 18.654 |
| 2022 | 0.001611 | 24.91% | 3.64% | 0.0818 | -18.01% | 19.094 |
| 2023 | 0.010760 | 4.03% | -7.72% | -0.6365 | -22.25% | 19.289 |
| 2024 | -0.001226 | 25.83% | 42.03% | 1.9047 | -13.08% | 18.724 |

Coverage is 100% in all four years with zero infinity and PIT violations.
Three RankIC years and all four excess years are positive. Median annual
RankIC is 0.002148, below the frozen 0.003 gate. Validation changes no
parameter, orientation, rank, Agent input, Planner input or Memory.

## 13. Multiple-testing control and failure

The combined 969-observation daily RankIC mean is 0.003457. HAC lag 10 gives
standard error 0.003160, t-statistic 1.0940 and one-sided p-value 0.136976.
With one Union hypothesis, BH adjusted q-value is also 0.136976, above the
immutable 10% FDR threshold.

Failure Report `pvfr1_0e668b8b...311310` records
`median_rankic` and `benjamini_hochberg_fdr`, generalization RankIC gap
-0.002244 and `registry_write=false`.

## 14. Final state, Registry and reports

Final Program Report is
`afpr1_d7368ad6bb59c53303ddfa0ffbd9d82aae96c6f994e2cb978c16c5c4f8e4f508`.
Terminal state is `completed_no_validation_survivor`. Candidate Locks,
Registry writes, Near Misses, 2025/2026H1 reports and Fresh Locks are all
zero. Strategy/Combined Optimization, Tushare/network and Promotion counts
are zero.

## 15. Artifact Store, cold recovery and replay

Cold validation returns `status=valid`,
`completed_no_validation_survivor`, zero evidence gaps and Store integrity
healthy with Missing 0 and Unreferenced 0.

Exact replay returns zero Agent, Factor/Strategy/Combined Optimization, Qlib,
Tushare/network, Registry, Fresh-Lock, Promotion, new Artifact and new Blob
counts.

## 16. Tests executed

- Focused Program/Campaign/Artifact Store/Context suite: 59 passed with
  `--no-cov`.
- Context Bootstrap: 42 bounded checks passed.
- Formal cold validation: passed, evidence gaps 0.
- Formal exact replay: passed, all call/write/new-object counts 0.
- A first Program-only invocation had 9 passing assertions but exited nonzero
  because repository-wide coverage was 3.61% below the global 5% threshold.
- A broad Artifact Store invocation had 38 passing tests and two failures
  because historical `/private/tmp/qm2-p0-005-optimization` source artifacts
  no longer exist. The directly relevant Store tests pass; this pre-existing
  reachability limitation was not repaired or hidden.

## 17. Architecture, security and data-lineage impact

This change adds a Program orchestration layer over existing services. It does
not replace Qlib, DSL, evaluation or Registry logic. No credentials,
dependencies, network-data authority, database or API boundary changed.
Lineage now freezes Lane and global selection before opening validation and
records project-level search multiplicity.

## 18. Known limitations

- Locked Validation is retrospective at project level, not Fresh or Frozen
  Test evidence.
- Runtime and Store are single-process/single-host.
- Historical novelty sources provide structural fingerprints but no uniform
  historical signal-materialization contract; current Program signal
  fingerprints are complete.
- The normal p-value uses a tested standard-normal approximation because no
  new statistical dependency was installed.
- Formal Program produced zero Survivors, so there is no Registry, report or
  Fresh-Lock success-path evidence from this run.
- Existing Qlib wrappers emit database/COS resolution warnings before the
  verified local formal Qlib chain completes.

## 19. Compatibility, rollback and remaining work

Campaign v1/v2 and all historical Candidates remain immutable. Rollback is
the single task commit; immutable Store objects are retained. No successor
task is authorized by this contract.

## 20. Git/workspace

The task creates one independent commit, does not amend and does not push.
Post-commit Planner evidence is finalized after commit.
