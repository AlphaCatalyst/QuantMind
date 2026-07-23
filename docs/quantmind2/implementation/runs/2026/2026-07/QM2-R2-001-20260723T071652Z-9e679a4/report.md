# QM2-R2-001 Implementation Report

## 1. Task summary

Task `QM2-R2-001 — Autonomous Factor Research Campaign Orchestrator v1`
implemented a bounded multi-round orchestration layer and executed the first
formal Campaign to a terminal state. The canonical Campaign completed with
three research-only Candidates; it made no production claim or Promotion.

## 2. Goal and scope

The implementation composes the existing Codex Research Agent, Factor DSL,
static novelty checks, default-first optimization governance, formal Qlib
runner and immutable filesystem Artifact Store. It adds a frozen Campaign
Spec, aggregate Failure Memory, automatic Round Planner, stage orchestration,
budget enforcement, checkpoints, resume behavior, Candidate and Near-miss
reporting, cold recovery, exact replay, CLI, tests and Project Memory.

## 3. Explicit non-goals

No full, random or Bayesian Factor search; Strategy or Combined optimization;
new Terminal Feature; market-data network call; Tushare call; Fresh Forward
input; automatic production registration; Promotion; LightGBM change; Qlib
replacement; API, database, migration, UI, dependency or lockfile change was
made.

## 4. Preflight state

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `9e679a423358b3500e78e3606c6b2ebc3d0fb3f3`
- Worktree before: clean
- Unrelated dirty files: none
- Formal Factor Lab path remained read-only. The `/tmp` donor is not used as
  runtime authority by this implementation.

## 5. Architecture and reused capabilities

`autonomous_factor_campaign` is an orchestration boundary, not a second
research stack. It reuses:

- `research_campaign` for `openai_codex_cli` and structured Agent decisions;
- `factor_dsl` for parsing, Template/Instance identity and factor execution;
- `optimization_governance` for one-hop, one-parameter local neighborhoods;
- `default_first_momentum_search` gates and parameter locking;
- `FormalQlibRunner` and existing `QlibBacktestService` for formal results;
- `artifact_store` for immutable publication, lineage, materialization and
  integrity checks.

The new package separates models, Admission, evaluation, planning, Failure
Memory, Artifact validation, Repository access and orchestration.

## 6. Frozen Campaign Spec and boundaries

The canonical Spec is
`afc1_5bae780edd8024e08220196a07d38c321ec6851204b16c30d75af92ac3fa8034`
at orchestrator revision `1.0.6`. It binds `technical_factor_campaign_001`,
`openai_codex_cli`, `gpt-5.6-terra`, `store_required`, `tushare-pro-v1`,
Tushare Fixed-100, CSI300 and Dataset
`mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c`.

Development is 2019-01-02 through 2020-12-31. Annual selection uses only
2021--2024. Results for 2025 and 2026H1 are contaminated report-only evidence.
`predictive_claim`, `fresh_validation`, `frozen_test` and
`usable_for_production` are all false.

The frozen maxima are 12 rounds, 12 Agent calls, 36 Proposals, 24 admissions,
48 local-rescue Trials, 140 formal Qlib calls, five Candidate Locks and five
Near-miss reports.

## 7. Agent and Admission contract

Each round creates a pre-Agent checkpoint and one immutable raw Agent-response
Artifact before parsing Proposals. Agent prompts receive only aggregate
Failure Memory and authorized Feature/operator lists. They do not receive
daily labels, daily returns, daily IC, stock contribution, report periods or
Fresh Forward evidence.

Admission parses the canonical DSL, validates the AST and parameter defaults,
enforces the operator and Feature allowlists, limits Terminal Features to
three, optimizable parameters to two and AST depth to six, requires a core
price/momentum/trend input, checks semantics and computes a
parameter-independent structural fingerprint before any Qlib call.

## 8. Evaluation and governance

Evaluation proceeds through static Admission, cheap development metrics,
default-parameter Qlib, optional one-hop local rescue, immutable Development
Parameter Lock, 2021--2024 annual Qlib, frozen Candidate gates and only then
contaminated reports for selected locks.

Default success freezes immediately. Rescue changes one declared Factor
parameter at a time to its adjacent legal value; it never searches Strategy
parameters or a joint space. Candidate ordering uses only the frozen
2021--2024 dictionary and never sees report-period evidence.

## 9. Failure Memory, Planner and state machine

Failure Memory contains only aggregate family, fingerprint, gate, failure,
turnover/cost and budget summaries. `report_period_degradation`, Fresh
evidence and daily data cannot enter Planner feedback.

The Planner selects among ten authorized technical families, caps each family
at three rounds, responds to the frozen failure taxonomy and temporarily
freezes repeatedly unsuccessful families. Early stops cover budget, novelty,
development improvement, exhausted search space and Candidate capacity.

States are `planned`, `running`, `paused_recoverable_error`, `paused_budget`,
`completed_with_candidates`, `completed_no_candidate`,
`completed_early_stop` and `failed_nonrecoverable`.

## 10. Checkpoint, recovery and replay

