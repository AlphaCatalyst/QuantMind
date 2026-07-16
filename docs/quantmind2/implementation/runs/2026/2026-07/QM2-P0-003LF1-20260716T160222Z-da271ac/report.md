# Implementation Report: QM2-P0-003LF1 — Fix Manifest Self-reference PostgreSQL Test Assertion

## Task Summary

Corrected one test-only assertion from the nonexistent
`AnalyzedRun.git_consistency` attribute to the public
`AnalyzedRun.evidence` contract. No production behavior changed. The original
isolated PostgreSQL failure now passes, and real 003L/003LF planning, indexing
and exact replay remain verified.

## Goal and Scope

- Reproduce the committed 003LF PostgreSQL assertion failure.
- Confirm the real Planner result contract before editing.
- Replace only the invalid test assertion.
- Re-run Manifest, Planner, PostgreSQL, Project Knowledge, Context, Dataset
  Snapshot and Legacy Provider verification.
- Update Project Memory and create this Manifest v2 Run.

## Explicit Non-goals

- No production Manifest, Parser, Planner, Git consistency, Indexer,
  Repository, migration or database-schema change.
- No Dataset Snapshot, Legacy Provider, Factor DSL, training, Qlib, API or UI
  change.
- No dependency, lockfile, runtime configuration, Factor Lab, production
  database, amend or push.

## Preflight State

- Repository: `quantmind-main`
- Branch: `master`
- Base commit: `da271accfc06417ce5a36f8e34cef7ca70052760`
- Dirty before: no; unrelated dirty files: none.
- Factor Lab supplied expected digest:
  `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`.
- The same historical digest command produced
  `42d16e39b36f95c9663426d979ef950064ff76b4b4eaa8fd70acd262b14965e5`
  before this task. The read-only donor was not modified; before/after equality
  is checked separately. This pre-existing external mismatch is not hidden.

## Failed Assertion Reproduction

The opt-in disposable PostgreSQL command produced exactly `3 passed, 1
failed`. The failure occurred before the 003LF database scenario at:

```text
AttributeError: 'AnalyzedRun' object has no attribute 'git_consistency'
```

## Public Contract Verification

`AnalyzedRun` has the frozen public fields `discovered`, `parsed`, `evidence`,
`domain_build`, and `errors`. Its `validated` property delegates to
`evidence.consistent`. `GitConsistencyEvidence.consistent` requires every
mandatory evidence check to pass, and structured compatibility notices are
stored in `evidence.warnings`.

The test therefore now asserts:

```text
analyzed.evidence.consistent
analyzed.evidence.warnings == ()
```

No alias, default, skip, xfail, weakened check or production compatibility
property was added.

## PostgreSQL Verification

With `QM2_LEDGER_POSTGRES_INTEGRATION=1`, all four tests passed against a
disposable PostgreSQL 15 container. The suite applied migration 0001 and
verified synthetic replay/conflict behavior, real 003L first index/replay, and
real 003LF first index/replay. Both real Runs retained Task, Run and children;
their own Manifest did not become a ChangedFile. The container was removed and
no production database was contacted.

## Planner Verification

- 003L: validated, indexable, complete eleven-family Domain Bundle, zero
  evidence gaps, and exactly one
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED` warning.
- 003LF: validated, indexable, complete eleven-family Domain Bundle, zero
  evidence gaps, and zero warnings.

## Tests Executed and Results

- Original PostgreSQL reproduction: 3 passed, 1 failed as expected.
- Corrected opt-in PostgreSQL suite: 4 passed, 0 failed, 0 skipped.
- Manifest/Planner/Indexer focused suite: 24 passed.
- Full Project Knowledge/Context regression: 368 passed, 9 explicit
  non-opt-in PostgreSQL skips, 247 subtests passed.
- Dataset Snapshot/Legacy Provider regression: 55 passed, 1 real-TDX skip.
- Context Bootstrap: 38 checks passed.
- JSON parsing, py_compile, diff/scope and donor before/after checks are
  recorded in the Manifest.

## Architecture, Security and Data Lineage Impact

There is no production architecture or runtime impact. The change repairs test
evidence so it uses the already-frozen public Planner result. Manifest
self-reference rules, historical-v2 compatibility, Dataset Snapshot identity,
Legacy feature bytes and lineage remain unchanged. No secret or absolute donor
content is persisted.

## Project Memory

Current State, Handoff, Known Issues and Roadmap now record that QM2-P0-003LF1
closed the test-only assertion failure through real PostgreSQL revalidation.
They retain the 003L compatibility warning, unavailable TDX status, immutable
Legacy Snapshot facts, closed Ledger stage and exact Factor DSL next task.

## Known Limitations

- The supplied Factor Lab digest did not equal the value produced at preflight;
  the donor is outside Git authority and under `/tmp`. Its bytes remained
  read-only and unchanged during this task, but the earlier expected digest
  cannot be re-established without modifying or replacing external state.
- CI scheduling for opt-in PostgreSQL and pinned SQLAlchemy/asyncpg parity
  remain pre-existing limitations.
- Historical 003L continues to emit its intended compatibility warning.

## Compatibility and Rollback

The test assertion is compatible with the existing public object contract.
Rollback is the single task commit and would restore only the erroneous test
attribute reference; it would not affect production Manifest behavior or data.

## Remaining Work and Recommended Next Task

Only `QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` is
recommended. Ledger development remains closed.

## Git and Workspace State

One independent commit is required with message
`test(qm2): fix manifest indexer postgres assertion`. No amend or push. Final
post-commit checks must verify this Run, donor before/after equality and a clean
worktree.
