# QM2-P0-011 Implementation Report

## Task Summary

`QM2-P0-011 — Artifact-backed Research Runtime Cutover and Recovery Drill`
changes formal QuantMind 2.0 research artifact access from legacy temporary
source directories to verified Artifact Store descriptors and blobs.

## Goal

Make the persistent Artifact Store the runtime authority for large research
artifacts, preserve unchanged Domain identities and validators, provide safe
exact replay/publication, and prove that current research state can be restored
from an empty cache without original temporary artifact roots.

## Scope

- Store-backed reference, runtime policy/context, resolver, publisher, cache,
  legacy guard, Domain adapters, exact replay and state recovery.
- Store-mode CLI seams for Factor Values/DSL, Optimization, Validation/Frozen,
  Registry, Campaign, Fresh Admission and Fresh Validation.
- Store-only recovery, external Campaign replay and exact-existing write drill.
- Runtime/recovery/rollback contracts, strict cutover record/schema, Project
  Memory, tests and this Manifest v2 Run.

## Explicit Non-goals

- No Agent research, new Template, Optimization, Development, Validation,
  Frozen evaluation, Fresh accrual/result, promotion, model, signal or backtest.
- No deletion of original source artifacts, remigration of 65 artifacts,
  replacement Inventory, cloud/distributed backend, database catalog, API/UI,
  Qlib or LightGBM consumer switch.
- No dependency, lockfile, database migration, production database or push.

## Preflight State

- Repository: `quantmind-main`
- Branch: `master`
- Base commit: `890afdde73de0616a7efcf43946b1cbf6329be91`
- Dirty before: false
- Unrelated dirty files: none
- Store baseline: format 1.0.0, 65 artifacts, 280 blobs, healthy, zero
  missing/unreferenced, Inventory `sai_a0b9e618...55d312`
- Fresh state: 0 eligible dates, `awaiting_first_fresh_date`

## Runtime Reality Audit

Before this task, low-level Domain code correctly used explicit paths, while
top-level CLIs/orchestration required local artifact roots and Campaign/Fresh
defaults referenced `/private/tmp`. Exact-existing behavior was local-directory
specific. The detailed per-module findings and retained low-level boundaries
are recorded in `ARTIFACT_BACKED_RUNTIME_V1.md`.

## What Changed

- Added logical Store references that exclude physical roots and materialized
  paths from identity.
- Added `legacy_local`, `store_preferred` and default `store_required` policy.
- Added descriptor/blob verification, atomic descriptor-keyed cache recovery,
  Domain validation, corruption repair and source-aware local path guards.
- Added immutable publication with exact-existing/conflict behavior and Domain
  publishing adapters.
- Added Store replay for current Factor Values, Optimization, Validation,
  Frozen, Registry, Campaign and Fresh Admission artifacts.
- Added read-only `RecoveredResearchState` from Store plus Git Fresh controls.
- Added unified runtime arguments and safe logical summaries to existing CLIs.
- Made Validation Result Store validation self-contained while retaining all
  manifest, payload-hash and embedded Selection identity checks.
- Added strict runtime cutover record/schema, operations documents, Project
  Memory updates and focused/real recovery tests.

## Why It Changed

The persistent Store created by QM2-P0-010 held complete immutable evidence,
but consumers still depended on historical materialization roots. Runtime
authority therefore did not yet match the accepted Store and lineage model.
This task closes that gap without changing research computation or identities.

## Files Changed

The Manifest `changed_files` is the authoritative business inventory. It
contains runtime code, bounded Domain-validator support, CLI seams, tests,
contracts, Project Memory and this Report. This Manifest is intentionally
excluded from business ChangedFiles and included in Git integrity inventories.

## Important Classes / Functions / Documents

- `ArtifactRuntimePolicy`, `StoreBackedArtifactRef`, `ArtifactRuntimeContext`
- `ResolvedArtifact`, `PublishedArtifact`, `RecoveredResearchState`
- `resolve_artifact`, `resolve_or_import_artifact`, `publish_domain_artifact`
- `replay_optimization_study`, `replay_research_campaign`
- `recover_research_state`, `guard_local_path`
- `validate_validation_result_directory`
- `ARTIFACT_BACKED_RUNTIME_V1.md`, `ARTIFACT_RUNTIME_RECOVERY_V1.md`,
  `ARTIFACT_RUNTIME_ROLLBACK_V1.md`

## API Changes

No network API. Python adds the `artifact_runtime` package and Store-backed
Domain adapter functions. Existing path APIs remain available as low-level or
explicit `legacy_local` compatibility boundaries.

## Database Changes

None. No database was connected or migrated.

## Configuration / Environment Changes

Runtime resolution recognizes `QUANTMIND_ARTIFACT_RUNTIME_MODE`,
`QUANTMIND_ARTIFACT_STORE_ROOT` and `QUANTMIND_ARTIFACT_CACHE_ROOT`. Formal CLI
default is `store_required`; default cache is non-authoritative under
`~/.cache/quantmind2/artifacts/v1`. No runtime deployment config or dependency
file changed.

