# Implementation Report: QM2-P0-003LF — Manifest Self-reference Fix and 003L Forward-indexability

## Task Summary

Fixed the Manifest v2 self-reference defect without modifying the immutable
QM2-P0-003L Run. New producers and semantic validation reject a Manifest that
lists its own protocol path as a ChangedFile. Committed v2 payloads receive a
narrow path-based compatibility warning, omit only that protocol carrier from
ChangedFile hashing/mapping, and retain every other Git evidence check.

## Goal

Make future Manifest v2 Runs self-reference-free, restore 003L Git consistency
and complete Domain construction, prove isolated PostgreSQL indexing/replay,
and close the repair so work can move directly to Factor DSL.

## Scope

- Reproduce and record 003L's exact failing check and hashes.
- Harden producer, standalone validator, Context Bootstrap and Planner.
- Add structured compatibility warning and exact diff exclusion boundary.
- Filter the protocol carrier from historical v2 ChangedFile Domain mapping.
- Revalidate and index 003L in disposable PostgreSQL 15.
- Update contracts, AGENTS, Project Memory, tests and this Manifest v2 Run.

## Explicit Non-goals

- No Factor DSL, optimization, Registry, TDX, training or Qlib switch.
- No Dataset Snapshot, source Parquet, feature, schema or quality change.
- No Ledger table, migration, Repository, API/UI, watcher or deployment.
- No historical Run edit/amend, dependency/lockfile change, Factor Lab change,
  production database access or push.

## Preflight State

- Repository ID: `quantmind-main`
- Branch: `master`
- Base commit: `22461e0fb603171efa5b1467586a260e2f54ed7b`
- Dirty before: no; unrelated dirty files: none.
- 003L Report/Manifest were tracked and immutable.
- Factor Lab digest before:
  `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`.

## Root Cause Reproduction

Formal Planner validation of
`QM2-P0-003L-20260716T151140Z-7d29df7` found containing commit
`22461e0fb603171efa5b1467586a260e2f54ed7b`, source status
`completed_uncommitted`, resolved status `completed_committed`, and exactly one
mandatory failure: `changed_file_hashes`. The historical Manifest listed its
own path as an added ChangedFile with declared after-hash
`0000000000000000000000000000000000000000000000000000000000000000`;
the actual Git blob SHA-256 is
`740814fdaff463f144b2d3982e3fd0ea015b8d3b8f62d2c604c987c1dd16fe1f`.
That single failure produced one `GIT_INCONSISTENT` gap and prevented a bundle.

## What Changed

- Added stable `MANIFEST_SELF_REFERENCE` error and semantic path detector.
- `new`, `finalize-payload`, standalone validation and source Domain validation
  now reject `changed_files[*].path == run.manifest_path`.
- Committed v2 parsing remains lossless and enables only the structural legacy
  compatibility path.
- Git evidence separately verifies complete protocol Git inventory and exact
  business ChangedFiles after excluding only the current Manifest.
- Compatibility skips only the self item's before/after hash and emits
  `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`.
- Historical Domain construction omits that item; Report and all other paths
  remain normal ChangedFiles.
- Planner JSON exposes structured warnings.
- Context Bootstrap permits an exact already-committed historical carrier but
  rejects an uncommitted/new self-reference.

## Important Classes and Functions

- `ManifestSelfReferenceError`
- `manifest_self_reference_items`, `reject_manifest_self_reference`
- `validate_manifest_v2_payload`
- `business_changed_paths`
- `GitConsistencyService.validate`
- `EvidenceWarning`
- `DomainBundleBuilder._v2_bundle`
- `new_draft`, `_plan_summary`, `validate_bootstrap`

## Compatibility Boundary