Every completed round publishes the Plan, exact Agent response, admitted
Proposal records, factor-value Parquet, evaluations, updated Failure Memory and
Campaign checkpoint. If a process stops after an Agent call, resume closes
that in-flight round from persisted evidence and does not repeat the call.

Cold validation materializes Spec, checkpoints, all 12 Round graphs, raw
responses, Proposals, factor values, Failure Memory, Candidates, Near-misses
and the Campaign Report from the Store. Exact terminal replay validates that
graph and performs no external or computational work.

## 11. Formal Pilot configuration and result

The formal Pilot ran once from the frozen revision 1.0.6 Spec. It completed
all 12 rounds with terminal state `completed_with_candidates` and stop reason
`budget_exhausted`.

| Counter | Actual | Frozen maximum |
|---|---:|---:|
| Rounds | 12 | 12 |
| Agent calls | 12 | 12 |
| Proposals | 26 | 36 |
| Admitted Templates | 20 | 24 |
| Default evaluations | 20 | 24 |
| Local-rescue Trials | 8 | 48 |
| Formal Qlib calls | 74 | 140 |
| Annual evaluations | 40 | bounded by admitted locks |
| Candidate Locks | 3 | 5 |
| Near-miss reports | 5 | 5 |
| Strategy / Combined optimization | 0 / 0 | 0 / 0 |
| Tushare / market-data network calls | 0 / 0 | 0 / 0 |
| Promotion writes | 0 | 0 |

Manual intervention and manual round-planning counts are both zero.

## 12. Round outcomes

| Round | Theme | Proposals | Admitted | Development locks | Eligible |
|---|---|---:|---:|---:|---:|
| 1 | multi_horizon_trend | 3 | 2 | 0 | 0 |
| 2 | drawdown_recovery | 2 | 2 | 2 | 1 |
| 3 | drawdown_recovery | 3 | 2 | 2 | 0 |
| 4 | drawdown_recovery | 3 | 2 | 1 | 0 |
| 5 | residual_relative_strength | 1 | 1 | 0 | 0 |
| 6 | residual_relative_strength | 1 | 1 | 0 | 0 |
| 7 | residual_relative_strength | 3 | 2 | 0 | 0 |
| 8 | path_quality | 1 | 1 | 1 | 1 |
| 9 | path_quality | 3 | 2 | 0 | 0 |
| 10 | momentum_acceleration | 1 | 1 | 0 | 0 |
| 11 | momentum_acceleration | 2 | 2 | 2 | 1 |
| 12 | momentum_acceleration | 3 | 2 | 2 | 0 |

The aggregate failure count is ten `weak_predictive_signal`, seven
`annual_instability` and six `semantic_mismatch`. No structure or signal
duplicate occurred in this Pilot; the duplicate gates were still executed.

## 13. Agent-call summary

All 12 calls completed through `openai_codex_cli` with effective model
`gpt-5.6-terra`. The immutable response artifacts record 210,267 input,
67,840 cached-input, 12,663 output and 3,785 reasoning-output tokens. There
were no market-data network calls; Agent calls are counted separately.

## 14. Candidate Locks

All three locks have status `research_registered`; none is validated,
approved, active, production-ready or promoted.

| Proposal | Parameters | 2021--2024 median / worst RankIC | Median / worst CSI300 excess | Median turnover | Max old-factor Spearman |
|---|---|---:|---:|---:|---:|
| `drawdown_distance_recovery_delta` | recovery periods 10, locally rescued from 5 | 0.005923 / 0.004264 | 15.17% / -1.75% | 17.912 | 0.442 |
| `normalized_acceleration_quality` | stability window 5, Agent default | 0.005612 / -0.003653 | 14.50% / 10.88% | 18.070 | 0.718 |
| `path_efficiency_acceleration` | baseline window 20, locally rescued from 10 | 0.004910 / 0.000847 | 8.26% / 3.46% | 17.934 | 0.491 |

The Candidate Lock IDs are:

- `afcl1_da61b45141892481dd3ab9250eea9dab9e9f6f0d6ca50f441b81e4ffe559ba3`;
- `afcl1_d54ef8d8fbd1163b844f20abb185a1144ec6125c0d304d7e65419f3cc3aac1c6`;
- `afcl1_6fddf98bb80863e952cc5c19472ffc81136943adb64dbd5b8cfb76bc4590f880`.

Each references a separate immutable Factor Value Materialization Artifact.

## 15. Contaminated report periods

All three Candidates have negative CSI300 excess in both report periods and
negative 2026H1 RankIC. The best 2025 net result is 10.94% for
`normalized_acceleration_quality`, but its CSI300 excess is -10.81%. In
2026H1 all three net returns and excess returns are negative. These results
were produced only after final Candidate selection and were never fed back
into the Campaign. They do not invalidate the historical research locks, and
they do prevent any predictive or production interpretation.

## 16. Near-miss queue

Five immutable Near-miss records were published with
`registry_write=false`. Two failed the development `predictive_or_excess`
gate. Three drawdown-recovery objects failed annual RankIC stability gates.
The queue is for human review only and did not alter Candidate thresholds.