## Runtime Flow

Read: `Domain ID -> descriptor lookup -> descriptor/blob verification -> cache
lookup/atomic materialization -> Domain validation -> consumer`.

Publish: `local staging -> Domain validation through Store import -> descriptor
reload -> Store-backed reference`. A known formal ID is resolved before costly
work and a Store miss never authorizes silent recomputation.

## Architecture Impact

Implements the accepted authority boundary; it does not change frozen
architecture. Domain Artifact, Store reference, runtime materialization and
legacy source remain separate. Git retains controls/project memory while the
Store is authoritative for large immutable research artifacts.

## Security Impact

References and runtime records exclude Store/cache roots, usernames, secrets
and staging paths. Store-mode CLI summaries expose logical IDs and validation
state only. Unknown CLI errors are bounded rather than echoing physical paths.
Frozen Test access rules remain unchanged.

## Data Lineage Impact

No research identity changed. The Store remains 65 artifacts / 280 blobs.
Baseline Inventory, Dataset/Factor/Study/Validation/Frozen/Registry/Campaign/
Admission identities and Fresh Git control identities remain unchanged.

## Store-only Recovery Result

From a new empty cache in `store_required`, the runtime restored one Factor
Values artifact, one Optimization Study, Validation Result, Frozen Result,
canonical Registry, baseline Campaign, external Codex Campaign and Fresh
Admission. All Domain Validators passed and all runtime roots were under the
new cache. No original source artifact root was an input.

Recovered state has 19 Registry entries, seven Optimization Studies and both
Campaigns. Promotion candidate / approved / active counts are 0 / 0 / 0.
Fresh remains 0/60 and `awaiting_first_fresh_date`.

## Exact Replay and Store Invariance

External Campaign `rc_0b13d7f...d9401c` returned exact existing with Agent
calls, Optimization calls and Registry writes all zero. Exact-existing
publication of one Registry, Campaign and Study returned existing references,
new blob count zero and did not change descriptor IDs, artifact count or blob
count. No replacement Inventory was published.

## Tests Executed

- Focused Artifact Runtime and real Store recovery/input preparation: 11 passed.
- Full relevant Store, Dataset, DSL, Optimization, Validation, Registry,
  Campaign, Fresh, Manifest, Indexer and Context regression: 241 passed, 8
  explicit-real-root tests skipped.
- Explicit real Snapshot/Optimization/Validation regression: 9 passed.
- Context Bootstrap: 42 checks passed.
- Official Store integrity: 65 artifacts, 280 blobs, healthy, zero issues and
  zero unreferenced blobs.
- Unified/runtime/domain CLI smoke, JSON parse, `py_compile`,
  `git diff --check`: passed.
- Post-commit Planner validation is mandatory after the containing commit.

## Test Results

All executed pre-commit tests passed. The eight skips in the broad run require
explicit preserved real-artifact roots; the same nine real test cases were run
separately with those roots and passed.

## Known Limitations

- Store and cache are single-host filesystem implementations. Locking is
  process-local; cloud storage, distributed cache/locks and deletion GC do not
  exist.
- Domain execution functions remain path-explicit by design. Only verified
  runtime materializations may feed formal consumers.
- `legacy_local` remains emergency/test compatibility and cannot by itself
  establish formal publication.
- Project Knowledge API/UI, Store metadata database, Qlib/LightGBM cutover and
  production Agent dry run remain separate.
- Fresh has no mature post-lock dates and no Fresh Result.

## Compatibility / Migration Notes

Existing low-level path APIs are retained. Formal CLIs now require explicit
`legacy_local` for old local roots. `store_preferred` may import a validated
explicit local artifact after a Store miss; `store_required` never falls back.

## Rollback Notes

Revert the containing commit to remove the runtime cutover. Operationally,
select `legacy_local` only for an emergency diagnosis and mark all local-only
outputs non-formal. Cache deletion is safe; do not delete Store descriptors or
blobs and do not edit accepted ADRs or research identities.

## Remaining Work

Complete containing-commit Planner verification. Then execute only the bounded
Artifact-backed external Campaign production dry run.

## Recommended Next Task

`QM2-P0-012 — Artifact-backed External Agent Campaign Production Dry Run`.

`QM2-FV-001` remains conditional and forbidden until at least 60 mature
post-lock trading dates exist.

## Git / Workspace State

This Run is produced before its single containing commit. `result_commit` is
null, task status is `completed_uncommitted`, and canonical status is
`noncanonical`. Publication status is resolved from Git after commit.

## Artifact Index

- This Report and Manifest v2.
- Artifact-backed runtime/recovery/rollback contracts.
- Strict runtime cutover record and Schema.
- Runtime package, CLI and focused recovery tests.
