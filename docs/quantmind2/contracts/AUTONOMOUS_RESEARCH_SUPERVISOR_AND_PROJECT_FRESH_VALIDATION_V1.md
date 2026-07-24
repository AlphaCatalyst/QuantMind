# Autonomous Research Supervisor and Project Fresh Validation v1

## Evidence boundary

As of `QM2-R2-005`, all project-visible market evidence through 2026-07-23 is
classified `retrospective_research_only`. It may support discovery,
diagnostics, parameter development and reporting, but cannot independently
support Fresh, Frozen, predictive, Validation, Promotion or production claims.

R1-010 remains an isolated Fresh protocol. Its observations are shown in the
project overview but never enter the Supervisor's Agent, Planner, feature
generation, historical ranking or Cohort statistics.

## Supervisor

`AutonomousResearchSupervisorSpecV1` freezes two-cycle, per-cycle Agent,
Proposal, Admission, Qlib, Candidate and Fresh-capacity budgets before
execution. The formal workflow is:

```text
Project Evidence Exposure Ledger
→ Research Queue
→ bounded Feature Factory / Alpha Program Cycle
→ retrospective_candidate
→ Project Candidate Fresh Lock
→ immutable Fresh Cohort
→ incremental first-seen market snapshots
→ archetype-specific Fresh test
→ global Cohort BH FDR
→ Fresh status
```

The Supervisor reuses the existing Feature Factory and Archetype-aware Alpha
Program. Historical gates can only create `retrospective_candidate`, meaning
`worth_fresh_observation`.

## Fresh protocol

A Fresh Lock starts on the first official trading date strictly after the
latest market date available at lock time and always sets `no_backfill=true`.
Formula, parameters, orientation, archetype, primary statistic, strategy,
universe, benchmark and market snapshot are immutable.

A Cohort contains at most ten locks and freezes before its first observation.
Minimum evidence is 60 Fresh trading days, five completed non-overlapping
holding windows, three rebalance periods, 90% finite coverage and zero PIT
violations.

Monotonic candidates use Fresh daily official-label RankIC with HAC lag 10.
Tail candidates use non-overlapping ten-session Top20-minus-universe spread
with HAC lag 1. Exactly one Primary p-value per mature Candidate enters one
Cohort-wide Benjamini–Hochberg test at FDR 10%.

Legal states are `fresh_locked`, `fresh_evidence_accumulating`,
`fresh_supported`, `fresh_rejected`, `fresh_inconclusive` and
`fresh_data_blocked`. Even `fresh_supported` has no Promotion authority.

## Data and credential boundary

Incremental collection is restricted to `daily`, `adj_factor`, `daily_basic`,
`trade_cal` and `index_daily`, starting at the stored maximum plus one.
Credentials are resolved from the environment only. The CLI has no credential
argument, and values, hashes, prefixes and suffixes cannot enter artifacts.
First-seen snapshots are immutable; corrections create child revisions.

## Formal QM2-R2-005 result

- Exposure Ledger: `peel1_f96c3595...a7c7eb`
- Supervisor Spec: `arsv1_1d07cf5c...abd14e`
- Research Queue: `arq1_1982ce71...29e71f`
- Research Cycle: `arc1_58325bd9...cb2c8b`
- Supervisor State: `ars1_57713f1c...61545b`
- Supervisor Report: `arsr1_3cc6becd...91666a`

The Ledger contains 16 formal Runs and extends project exposure through
2026-07-23. The first Cycle reused the immutable R2-004 Factory/Program
implementation and found no new authorized structure or Retrospective
Candidate. It made zero Agent, Qlib, Tushare and network calls. There are zero
Supervisor Fresh Locks/Cohorts/Observations; incremental collection is
therefore legitimately not required. Store integrity is healthy, and terminal
resume/replay has zero calls, writes and new objects.
