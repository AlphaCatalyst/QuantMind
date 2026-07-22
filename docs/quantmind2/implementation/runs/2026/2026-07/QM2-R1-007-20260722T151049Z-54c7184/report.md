# QM2-R1-007 Implementation Report

## 1. Task Summary

- Task: `QM2-R1-007 — Default-first Momentum Structure Search v2`
- Result: completed, pending the containing commit and post-commit Planner
- Base: `54c718431f9532d88057006c203bec2d937a1055`
- Branch: `master`
- Experiment: `dfme1_e15ea299d223126df6c2e94c47522233393ae0903f75d48bdaa0e606db0986b0`
- Assessment: `dfma1_b2594506554b166154d4056e4ac23320da0c871d03cfa982885db483d2271af4`

## 2. Goal

Determine whether new Agent-proposed momentum structures produce stable
cross-sectional ability and CSI300 excess with explicit defaults and at most
R1-006 one-hop local factor rescue, without restoring full or combined search.

## 3. Scope and non-goals

Implemented the bounded runtime, Artifact contracts, Store integration, CLI,
tests, research execution, cold recovery, replay and Project Memory. The task
does not change Tushare authority, Fixed-100, Labels, existing Candidates,
Strategy parameters, Qlib algorithms, Registry lifecycle or Promotion. It
does not call Tushare/network, use 2025/2026 for selection, or run full,
random, Bayesian, Strategy or Combined optimization.

## 4. Preflight State

Repository, branch and HEAD matched the task contract. Worktree was clean,
`git diff --check` passed and unrelated dirty files were absent. R1-003,
R1-004, R1-005/R1-005F and R1-006 Reports/Manifests/Project Memory were read.
The formal Factor Lab path was read-only; at final verification the supplied
path contained only empty directories, so a content digest could not be
reconfirmed and no Factor Lab file was touched.

## 5. Governance and protocol

Decision `ogd1_7de0...911f7f5` was materialized and formally validated. It
requires default-first Factor/Strategy behavior and suspended combined search.
Development is 2019-01-02 through 2020-12-31. The fixed strategy is TopK20,
n_drop5, five-session rebalance, equal weight, lag one, open and CSI300.

Six themes were called once each through `openai_codex_cli` and
`gpt-5.6-terra`. Proposals were constrained to three terminals, two parameters
and depth six; accepted templates had one explicit Agent default parameter.

## 6. Agent proposals and defaults

| Round | Proposal | Default |
|---|---|---|
| 1 | multi_horizon_smoothed_consensus | consensus_window=10 |
| 2 | stability_adjusted_medium_momentum | stability_window=20 |
| 3 | medium_momentum_realized_volatility_adjusted | volatility_window=20 |
| 4 | breakout_confirmed_medium_momentum | breakout_confirmation_weight=0.5 |
| 5 | residual_relative_strength_blend | relative_strength_weight=0.5 |
| 6 | acceleration_quality_momentum | acceleration_weight=0.5 |
| 6 | residual_breadth_confirmed_momentum | residual_weight=0.65 |
| 6 | trajectory_stable_medium_momentum | trajectory_penalty=0.2 |

All eight raw Agent responses/Proposals/Templates are immutable Store-backed
evidence. R1-004 semantics were included in sanitized aggregate memory; no
daily Label, return, IC, single-stock contribution or report-period detail was
exposed.

## 7. Default evaluation result

All defaults have coverage 0.961--0.999, oriented mean RankIC 0.00146--0.01043
and positive-rate 0.511--0.542. Every default failed because turnover was
63.52--69.47, above the fixed limit 45, and because CSI300 excess was negative
(-61.71 to -38.01 percentage points) while top-bottom spread and monotonicity
were also negative. No default was frozen.

## 8. Local rescue

All defaults were data-quality clean and near-gate, so the legal R1-006
one-hop neighborhoods ran. Thirteen local Trials changed one parameter at a
time; each template used at most three total default-plus-local points, below
the seven-Trial cap. Every local Trial retained turnover above 61 and negative
CSI300 excess/group evidence. `optimization_rescued=false` for every study.

## 9. Development Locks, annual evaluation and later reports

