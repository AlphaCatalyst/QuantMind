# Autonomous Factor Research Campaign v1

Status: implemented by `QM2-R2-001`.

## Boundary

The campaign is a bounded orchestration layer over the existing canonical
Factor DSL, Tushare Fixed-100 Momentum Feature Dataset, default-first
optimization governance, formal Qlib service and Research Artifact Store. It
does not implement another DSL, optimizer, backtester, Registry or market-data
provider.

The retrospective selection chronology is immutable:

```text
Development: 2019-01-02..2020-12-31
Annual selection: 2021, 2022, 2023, 2024
Contaminated report only: 2025, 2026-01-05..2026-06-23
```

R1-010 Fresh Forward artifacts and observations on or after 2026-06-24 are
forbidden as Agent, planner, failure-memory, optimization or Candidate
evidence. Tushare and market-data network calls are zero. The Agent network
boundary is counted separately.

## Frozen pilot budget

`technical_factor_campaign_001` permits at most 12 rounds, 12 Agent calls, 36
Proposals, 24 admitted Templates, 48 local-rescue Trials, 140 formal Qlib
calls, five Candidate Locks and five Near Misses. Each round permits one Agent
call, three Proposals and two admissions. The external provider is
`openai_codex_cli`, model `gpt-5.6-terra`, under `store_required` runtime.

## Stages and governance

Each Proposal passes closed DSL parsing, operator/Terminal/PIT/default/
complexity checks and parameter-independent structural fingerprinting before
value computation. The limits are three Terminal Features, two optimizable
parameters and AST depth six. Cheap 2019--2020 factor metrics precede formal
Qlib. Defaults are evaluated first with TopK 20, n_drop 5, ten-session
rebalance, equal weight, signal lag one, open execution and CSI300. A passing
default freezes immediately. Only a near-gate failure may evaluate the direct
one-parameter neighborhood, bounded by `min(1 + 2*p, 7)`.

A Development Parameter Lock fixes the Instance used independently in the
four annual selection years. Candidate eligibility applies the frozen
RankIC, CSI300 excess, turnover, concentration and independence gates. At
most five results may be stored as `research_registered`; no campaign action
may write Promotion, approved, active or production state.

## Automation, memory and recovery

The state machine is:

```text
planned -> running
running -> paused_recoverable_error | paused_budget
running -> completed_with_candidates | completed_no_candidate
running -> completed_early_stop | failed_nonrecoverable
```

Each completed round publishes its plan, exact raw Agent response, normalized
Proposals, evaluations and aggregate failure memory, followed by a content-
addressed state checkpoint. A provider timeout is counted and closed as a
failed round on resume; it is never silently retried as the same call.
Planner-visible memory contains aggregate outcomes only and excludes daily
labels, daily returns, daily IC, single-stock contribution, report-period
feedback and Fresh Forward evidence.

Automatic stopping occurs on any frozen budget, three consecutive rounds
without admission, four consecutive rounds without a Development Lock or
stability improvement, exhausted authorized families, or five independent
Candidate Locks. Zero Candidate is a legal result.

## Artifact and replay contract

The Store kinds are `autonomous_factor_campaign_spec`,
`autonomous_factor_campaign`, `autonomous_factor_round`,
`autonomous_factor_proposal`, `autonomous_factor_failure_memory`,
`autonomous_factor_round_plan`, `autonomous_factor_candidate_lock`,
`autonomous_factor_near_miss` and
`autonomous_factor_campaign_report`. Candidate values are stored separately
as `autonomous_factor_value_materialization` so the Candidate Lock references
an immutable value dataset instead of embedding or depending on a work cache.

Candidate Locks include the exact factor-value Parquet and contaminated
report-period results. The report results cannot enter selection or feedback.
Cold recovery validates the graph from an empty cache. Exact terminal replay
makes zero Agent, Factor/Strategy/Combined Optimization, Qlib, Tushare,
network, Registry, Promotion, Artifact or Blob writes.
