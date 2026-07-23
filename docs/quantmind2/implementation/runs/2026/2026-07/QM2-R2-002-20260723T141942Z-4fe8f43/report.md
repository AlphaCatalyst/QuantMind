# QM2-R2-002 Implementation Report

## 1. Task summary

Task `QM2-R2-002 — Autonomous Campaign Locked-Holdout and Generalization
Control v2` implemented a physically isolated Discovery/locked-holdout
Campaign and ran formal `technical_factor_campaign_002`. The governed result
is a legal zero-candidate completion.

## 2. Goal and scope

The change adds v2 Campaign models, evidence partitions, clean-room seed
memory, underexplored-family planning, search-exposure records, Failure Memory
freeze, immutable Shortlist Lock, one-time Holdout access, frozen Holdout
Gate, failure reports, survivor-only Registry writes, contaminated survivor
reports, Fresh Locks, CLI routing, Artifact kinds, tests, contract and Project
Memory.

## 3. Explicit non-goals

No new terminal feature, structure evolution, Strategy or Combined
Optimization, market-data fetch, Tushare call, Fresh evaluation, Promotion,
LightGBM/Qlib replacement, database/API/UI/dependency/lockfile change, v1
Candidate mutation, or Holdout-driven retuning/ranking was performed.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `4fe8f434aab959afd6e2402d326ac288bf285bb8`
- Worktree: clean
- Unrelated dirty files: none
- Factor Lab was not read or modified by the implementation runtime.

## 5. Campaign v1 generalization audit

The three v1 Candidates remain immutable
`research_registered/retrospective_v1_candidate`. Their creation was valid,
but all degraded in the 2025/2026H1 reports. The formal assessment records
`v1_candidate_creation_valid=true`,
`v1_fresh_or_predictive_validation=false`, and
`report_period_degradation=true`; it is forbidden from v2 Agent, Planner and
Failure Memory input.

## 6. Architecture and time isolation

Development is 2019-01-02..2020-12-31; Adaptive Discovery is
2021-01-04..2022-12-30; locked retrospective Holdout is
2023-01-03..2024-12-31; 2025 and 2026H1 are contaminated reports; future
observations are Fresh Forward.

Before constructing the Discovery evaluator, the feature matrix and every
known comparison signal are physically cropped to 2022-12-30. Agent requests,
Planner logs, Round Artifacts and Failure Memory accept only Development and
Adaptive Discovery. Holdout is instantiated from the full matrix only after
Rounds stop, Agent/Planner close, Memory freezes, parameters freeze and the
Shortlist Lock exists with `locked_holdout_reads=0`.

## 7. Spec, Agent and family allocation

The canonical revision 2.0.1 Spec is
`afc2_f3ba310a3b67cc9a4291744ae96c1d550bd7dd18ad9dcbe1be62cc52a9f17cb2`.
It binds `openai_codex_cli`, `gpt-5.6-terra`, `store_required`,
`tushare-pro-v1`, Fixed-100 and CSI300 before Agent use.

The Planner prioritizes volume/price confirmation, volatility-conditioned
trend, liquidity-normalized trend, pullback continuation, multi-horizon trend
and simple cross-family hybrid. v1-saturated families are limited to one
round; every family remains under the 25% Agent-call ceiling. Four rounds were
executed before the Development-improvement early stop.

## 8. Formal Campaign result

| Counter | Actual | Maximum |
| --- | ---: | ---: |
| Rounds | 4 | 12 |
| Agent calls | 4 | 12 |
| Proposals | 12 | 36 |
| Admissions | 8 | 24 |
| Local rescue Trials | 6 | 48 |
| Discovery Qlib calls | 17 | 100 |
| Discovery shortlist | 1 | 6 |
| Holdout Qlib calls | 2 | 12 |
| Report Qlib calls | 0 | 12 |
| Candidate Locks | 0 | 3 |
| Fresh Locks | 0 | survivor-only |

Manual intervention and manual round planning were both zero. Strategy and
Combined Optimization, Tushare/network calls and Promotion writes were zero.

## 9. Shortlist, exposure and Memory freeze