There is no successful default or rescue, hence no Development Parameter Lock.
Without a lock there is no legal 2021--2024 annual fixed-parameter evaluation,
Eligibility Candidate, Candidate Lock, 2025 report or 2026H1 report. This is
the task contract's explicit valid zero-candidate terminal result, not a
missing run. The system did not lower gates, add rounds or use report periods.

## 10. Research conclusion

Under explicit defaults, no Strategy optimization and only one-hop local
factor rescue, the current Momentum Feature space did not produce a stable
research candidate. The experiment is materially less exposed to parameter
selection than R1-003, but the evidence cannot establish predictive
generalization or prove a causal reduction in overfit. No structure is
retained for future validation by this task.

## 11. Runtime and artifacts

- Agent calls: 6
- Defaults: 8
- Factor local optimization calls: 13
- Formal Qlib calls: 21
- Strategy/Combined optimization calls: 0/0
- Tushare/network calls: 0
- Promotion writes: 0
- Candidate Locks/reports: 0/0
- Store after run: 676 Artifacts, 3,427 Blobs
- Inventory: `sai_1cabe6a5...b8c1da`
- Integrity: healthy; Missing 0; Unreferenced 0

Cold recovery restored 40 formal objects. Exact replay restored the Experiment
and all descendants with Agent, Factor/Strategy Optimization, Qlib, network,
new Artifact, new Blob and Promotion counts equal to zero.

## 12. Implementation changes

Added `default_first_momentum_search` protocol/artifact/runtime, nine formal
Artifact kinds, cache/validator registration, the requested CLI, focused tests
and the frozen contract. Project Memory records the zero-candidate outcome.
Existing Factor DSL, Agent adapter, Momentum Dataset, R1-006 governance and
formal Qlib services are reused; none was reimplemented.

One post-execution result-summary bug called nonexistent `store.list_all()`
after the immutable Experiment had already published. It was changed to the
formal `list_artifacts()` API. Cold recovery proved the business chain was
complete; exact replay performed zero research calls. No research result was
rerun or mutated by this correction.

## 13. API, database, configuration and dependencies

No API, database, migration, configuration, dependency or lockfile change.
No service, Electron, LightGBM or production database was started.

## 14. Architecture, security and lineage impact

The runtime operationalizes ADR-0008 separation and R1-006 default-first
governance. All definitions, evaluations and terminal conclusions are
immutable and Dataset/Governance-lineaged. No credential is accepted or
persisted. Report periods and Promotion remain outside selection authority.

## 15. Tests executed

- Focused and governance tests: 46 passed.
- Relevant Momentum/Store/Runtime/Context regression: 110 passed after one
  corrected command; the first aggregate command named a nonexistent test
  file and ran zero tests.
- Context Bootstrap: 42 checks passed.
- CLI plan, governance validation, formal execute, cold recovery and exact
  replay passed. Formal execute initially returned exit 2 only at the final
  unsupported summary-count method; the immutable research artifacts had
  completed and were validated before the API correction.
- JSON parsing, `py_compile`, `git diff --check` and post-commit Planner are
  recorded by final task evidence; the Planner claim remains pending until
  the containing commit exists.

## 16. Known limitations

- Evidence is retrospective and contaminated, not Fresh Validation, Frozen
  Test, Promotion or production Alpha.
- Zero locks mean no 2021--2024 locked annual metrics or 2025/2026H1 reports
  exist; inventing them would violate chronology.
- Agent returned only one Proposal in rounds 1--5 and three in round 6; this
  is within the response cap and yielded eight total structures.
- Existing Qlib logs non-blocking missing optional model-registry dependencies
  and open-field NaN warnings; all claimed calls completed via formal Qlib.
- Artifact Store and execution are single-host/single-process.
- The official Factor Lab `/tmp` source directory was empty at final digest
  verification; its previously recorded branch/commit cannot be reverified.

## 17. Rollback, workspace and next task

Revert the single task commit to remove code/docs/tests. Immutable Store
evidence remains historical and must not be overwritten; a later task may
supersede it only through new lineage. No next task is authorized. Commit and
push were not performed when this Report was drafted; the final commit is
created only after Manifest and verification complete, and push remains no.
