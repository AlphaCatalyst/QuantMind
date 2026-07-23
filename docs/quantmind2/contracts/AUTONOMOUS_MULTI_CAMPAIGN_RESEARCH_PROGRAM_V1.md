# Autonomous Multi-Campaign Research Program v1

## Status and scope

This is the frozen implementation contract for
`QM2-R2-003 — Autonomous Multi-Campaign Research Program and Global Search
Control v1`. It composes the existing Campaign v2, canonical Factor DSL,
default-first/local-rescue evaluator, formal Qlib chain and immutable Research
Artifact Store. It does not create a third factor-compute or backtest chain.

The formal Program is `technical_factor_program_001`. It is retrospective
clean-room research, not Fresh Validation, Frozen Future Test, predictive
evidence, Promotion or production evidence.

## Evidence partitions

| Partition | Agent | Planner | Failure Memory | Parameter selection | Shortlist | Registry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `adaptive_research` (2019–2020) | aggregate only | yes | yes | yes | yes | no |
| `locked_validation` (2021–2024) | no | no | no | no | no | pass/fail |
| `contaminated_report` (2025, 2026H1) | no | no | no | no | no | no |
| `fresh_forward` | no | no | no | no | no | no |

Any use outside this table is
`PROGRAM_EVIDENCE_PARTITION_VIOLATION`. All Lane planners and memories close,
all selected parameters freeze and the Union Shortlist publishes with zero
locked-validation reads before the 2021–2024 matrix can be evaluated.

## Program and Lane configuration

The immutable Program ID is the content hash prefix `afrp1_`. Its global
maximums are 3 Lanes, 24 Rounds, 24 Agent calls, 72 Proposals, 48 Admissions,
96 local-rescue Trials, 220 adaptive Qlib calls, 12 validation objects, 48
validation Qlib calls, 20 report Qlib calls, 5 Survivors and 8 Near Misses.
One Lane may use at most 9 Agent calls (the integer bound below 40% of 24) and
one Family at most 4 Rounds.

All three Lanes freeze before the first Agent call:

- `trend_structure_lane`: multi-horizon trend, pullback continuation, path
  quality and momentum acceleration.
- `trading_confirmation_lane`: volume/price confirmation,
  liquidity-normalized trend and volatility-conditioned trend.
- `recovery_relative_lane`: drawdown recovery, residual relative strength and
  simple cross-family hybrid.

Each Lane owns its Planner, Failure Memory, Round history, counters and
Shortlist. Performance, ranks and failure metrics never cross Lane
boundaries. Only the Feature/Operator contracts, data-quality/PIT failures,
structural fingerprints and adaptive signal fingerprints are global.

## Agent and Proposal boundary

The provider/model/runtime tuple is
`openai_codex_cli`/`gpt-5.6-terra`/`store_required`. One Round makes at most
one Agent call, requests at most three Proposals and admits at most two.
Proposal parsing, parameter/AST consistency and static Admission reuse the
Campaign v2 contracts. A persisted but contract-invalid Agent response closes
as a failed Round; it is not retried and cannot block Program recovery.

Terminal features are limited to three, optimizable parameters to two and AST
depth to six. Strategy parameters, regime gates, dynamic sizing, stop-loss,
rebalance selection and Promotion suggestions are forbidden.

## Adaptive evaluation and stopping

Adaptive evaluation physically receives only rows through 2020-12-31:

```text
Static Admission
→ Cheap Evaluation
→ Agent defaults
→ optional one-hop Local Rescue
→ Development Lock
→ 2019 and 2020 annual evaluation
```

The strategy is fixed at TopK 20, `n_drop=5`, ten-session rebalance, equal
weight, signal lag 1, open execution and CSI300 benchmark. Strategy and
Combined Optimization calls must remain zero.

An object becomes Lane-shortlist eligible only if both years are complete,
coverage is at least 90%, infinity/PIT violations are zero, at least one
annual RankIC and excess is positive, median RankIC is at least 0.003, worst
RankIC at least -0.008, median excess positive, worst excess above -10
percentage points, median turnover at most 30, best-ten-day contribution at
most 35% and maximum absolute existing-signal Spearman below 0.85.