The only Discovery-eligible object had frozen `stability_window=10`,
orientation `+1` and a medium search-exposure classification. Failure Memory
was frozen before Shortlist
`acsl1_3746253e487016ec80ffe15088f6ea04ea5daff3a09f7d5a35b03681cab5f0a4`.
The Lock records one object, its Discovery rank, parameters, orientation,
metrics, correlations and exposure, with zero prior Holdout reads.

## 10. Locked Holdout result

Holdout evaluation
`ache1_ffda3d58639e2701c1405c50ae15e046aa96ccd39791bbcc059d274906fbe1df`
used the unchanged parameters and orientation:

| Year | RankIC | CSI300 excess | net return | turnover | best-10-day contribution |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023 | 0.009854 | 24.92% | 13.17% | 18.396 | 20.10% |
| 2024 | -0.002376 | 6.37% | 22.57% | 18.148 | 28.02% |

Coverage was 100%, with zero infinity and PIT violations. All gates passed
except `positive_rankic_years=2`. Failure Report
`achfr1_9493f072db4582a974766886d8a5c41b04fdc5d6899013211b39b046176bea70`
therefore records the object as `failed_locked_holdout=true` and
`registry_write=false`.

Holdout was Pass/Fail only. No ranking, retuning, additional round or Agent
feedback occurred.

## 11. Final state, Registry and Fresh isolation

The final state is `completed_no_holdout_survivor`. Candidate Locks, Registry
writes, 2025/2026H1 reports and Fresh Locks are all zero. This is the required
governed outcome; no gate or budget was relaxed.

## 12. Artifact Store, cold recovery and replay

Report:
`afcr2_bbeee1e907b2406e46dc82d72614e0e047c8e449457cc6fa9bd9fc82603cb4b0`.
The Store is healthy with Missing 0 and Unreferenced 0. Cold validation
returns `status=valid`, the final Campaign state and zero evidence gaps.
Exact replay returns zero Agent, Factor/Strategy/Combined Optimization, Qlib,
Tushare/network, Registry, Fresh Lock, Promotion, Artifact and Blob counts.

## 13. First-attempt evidence

Revision 2.0.0 Spec `afc2_8ba9c812...ddb8f` exposed a strict Timestamp/string
comparison error after the first Agent/Qlib work but before a Round Artifact
closed. It was not resumed or represented as canonical. Revision 2.0.1 fixed
date normalization and produced the canonical Campaign above. This failed
attempt remains immutable Store evidence and is a known limitation of the
pilot execution history.

## 14. Tests executed

- v2 focused pytest: 14 passed with `--no-cov`.
- Default v1/v2 Campaign tests and Artifact Store tests: passed.
- Context bootstrap and all new JSON parsing: passed.
- `py_compile`, `git diff --check`, Git inventory and post-commit Planner:
  recorded below/finalized after commit.
- The first focused pytest invocation also had 14 test passes but pytest
  returned nonzero because repository-wide coverage was 3.45% below its 5%
  global threshold; this was a test-invocation issue, not a failed assertion.

## 15. Architecture, security and data-lineage impact

The v1 API remains default-compatible. v2 adds a separate orchestrator path
and reuses the same canonical DSL, Qlib and Artifact Store. No credential or
network-data boundary changed. Data lineage now explicitly binds every metric
to a partition and prevents the 2023+ partitions from influencing generation
or Discovery selection.

## 16. Known limitations

- Locked Holdout is retrospective at project level, not Fresh or Frozen Test.
- Runtime is single-process/single-host.
- Formal Campaign produced zero survivors; future predictive evidence is
  therefore absent.
- The formal Qlib wrapper emits existing database/COS fallback warnings while
  completing the local Qlib chain.
- Revision 2.0.0 remains a noncanonical failed attempt as documented above.

## 17. Compatibility and rollback

Rollback is the single task commit. Artifact Store objects are immutable and
are not deleted by code rollback. v1 Campaign interfaces and historical
Candidates remain unchanged.

## 18. Git/workspace and recommendation

The task creates one independent commit and does not amend or push. No next
research task is authorized by this contract.
