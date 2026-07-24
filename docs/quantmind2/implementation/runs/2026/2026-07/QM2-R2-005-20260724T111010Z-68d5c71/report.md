# QM2-R2-005 Implementation Report

## 1. Task summary

Task `QM2-R2-005 — Autonomous Research Supervisor and Project-Level Fresh
Validation v1` establishes the project-wide historical-exposure boundary,
bounded autonomous research Supervisor, retrospective Candidate contract,
no-backfill Fresh locks/cohorts, archetype-aware Fresh testing and global
Cohort FDR.

The first formal Supervisor execution completed one automatic Cycle and
correctly produced zero Retrospective Candidates. It did not repeat Agent,
Qlib or market-network work and did not lower any gate.

## 2. Goal and scope

The implementation adds:

- immutable `ProjectEvidenceExposureLedgerV1`;
- frozen `AutonomousResearchSupervisorSpecV1`;
- autonomous Research Queue and Cycle records;
- strict `retrospective_candidate` validation;
- first-official-date-after-cutoff Fresh Locks;
- immutable, maximum-ten-member Fresh Cohorts;
- monotonic HAC10 and tail HAC1 Fresh tests;
- Cohort-wide Benjamini–Hochberg FDR 10%;
- six-state Fresh lifecycle, active-capacity and global-stop controls;
- first-seen Snapshot/revision and incremental deduplication contracts;
- Store publication, cold validation, resume, exact replay and CLI;
- tests, contract and Project Memory.

## 3. Explicit non-goals

No historical evidence was relabeled Fresh. No old Candidate or Artifact was
mutated. No threshold/FDR relaxation, automatic Promotion/trading,
Factor/Strategy/Combined Optimization, LightGBM/Qlib replacement, dependency,
lockfile, database, API or UI change occurred.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `68d5c7175390089db5827b9ce8f57b13761dfde1`
- Worktree: clean
- Unrelated dirty files: none
- `TUSHARE_TOKEN`: present in environment; value, hash, prefix and suffix were
  not printed or persisted.
- Official Factor Lab remained read-only.

## 5. Historical research audit and exposure Ledger

The formal conclusion is:

```text
Autonomous research execution = operational
Historical robust alpha survivor = none
```

Campaign 001 later degraded; Campaign 002 had no Holdout Survivor; Program
001 and Alpha Program 002 had no Validation Survivor.

Ledger `peel1_f96c3595ab18f3d496fa216799347c33092c8e4b19b8effb126d28b0d0a7c7eb`
contains 16 formal R1/R2 Runs. The R1-010 incremental Snapshot proves project
visibility through 2026-07-23, so the project exposure range is
2019-01-02..2026-07-23. All such evidence is now
`retrospective_research_only`.

R1-010 is explicitly marked statistically isolated: its Fresh observations
cannot enter Supervisor Agent, Planner, parameters, candidate selection or
Cohort statistics.

## 6. Supervisor Spec and Research Queue

Supervisor Spec
`arsv1_1d07cf5c773e0fef1c7855b874235405e8c1e0e247caa1f4af51876aecabd14e`
was persisted before Cycle execution. It freezes all task budgets, FDR 10%,
minimum Fresh evidence, no-backfill, no Promotion and no automatic trading.

Research Queue
`arq1_1982ce71db80bff8cdabf266b2ab259c599a2eb2dcb4150f25ee548f1d29e71f`
contains three research directions. Priority inputs are structural/feature
coverage, duplicates, static failure and historical research efficiency.
Fresh performance cannot modify the same Candidate formula.

## 7. Formal Research Cycle

Cycle
`arc1_58325bd9f85a99d605dd185b7555220005b747132cb0ff456b130c0a3bcb2c8b`
reuses the existing Feature Factory and Archetype-aware Alpha Program
implementation and immutable R2-004 result. The current Catalog/Program
revision has no new authorized structure, so replaying the same Agent/Qlib
work would add no novel research.

Formal Cycle counts:

- Research Cycles: 1
- Feature/Alpha Agent calls: 0/0
- Proposals/Admissions: 0/0
- Qlib calls: 0
- Tushare/network calls: 0/0
- Candidate/Fresh/Registry/Promotion writes: all 0

The Cycle produced no Retrospective Candidate. This is a legal result and no
historical gate was reduced.