Compatibility requires schema v2 and a ChangedFile path exactly equal to that
payload's `run.manifest_path`. There is no Run-ID condition. Only that path is
removed from business comparison and Domain mapping. The Report, another Run's
Manifest, arbitrary JSON, all other statuses/hashes, artifact bytes, report and
payload hashes, complete Git inventories, source/diff hashes, containing commit
and immutable history remain mandatory. Payload hashing is unchanged.

## QM2-P0-003L Revalidation

- Parse, report hash and payload hash: passed.
- Containing commit: `22461e0fb603171efa5b1467586a260e2f54ed7b`.
- Source/resolved status: `completed_uncommitted` / `completed_committed`.
- Git consistency: passed.
- Warning: one `LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`.
- Evidence gaps: zero.
- Domain Bundle: complete, all eleven families.
- ChangedFiles: 28 real business records; Manifest absent, Report retained.

## PostgreSQL Verification

An isolated `postgres:15-alpine` container received unchanged migration 0001.
The formal 003L plan indexed successfully, stored its Task, resolved Run, all
children and real Snapshot Artifact, and stored 28 ChangedFiles without the
Manifest. The second index was exact replay with no extra Run/detail rows. The
container was removed. No production database was contacted.

## Architecture Impact

This is an Implementation evidence-contract correction only. It does not alter
frozen research architecture, Ledger persistence schema, Dataset Snapshot,
Factor/Model/Qlib behavior or authority boundaries. Ledger remains closed after
this bounded repair.

## API, Database and Configuration Changes

No API, table, migration, production configuration, dependency or lockfile
changed. Existing migration 0001 was only exercised in a disposable database.

## Security and Data Lineage Impact

Errors and warnings contain stable codes and repository-relative semantics, not
absolute paths or secrets. Historical payload bytes and payload-hash algorithm
remain immutable. Dataset lineage and every 003L Snapshot hash remain unchanged.

## Tests Executed and Results

- Focused producer/validator/compatibility/Planner suite: 24 passed after final
  additions (recorded in Manifest command evidence).
- Full Project Knowledge/Context regression: 368 passed, 9 explicit disposable
  PostgreSQL tests skipped in the non-opt-in pass, 247 subtests passed.
- Full relevant market/Legacy Snapshot regression: 55 passed, 1 real-TDX test
  skipped because the proprietary runtime remains unavailable.
- Opt-in disposable PostgreSQL backfill suite: 3 passed, 1 expected pre-commit
  skip for this Run's containing-commit check; container cleaned.
- Context Bootstrap: 38 checks passed.
- JSON, py_compile, diff/scope and digest checks are recorded in the Manifest.

## Known Limitations

- The committed compatibility parser accepts structurally matching historical
  v2 carrier entries and warns; strict production paths reject new ones.
- Production Ledger deployment and historical v1 gaps remain out of scope.
- SQLAlchemy 2.0.51/asyncpg 0.31.0 were used for disposable PostgreSQL evidence;
  pinned-runtime parity remains a pre-existing limitation.
- Current Run post-commit self-indexability and PostgreSQL replay must be
  verified after the single commit; they are not pre-claimed here.

## Compatibility and Rollback

Manifest v1 parsing and hashing are unchanged. Normal self-reference-free v2
Runs remain strict and indexable. Rollback is the single task commit. Rolling
back reintroduces 003L's `changed_file_hashes` gap but does not alter 003L or its
Dataset Snapshot.

## Remaining Work and Recommended Next Task

Only `QM2-P0-004 — Factor DSL v1 on Real Legacy Feature Dataset Snapshot` is
recommended. No further Ledger expansion belongs in this task.

## Git / Workspace State

One commit is required with message
`fix(qm2): prevent manifest self-reference`; no amend or push. Final
post-commit checks must prove this Run has no self ChangedFile, is Git
consistent and indexable, and leaves the worktree clean.

## Artifact Index

- Updated Manifest v2 and Ledger Indexer contracts
- Updated AGENTS and Project Memory
- This Report and sibling Manifest v2
- Structured 003L Planner warning and disposable PostgreSQL test evidence