Improvement stop is illegal before 12 Rounds, 12 Agent calls, six distinct
Families and completed Rounds in all three Lanes. It also requires at least
16 Admissions or exhaustion of all remaining Families. A stopped Lane does
not stop another Lane.

## Novelty and search exposure

The Global Novelty Index includes structural fingerprints from R1, Campaign
001, Campaign 002 and the running Program without performance metadata.
Exact canonical structures and parameter-only structural variants are
rejected. Adaptive absolute signal Spearman of at least 0.95 is rejected;
0.85–0.95 is high redundancy and cannot pass the independence gate.

Every adaptive Candidate records Lane and Program Agent calls, Proposals,
Admissions, local rescue Trials, prior Development Locks, global structural
and signal neighbors, and effective search count. Rejected objects remain in
the corresponding Round and budget evidence.

## Locks and validation

Each Lane publishes an immutable shortlist of at most four objects ranked only
on 2019–2020 evidence. After every Lane planner and memory is frozen, the
Program publishes one Union Shortlist of at most 12 structurally and
signal-distinct objects. Lane/Family diversity is preferred; capacity uses
only the frozen adaptive order.

Each Union object is evaluated once per calendar year from 2021 through 2024
with unchanged parameters and orientation. Validation is Pass/Fail and cannot
reorder, retune, update memory or create Rounds. The base gate requires four
complete years, three positive RankIC years, median RankIC at least 0.003,
worst RankIC at least -0.008, three positive excess years, positive median
excess, worst excess above -10 percentage points, turnover/concentration and
correlation limits, and parameter/orientation identity.

Daily 2021–2024 RankIC uses a Newey–West/HAC standard error with lag 10 and a
one-sided normal-approximation p-value for positive mean. Benjamini–Hochberg
is applied once over the complete Union with immutable FDR `q=0.10`.
Survival additionally requires adjusted q-value at most 0.10 and positive
combined mean RankIC.

If more than five objects pass, the pre-validation adaptive order alone
selects capacity. Failures publish immutable failure reports with
`registry_write=false`. Only Survivors may be idempotently registered as
`research_registered`; no stronger lifecycle state is permitted.

## Reports, Fresh Locks and replay

Only Survivors receive 2025 and 2026H1 contaminated reports. Reports never
change selection or lifecycle state. Each Survivor receives a no-backfill
Fresh Lock beginning on the first formal calendar date after the latest
market-data date, with minimum 60 trading days, five completed holding
windows and three rebalance periods. This task does not fetch or evaluate
Fresh data.

Checkpoints make a persisted Agent response recoverable without another
Agent call. Terminal replay validates immutable Store evidence and must
record zero Agent, Factor/Strategy/Combined Optimization, Qlib, Tushare,
network-data, Registry, Fresh-Lock and Promotion calls and zero new Artifacts
or Blobs.

## Formal first Program result

Program `afrp1_5ac295d3...a150b0` completed 15 automatic Rounds across all
three Lanes with 15 Agent calls, 26 Proposals, 23 Admissions, 20 local-rescue
Trials and 61 adaptive Qlib calls. Improvement stop occurred only after the
minimum coverage conditions were met.

Only `trading_confirmation_lane` produced a Lane-shortlist object. Union Lock
`apusl1_ede68a49...2901c` contains that one object and records zero prior
validation reads. The unchanged object completed four locked-validation Qlib
calls. It failed median RankIC (0.002148 versus 0.003) and BH FDR (adjusted
q-value 0.136976 versus 0.10). The governed final state is
`completed_no_validation_survivor`; Candidate, Registry, contaminated-report
and Fresh-Lock writes are zero.

Formal Report is `afpr1_d7368ad6...e4f508`. Store integrity is healthy with
zero missing or unreferenced Blobs. Cold validation has zero evidence gaps,
and exact replay reports every call/write/new-object counter as zero.