## 8. Fresh validation contracts

A Candidate can only be `retrospective_candidate` after data, PIT,
default-first, frozen-parameter, cross-year, turnover, concentration,
redundancy and historical multiple-testing gates.

A Fresh Lock binds the unchanged formula, parameters, orientation, archetype,
primary statistic, strategy, universe, benchmark and market Snapshot. Its
start is the first official trading date strictly after the lock-time market
maximum, with `no_backfill=true`.

Cohorts freeze no more than ten members before their first observation.
Minimum evidence is 60 Fresh trading days, five completed non-overlapping
holding windows, three rebalances, 90% finite coverage and zero PIT
violations.

Monotonic uses Fresh daily RankIC/HAC10; tail uses non-overlapping ten-session
Top20-minus-universe spread/HAC1. One Primary p-value per mature Candidate
enters one global Cohort BH test at q=10%.

Legal states are `fresh_locked`, `fresh_evidence_accumulating`,
`fresh_supported`, `fresh_rejected`, `fresh_inconclusive` and
`fresh_data_blocked`. `fresh_supported` still has no Promotion authority.

## 9. Incremental data and credential safety

The incremental contract restricts collection to `daily`, `adj_factor`,
`daily_basic`, `trade_cal` and `index_daily` from the stored maximum plus one.
The CLI has no Token argument. First-seen Snapshots are immutable; revisions
bind their parent without overwriting it.

The formal run had zero active Supervisor Fresh Candidates, so
`update-market-data` returned
`not_required_no_active_fresh_candidates` with zero Tushare/network calls.
This is the required legal no-data path, not a hidden failure.

## 10. Formal terminal state

Supervisor State:
`ars1_57713f1cd561c8188c67eb21a8dbeb0b3e0a73da1c8d7851e8d88750f761545b`

Report:
`arsr1_3cc6becdc5aa349f7ebe83c6814d5b1bb0b4367d5361b83261e54cf1db91666a`

Status is `waiting_for_fresh_data_or_novel_space`. Active Fresh count is
0/20. Consecutive empty Cycle counters are 1/1, below the two-Cycle global
stop threshold.

## 11. Store, recovery and replay

Store integrity is healthy with Missing 0 and Unreferenced 0. Cold validation
reconstructs Ledger, Spec, Queue, Cycle, State and Report with zero evidence
gaps. Terminal resume and exact replay return zero Agent, Qlib, Tushare,
network, Feature, Candidate, Fresh, Registry, Promotion, new Artifact and new
Blob counts.

## 12. Tests executed

- Supervisor/R2/R1-010/Tushare/Store/Context relevant suite: 142 passed with
  `--no-cov`.
- Initial Supervisor and R2 focused suite: 73 passed.
- Supervisor/Context focused suite: 45 passed.
- Context Bootstrap: 42 bounded checks passed.
- Formal create/plan/execute/update/validate/resume/replay: passed.
- All Project Context JSON documents parse.
- New Python modules and CLI pass `py_compile`.
- `git diff --check` passes.

## 13. Architecture, security and lineage impact

The Supervisor composes existing Factory/Program/Data/Store services and does
not create another research engine. It introduces the project-level
contamination authority and makes true Fresh time start only after the latest
visible market date at lock time.

No credential material enters code, CLI, Store, Report or Manifest. Registry
and Promotion remain separate human-authorized boundaries.

## 14. Known limitations

- The formal Cycle produced zero Candidate, so there is no formal-run
  Fresh-Lock/Cohort/observation success-path evidence.
- Project Fresh evaluation cannot begin until a new Candidate is locked and
  official data exists strictly after that lock-time cutoff.
- Incremental execution and the Artifact Store remain local,
  single-process/single-host.
- Current authorized Catalog/Program revision is exhausted; a new Cycle
  requires genuinely new authorized search space.
- R1-010 remains a separate Fresh experiment and is not statistically pooled.

## 15. Compatibility and rollback

Historical Campaigns, Programs, Candidates, Locks, observations and Registry
states remain immutable. Rollback is a revert of the single task commit;
Store artifacts remain immutable evidence. No successor task is authorized.

## 16. Git/workspace

The task creates one independent commit, does not amend and does not push.
Post-commit Planner evidence is finalized after commit.
