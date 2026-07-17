# QM2-P0-010F Implementation Report

## Task Summary

`QM2-P0-010F — Immutable Git Inventory Correction for Artifact Store Run`
records independent correction evidence for the immutable
`QM2-P0-010-20260717T154150Z-26cebb9` Run. It does not alter that Run or any
Artifact Store implementation or research artifact.

## Goal

Reconstruct the exact base-to-containing-commit path inventory, preserve the
business ChangedFile self-reference rule, explain the omission, publish a
strict correction Artifact, and make this correction Run independently
Git-consistent and indexable.

## Scope

- Git blob and diff evidence for base `26cebb9a9dfa95a295a57d66db193d9629844b90`
  through containing commit `77f5b1fd36fd4f85e14a4c0dd5945abefe847f7d`.
- A strict Git inventory correction Schema and Artifact.
- A read-only reconstruction/validation tool and prevention guard.
- Focused, context, Planner, and isolated PostgreSQL index/replay tests.
- Project Memory and Manifest v2 completion-gate clarification.

## Explicit Non-goals

- No edit or amendment to the target Report, Manifest, or commit.
- No Artifact Store production-code or runtime-result change.
- No migration rerun, inventory publication, recovery rerun, materialization,
  import, artifact mutation, Fresh evaluation, model, signal, Qlib or backtest.
- No dependency, lockfile, database migration, API, UI or production database.

## Preflight State

- Repository: `quantmind-main`
- Root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base commit: `77f5b1fd36fd4f85e14a4c0dd5945abefe847f7d`
- Dirty before: false
- Unrelated dirty files: none
- `git diff --check`: passed

## Historical Failure Reproduction

The formal Planner returned exit code 2 for the target Run:

- `validated=false`
- `indexable=false`
- mandatory failures: `git_changed_paths`, `added_files`
- evidence gap: `GIT_INCONSISTENT`
- warnings: none
- parser errors: none

The correction deliberately leaves that result unchanged.

## What Changed

- Added a strict correction Schema and a canonical correction Artifact.
- Added a Git-derived inventory reconstruction/validation CLI.
- Added a finalized-Run guard covering exact changed/added inventories,
  Manifest business exclusion, Report inclusion, late paths, add, modify,
  delete and rename behavior.
- Added focused and isolated PostgreSQL correction Run coverage.
- Added the correction Artifact to bounded Context Bootstrap validation.
- Clarified Manifest v2's post-commit completion gate.
- Updated human and machine Project Memory to distinguish the implemented
  Store from the still-inconsistent original Implementation Run.

## Why It Changed

The original structured input excluded the Run Manifest from both the business
ChangedFiles and integrity inventories. Only the business exclusion is valid.
The producer did not infer or delete the path; this is classified as
`incorrect_run_generation_usage`, not a producer or Artifact Store bug.

## Git Inventory Findings

- Verified changed paths: 42; recorded: 41.
- Verified added paths: 28; recorded: 27.
- Verified modified paths: 14.
- Verified deleted paths: 0.
- Verified renamed paths: 0.
- Missing from both integrity inventories: only the target Run Manifest.
- Unexpected paths in either inventory: 0.
- Business ChangedFiles: 41, correctly excluding the Manifest and including
  the Report.
- Canonical inventory SHA-256:
  `9bd0cdd46995b5e300d67a4c2d1a648d24d234689addf80d0191f1d8477ef25e`.

## Immutable Target Evidence

- Target Manifest SHA-256:
  `4f247cab75a073b5507d6583812bf810cde71b82a058a957151c7582424e96e3`.
- Target Report SHA-256:
  `abd6681b6703727de8eb52d61ff1862713e5ad607e31407eb365b6d21f2ef72a`.
- The original Run remains immutable, Git-inconsistent and non-indexable.
- This Run has exactly one relationship: `corrects` the original Run. It does
  not supersede, replace or reexecute it.

## Files Changed