## 17. Research efficiency

- Proposals per Agent call: 2.1667
- Admission rate: 76.92%
- Duplicate rejection rate: 0%
- Cheap-screen rejection rate: 0%
- Development-lock rate: 50%
- Local-rescue rate: 15%
- Annual-evaluation rate: 50%
- Candidate-lock rate: 15%
- Qlib calls per Candidate: 24.6667
- Terminal replay cache hit rate: 100%
- Manual intervention / round planning: 0 / 0

The artifact-cache metric is reported as 0% for first execution because the
formal Pilot created its Campaign evidence rather than replaying it.

## 18. Artifact Store and lineage

Ten Store kinds are supported: the nine required Campaign kinds plus a
separate Factor Value Materialization kind. Candidate values are not hidden in
work directories or mixed into Candidate identity.

Canonical Report:
`afcr1_e5eea677f1dc1b953740c740a4acd40d5c4d4d7c151680370c138ae77e8460f4`.
Final Failure Memory:
`affm1_b8c2e7f04338163f5c022eaab3ac54b9eb2f840cde3b8a5545b31b1495dba735`.
Store integrity is `healthy`, Missing 0 and Unreferenced 0.

## 19. Recovery and exact replay verification

Cold `validate-campaign` returned `status=valid`,
`campaign_state=completed_with_candidates`, `evidence_gap_count=0` and
healthy Store integrity. Exact replay and terminal `execute` each returned:

```text
Agent = 0
Factor / Strategy / Combined Optimization = 0 / 0 / 0
Qlib = 0
Tushare / network = 0 / 0
Registry / Promotion = 0 / 0
new Artifacts / Blobs = 0 / 0
replay cache hit rate = 1.0
```

The resume state transition is covered by a focused interrupted-Agent
checkpoint test: it preserves the counted Agent call, closes one Round from
persisted evidence and marks `call_repeated=false`.
The formal terminal Campaign was also pause-marked and resumed through the
CLI; it returned `exact_existing=true`, zero evidence gaps and all replay
call/write/new-object counts at zero.

## 20. Files and technical implementation

The new `autonomous_factor_campaign` package contains its public interface,
domain models, Artifact protocol, Admission, evaluator, Planner, Failure
Memory, Store Repository and Orchestrator. The CLI exposes all required
commands. Artifact Store enums and formal validators recognize the new kinds.
Focused tests and Project Memory/Context validation were added.

No existing Factor DSL, optimizer algorithm, Qlib service, Factor Registry,
model, data provider or trading implementation was replaced.

## 21. Tests and verification

- Formal revision 1.0.6 Pilot: 12 Agent calls and 74 real Qlib calls, terminal.
- Cold validation: valid, zero evidence gaps, Store healthy.
- Exact replay and terminal execute: all call/write/new-object counts zero.
- Focused autonomous suite: seven passed.
- Initial related suite: 79 passed before the resume-test addition.
- Final relevant Agent/DSL/governance/Store/Context regression and all
  remaining repository checks are recorded in the Manifest.
- Context Bootstrap: 42 bounded checks passed.

## 22. Security, lineage and architecture impact

The implementation reads only the existing Tushare-authoritative Snapshot and
does not accept a data credential. Artifact validators reject secret markers.
Selection lineage binds the Spec, source Dataset, Round Plan, exact Agent
response, Proposal, factor values, Development Lock, annual evidence, Failure
Memory and Candidate Lock. Report/Fresh evidence cannot enter selection.

The change adds an orchestration component and Store Artifact kinds without
changing accepted ADRs or the frozen separation of Factor, Strategy and
Combined optimization.

## 23. Known limitations

- Runtime is single-process and single-host; scheduling, leases and
  distributed workers are outside v1.
- Formal Qlib logs warn when the optional local PostgreSQL model Registry is
  unavailable. The explicit signal path still completed through
  `QlibBacktestService`, `RedisRecordingStrategy`, `SimulatorExecutor` and
  `CnExchange`; no model resolution was required.
- Only three of the five Candidate-capacity slots were filled. Gates and
  budgets were not relaxed.
- All three research Candidates degrade relative to CSI300 in the
  contaminated 2025 and 2026H1 reports; none is production-usable.
- Earlier same-task development Spec revisions remain immutable diagnostic
  artifacts. Only revision 1.0.6 and its listed Spec/Report are canonical.
- The official Factor Lab donor remains under `/tmp`, which is not a durable
  long-term source location; this task did not modify or copy it.

## 24. Compatibility, rollback and next work

Rollback is a revert of the single task commit. Store objects are immutable
historical research evidence and are not deleted or overwritten by rollback.
Existing research Candidates, Factor Registry, R1-010 Fresh observation,
LightGBM and Qlib remain compatible and unchanged.

This task authorizes no successor and the Manifest recommends no next task.

## 25. Git/workspace state

The task will be committed once as
`feat(qm2): automate factor research campaigns`, without amend or push.
Post-commit Planner validation and the final clean worktree are reported after
the commit.
