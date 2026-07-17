# QM2-P0-009 Implementation Report

## Task Summary

QM2-P0-009 establishes the strict-forward Fresh Validation protocol for the
three candidates admitted by QM2-P0-008G. The implementation locks the cohort
before future market data, records historical exposure, publishes an immutable
protocol and source Watermark, implements immutable accrual and a one-time
evaluator, and adds bounded Registry and sanitized-memory compatibility.

## Goal, Scope, and Explicit Non-goals

Scope covers Candidate Lock, Exposure Ledger, Fresh Start, Watermark, post-lock
accrual, maturity, fixed-window evaluation, Registry pending/result fields,
sanitized Agent outcome categories, CLI, tests, documentation and Project
Memory. It does not rerun Agent, Optimization or Development; reselect a Trial;
change direction or admission; reuse historical 2026 data; run Frozen Test,
model, signal, Qlib or backtest; install dependencies; alter a lockfile; connect
to production databases; wait in the background; or promote a Factor.

## Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`; base `34dfa6eb50d7bd9405c3d3bdf0019aa84f9de432`.
- Worktree was clean; unrelated dirty files: none.
- Factor Lab remained read-only.

## Candidate Admission and Lock

The canonical admission and Registry were validated. The immutable lock is
`fvcl_716d7465285f7a8f541924877aa3acde9e90a38efe7d10dea2e20d6874063c7b`,
created at `2026-07-17T14:12:16.318993Z` (Asia/Shanghai market date
2026-07-17). It binds, in admission order:

1. `fi_a472a369d1e9abc63e756322da90d45e83b0031148691f49327ab543182f46e7`
2. `fi_85428fbe814abaaf7b6417c31da369b69794985c9e0418b2f634c24cfc6100b7`
3. `fi_79b37070859320f3fdda8335c1ad00b24fba7c4ccff1c68230dd6680e6202516`

Each record includes the complete Template payload/ID, bound parameters,
Study, Trial, Development result, family, rank and the locked `-1` orientation
derived before 2025 Development.

## Exposure, Fresh Start, and Watermark

Ledger `rdel_56d95b77f42f5b9784badaf3558e92e375d87be9cc1194143e334aba3e55f5ff`
records formal 2024 Validation, adaptive 2025 Development and historical
2026-01-05..2026-06-23 Frozen exposure. The already-generated source cutoff is
2026-06-24. Fresh start is the first observed trade date strictly after the
maximum of that cutoff and the lock market date.

Protocol `fvp_93163e1b4f82b52154bf0472b1cd165916f8ecae722ab851dd7fc4210bb5a867`
freezes the earliest 60 common label-complete dates, 100 daily observations,
fixed orientation, exact metrics and pass gates, with no backfill or reselection.

Real source
`model_features_2026.parquet` hashes to
`c2060c913dfdc7cc6a0723d19de53cc957c928a6ed490c163b1dceefde9269c1`
and ends 2026-06-24. Watermark
`fdw_3459fb5a20fb60707c6bf001dc194a931cfea7cddf250de2a099cba97efaa248`
therefore has zero eligible dates and status `awaiting_first_fresh_date`.
`build-accrual` returned `FRESH_VALIDATION_NOT_MATURE`; it emitted no artifact
or empty result.

## Runtime Flow and Important Symbols

`build_candidate_lock`, `build_exposure_ledger`, `build_protocol`, and
`build_watermark` publish/validate small Git-authoritative controls.
`compute_locked_factor_values` accepts only locked Template payloads and
parameters. `build_accrual_snapshot` rejects pre-lock rows, requires real T+1
label completion, and staging-publishes hash-validated Parquet artifacts.
`evaluate_fresh_validation` requires 60 dates, evaluates all three on the same
earliest window, applies fixed orientations/gates, atomically publishes one
result, and returns exact replay without reading later dates.

The Registry successor
`frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5`
adds `awaiting_data` evidence to the three entries. All main statuses remain
`research_registered`; promotion candidate, approved and active are 0/0/0.
Agent memory receives only pending/pass/fail categories, never Fresh metrics,
daily data or labels.

## Tests Executed and Results

- Focused Fresh suite: 8 passed, then 9 passed after sanitized-memory coverage.
- Registry/admission compatibility: included in the full relevant run.
- Full relevant DSL, Optimization, Validation, Registry, Campaign, Dataset,
  Manifest and Context regression: 243 passed, 9 environment-gated skips.
- Context Bootstrap: 39 checks passed; Context unittest: 21 passed.
- Real CLI lock, Watermark, maturity and immature accrual behavior: passed.
- JSON parsing, `py_compile`, `git diff --check`, scope, Factor Lab digest and
  final Manifest validation are final verification entries.

## Architecture, Security, Data Lineage, and Compatibility

This adds a forward evidence boundary downstream of Development admission and
upstream of any future Frozen protocol. Existing Factor DSL, Optimization,
production labels and metric implementations are reused. Registry fields are
optional, so old snapshots remain readable and retain their identities. Agent,
Optimizer and Admission packages cannot import the Fresh evaluator. No secret,
network call, API, database migration, runtime configuration, dependency or
lockfile changed.

Rollback is a revert of this single commit and removal of uncommitted runtime
artifacts under `/private/tmp/qm2-p0-009`; source/admission/history artifacts are
never overwritten.

## Known Limitations and Remaining Work

No strictly post-lock data exists, so no real Fresh metric, pass/fail conclusion,
Alpha claim or promotion exists. Annual Parquet remains mutable input. Small
controls are durable in Git, but future large accrual/result artifacts need a
persistent store. A real one-time run is allowed only after 60 label-complete
dates and must be a separate `QM2-FV-001` task.

The only recommended next implementation task is
`QM2-P0-010 — Persistent Research Artifact Store v1`.

## Git / Workspace State and Artifact Index

This Run is recorded as `completed_uncommitted` with `result_commit=null`, then
committed once using `feat(qm2): add fresh validation protocol v1`. No amend or
push is performed. Git authority includes Candidate Lock, Exposure Ledger,
Protocol and Watermark; large future datasets remain outside Git.
