# QM2-R1-001F Implementation Report

## 1. Task Summary

`QM2-R1-001F — Expanded-factor Iteration Git Evidence Correction` records an
independent immutable correction for the only Git evidence gap in
`QM2-R1-001-20260720T182257Z-a574580`.

## 2. Goal

Reconstruct the target commit's exact path and business-file inventories,
preserve the original Run unchanged, and publish a gap-free Manifest v2 Run
with one `corrects` relationship.

## 3. Scope

- Read-only Git reconstruction for commit `4de8b1e8...`.
- `GitEvidenceCorrectionV1` evidence and focused contract tests.
- Project Memory correction status and authorized next-task update.
- Implementation Report, Manifest v2, Planner and Ledger admission evidence.

## 4. Explicit Non-goals

- No edit to the original QM2-R1-001 Report or Manifest.
- No business, Agent, optimization, Qlib, Tushare, network or Promotion run.
- No Factor, Dataset, DSL, value, Registry, Store descriptor or Blob change.
- No Producer, Parser, Planner, Indexer, migration, API or database behavior change.

## 5. Preflight State

- Repository: `quantmind-main`
- Root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `4de8b1e8e1f8562c0ef0a4a8d692df2fc7f3cfab`
- Dirty before: false
- Unrelated dirty files: none
- `git diff --check`: passed

## 6. What Changed

- Added one deterministic `GitEvidenceCorrectionV1` Artifact.
- Added focused tests for exact Git inventory, immutable original evidence,
  path-only Manifest self-reference semantics, correction relationship,
  Planner/Indexer admission, runtime call counts and Store integrity.
- Updated human/machine Current State and Handoff plus their bounded schemas
  and assertions for `QM2-R1-001F` and the authorized `QM2-R1-002` successor.
- Added this Run's Report and Manifest v2.

## 7. Why It Changed

The original structured Manifest input correctly omitted its own protocol
carrier from business `changed_files`, but incorrectly reused that reduced
list for `integrity.git_changed_paths` and `integrity.git_added_paths`. The
producer did not remove the path, and Planner correctly treats the collections
as distinct. Root cause is `incorrect_run_generation_usage`; no generic code
change is justified.

## 8. Files Changed

The Manifest `changed_files` array is authoritative. It excludes only this
Run's Manifest, while the integrity Git path inventories include it as a path
string.

## 9. Important Classes / Functions / Documents

- `GitEvidenceCorrectionV1`: exact target Git paths, business hashes, root
  cause, target identities and zero-call audit.
- `test_expanded_factor_iteration_git_evidence_correction.py`: deterministic
  reconstruction and immutable-boundary verification.
- Project Current State and Handoff: corrected Ledger interpretation without
  changing research conclusions.

## 10. API Changes

None.

## 11. Database Changes

None. No production database is accessed.

## 12. Configuration / Environment Changes

None. No dependency or lockfile is changed. Existing cached Python runtimes
are reused.

## 13. Runtime Flow

`immutable target commit → Git diff/blob reconstruction → correction Artifact
→ Manifest v2 correction Run → Planner → existing Ledger Indexer admission`.

## 14. Architecture Impact

Evidence-only. It reinforces the frozen distinction
`changed_files != git_changed_paths != git_added_paths` and does not alter
platform architecture or runtime behavior.

## 15. Security Impact

None. Evidence contains repository-relative paths and hashes only; no secret,
credential, token, network request or production database access exists.

## 16. Data Lineage Impact

None to research data. Experiment
`afi2_78fe313863910ce2cd47409ac1fbe66dbedaea1bfc8815a0e09f261288d57fcf`
and Candidate Lock
`afcl_27fb695b24bf92a63fb8a57e55bfdb102a675935e951b12184d7b9e8f6aba51e`
remain unchanged.

## 17. Tests Executed

- Original Planner: reproduced `validated=false`, `indexable=false`, one
  `GIT_INCONSISTENT` gap and failures `git_changed_paths` / `added_files`.
- Focused correction plus Context tests: 24 passed, 2 publication-dependent
  tests skipped before the Correction Run commit exists.
- Full relevant correction, Manifest v2, Git consistency, Ledger Indexer and
  Project Memory regression: 57 passed, 1 containing-commit test skipped.
- Context Bootstrap: passed all 42 bounded checks.
- Artifact Store read-only scan: 285 Artifacts, 2,508 Blobs, healthy, zero
  missing and zero unreferenced.
- Context Bootstrap, Manifest v2, JSON, `py_compile`, regression and Git scope
  checks are execution gates for this Run.

## 18. Test Results

All executable pre-commit checks pass. The remaining skip requires this Run's
containing commit and must pass after the single publication commit. An initial
system-runtime attempt did not collect tests because pytest was unavailable;
it is not represented as a passed or failed test.

## 19. Known Limitations

- The immutable target Run remains historically Git-inconsistent and
  `partial_committed`; the separate completed correction Run and `corrects`
  relationship are the supported corrected-completion representation.
- The business research conclusion remains `mixed`; the factor is only
  `research_registered`, fails to continue in 2025 and 2026H1, and has no
  Promotion candidacy.

## 20. Compatibility / Migration Notes

No runtime, schema migration or API compatibility change. Existing historical
Runs retain their bytes and interpretation.

## 21. Rollback Notes

Revert this single correction commit to remove only correction evidence,
tests and Project Memory updates. Do not edit the original Run or research
Artifacts.

## 22. Remaining Work

Only the post-commit Planner and Indexer-admission checks remain at Manifest
production time. No research work remains in this task.

## 23. Recommended Next Task

`QM2-R1-002 — PIT Fundamental and Regime-aware Factor Iteration v1`.

## 24. Git / Workspace State

The Run is produced before its single containing commit. Its Manifest source
status is `completed_uncommitted`, `result_commit` is null, and the Planner
must resolve it to committed status from Git. No amend or push is permitted.

## 25. Artifact Index

- This Implementation Report.
- This Implementation Manifest v2.
- `QM2-R1-001-git-evidence-correction-v1.json`.