The Manifest's structured `changed_files` is the authoritative business file
inventory for this Run. It excludes this Run's Manifest, includes this Report,
and covers only correction evidence, tests, validation contracts and Project
Memory.

## Important Classes / Functions / Documents

- `git_path_inventory`: reconstructs stable Git path families from commits.
- `verify_finalized_run_inventory`: enforces post-commit inventory semantics.
- `build_correction` / `validate_correction`: build and verify evidence.
- `implementation_git_inventory_correction_v1.schema.json`: strict contract.
- `IMPLEMENTATION_MANIFEST_V2.md`: post-commit completion gate.

## API Changes

None.

## Database Changes

None. PostgreSQL is used only through the existing migration and Repository in
a disposable test container.

## Configuration / Environment Changes

None. No dependency or lockfile changed.

## Runtime Flow

`immutable target commits → Git inventory reconstruction → strict correction
Artifact → correction Run → Planner → existing Ledger Indexer → exact replay`.

## Architecture Impact

No architecture or Artifact Store runtime behavior changes. This task makes
the Implementation Ledger evidence boundary explicit: business ChangedFiles
exclude a Run's own Manifest, while integrity Git inventories include it.

## Security Impact

No secrets, absolute Store root, credentials or external calls are recorded.
The tool executes fixed local Git inspection and validates repository-relative
paths. No production database was accessed.

## Data Lineage Impact

Evidence-only. Store reachability Plan, Inventory, all 65 Descriptors, 280
Blobs, migrated bytes and Fresh Validation identities are unchanged.

## Tests Executed

- Historical formal Planner validation: reproduced the original failure.
- `python3 tools/quantmind2/git_inventory_correction.py validate`: passed.
- Focused correction and Context Bootstrap pytest: 25 passed, 1 publication-
  dependent test skipped before this Run existed.
- DSL, Optimization, Validation, Registry, Campaign, Fresh Validation,
  Dataset Snapshot, Manifest and Indexer regression: 194 passed, 8 real-data
  tests skipped until their explicit artifact roots were supplied.
- Explicit real DSL, Optimization and Validation artifact regression: 9
  passed after binding the preserved local immutable artifact roots.
- `python3 tools/quantmind2/validate_context_bootstrap.py`: passed, 41 checks.
- JSON parse and `git diff --check`: passed.
- Post-commit Planner and disposable PostgreSQL index/replay are mandatory
  publication checks; their actual results are reported in the task handoff
  after the containing commit exists.

## Test Results

All executable pre-commit checks passed. The single pre-commit skip is the
test that requires this Run's Manifest to exist in a containing commit; it is
required to execute after publication and is not treated as a pass here.

## Known Limitations

- The immutable target Run remains inconsistent and cannot be indexed as a
  validated historical bundle without separately presenting correction
  evidence.
- Artifact Store runtimes are not yet cut over; that remains `QM2-P0-011`.
- Fresh Validation remains at 0/60 and no real Fresh Result exists.

## Compatibility / Migration Notes

No schema migration or runtime compatibility change. Existing Manifest v2 and
Planner strictness remain intact. The new correction Schema is additive.

## Rollback Notes

Revert this correction commit to remove the new evidence, guard, tests and
Project Memory statements. Do not edit the original Run or Artifact Store.
The Store's persisted objects require no rollback.

## Remaining Work

Complete post-commit Planner verification and isolated PostgreSQL index/replay,
then begin only the explicit runtime cutover task.

## Recommended Next Task

`QM2-P0-011 — Artifact-backed Research Runtime Cutover and Recovery Drill`.

`QM2-FV-001` remains conditionally forbidden until at least 60 mature trading
dates after the Candidate Lock are available.

## Git / Workspace State

This Run is produced before its single containing commit. `result_commit` is
therefore null and its source task status is `completed_uncommitted`; the
Planner resolves committed status from immutable Git after publication.

## Artifact Index

- This Implementation Report.
- This Implementation Manifest v2.
- Git inventory correction Artifact v1.
- Git inventory correction Schema v1.
