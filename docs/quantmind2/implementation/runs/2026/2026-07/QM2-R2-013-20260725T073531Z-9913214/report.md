# QM2-R2-013 Implementation Report

## Task Summary

`QM2-R2-013 — Fresh Runtime State Consistency and Recovery Completion v1`
closes the five dynamic runtime defects observed after R2-012 without changing
Fresh research behavior.

## Goal

Make environment validation temporary state self-cleaning, bind the final
Scheduler and Deployment revisions, establish explicit canonical runtime
selection, recover the current activation deterministically, and reduce
redaction false positives while preserving credential protection.

## Scope

- Run-scoped environment-validation temporary directories.
- Final Scheduler/Deployment field binding and consistency validation.
- Atomic Current Deployment Pointer.
- Pointer-first, revision-aware Cold Recovery.
- Context-aware runtime diagnostic redaction.
- Four immutable operational completion Artifact kinds.
- Runtime contracts, Project Memory, tools and focused tests.

## Explicit Non-goals

- No Feature or Alpha Agent execution.
- No Factor, model, strategy or combined optimization.
- No Qlib research execution or market-data request before post-commit
  heartbeat verification.
- No Candidate, Fresh Lock, Cohort, Label, Bundle, model, strategy, Registry
  or Promotion mutation.
- No dependency, lockfile, environment, canonical Store or historical
  R2-011/R2-011F/R2-012 evidence change.

## Preflight State

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`.
- Base commit: `9913214826796295f7027756ff2bdf0eb703846f`.
- Workspace dirty before: false.
- Current App commit: `9913214826796295f7027756ff2bdf0eb703846f`.
- Current environment:
  `qmenv1_04c4ddf175ad805e1bac15b9cfef00f9ab686a5a4842b8997d1623a6ddd629f8`.
- Existing fixed tmp child count/hash: `1` /
  `fdb3a96f04f0042973f9ea2ef78416d1665ce6fbb128160496cde07f00081a3e`.
- The fixed child was empty, no Scheduler/Deployment lock existed and `lsof`
  reported no holder.
- Existing pointer referenced Deployment and App but had no final
  `scheduler_status_id`.
- Unrelated dirty files: none.

## Root-cause Audit

1. `validate_environment()` created
   `state/tmp/environment-validation` and had no cleanup boundary. It hosted
   Python, NumPy/Pandas, PyArrow/Parquet, LightGBM, Qlib and SciPy relocation
   smoke and remained after success or failure.
2. Scheduler Status was published before Deployment. Its App ID came from a
   recovered identity payload that intentionally omitted the generated ID.
   It never received second-run idempotency or a Deployment reference.
3. `record_deployment()` wrote the current pointer before a final Scheduler
   revision or cross-Artifact validation existed.
4. Runtime and Scheduler recovery selected the final Store tuple element,
   which is descriptor-path/Artifact-ID order rather than publication order.
5. The redaction guard treated any long token-like string as secret. This
   suppressed safe schemas, paths and public identifiers.

## What Changed

- `runtime_tmp_directory()` creates validated, owner-recorded run children and
  removes the exact child from a `finally` boundary. HUP, INT and TERM become
  controlled exceptions so cleanup executes.
- One-time legacy cleanup accepts only the exact empty fixed directory and
  rejects unsafe, nonempty or lock-referenced paths.
- Final Scheduler Status receives the immutable Deployment Status, second
  operational run and explicit App identity. New fields bind environment,
  program/plist checksums, Deployment and operational IDs.
- `FreshRuntimeStatusConsistencyValidatorV1` rejects cross-Artifact mismatch
  with `RUNTIME_STATUS_CROSS_ARTIFACT_MISMATCH`.
- `current-deployment.json` is a mode-0600 atomic pointer published only after
  consistency succeeds.
- `CanonicalRuntimeArtifactResolverV1` reads identities directly from verified
  Store blobs, prioritizes the explicit pointer and otherwise orders immutable
  revision metadata. Artifact ID is only a final tie-breaker.
- Cold Recovery returns canonical and historical groups, runtime config,
  heartbeat and Cohort without materialization copies or runtime mutation.
- Redaction now uses credential key/assignment context, authorization/Bearer
  context, launchd/Shell environment structure and explicit in-memory known
  secrets. Public commits, hashes, Artifact IDs, schemas, approved paths,
  enums and timestamps are not redacted merely for length.

## Important Symbols

- `runtime_tmp_directory`
- `remove_legacy_environment_validation_tmp`
- `FreshRuntimeStatusConsistencyValidatorV1`
- `CanonicalRuntimeArtifactResolverV1`
- `FreshRuntimeDeploymentService.publish_scheduler_status`
- `FreshRuntimeDeploymentService.publish_current_deployment_pointer`
- `FreshRuntimeDeploymentService.cold_recover`
- `RuntimeDiagnosticRedactionGuardV1`

## Artifact Contracts

- `environment_validation_tmp_assessment`
- `fresh_runtime_status_consistency_validation`
- `canonical_runtime_artifact_resolution`
- `fresh_runtime_hardening_completion`

All are operational evidence with zero Registry and Promotion writes.

## Runtime Flow

`deployment lock → bootout → Git App Snapshot → exact legacy-empty cleanup →
tmp baseline → environment smoke → runtime validation → bootstrap/enable →
first run → second run → Deployment Status → final Scheduler Status →
cross-Artifact validation → atomic pointer → Cold Recovery → tmp equality →
completion Artifacts`.

Failure restores the prior App/environment pointers, runtime/public config,
plist, Current Deployment Pointer and prior loaded Agent.

## Architecture Impact

No research architecture boundary changes. Runtime activation now has an
explicit machine-local authority and immutable consistency/resolution evidence.
Content identity remains separate from publication order.

## Security Impact

Positive. Generic length-based redaction is removed, but credential
assignments, Authorization/Bearer values, environment blocks/dumps and
in-memory known secrets remain protected. No secret value, hash, length or
fragment is persisted.

## Data Lineage Impact

Operational lineage only. Fresh research identities and market/model lineage
are unchanged unless a post-commit heartbeat naturally observes new official
data under the frozen protocol.

## Tests Executed Before Commit

- Targeted Fresh Runtime/Scheduler suite: `82 passed`.
- Relevant Artifact Store/Runtime/Campaign/Fresh/Context suite:
  `227 passed`.
- JSON parse, Context Bootstrap, `py_compile`, `plutil`, secret-canary,
  pointer rollback, tmp success/failure/signal cleanup and `git diff --check`
  are included in the final verification ledger.

## Post-commit Verification Contract

The containing commit must be deployed through `hardened-cutover` with this
Run ID. Completion requires two real LaunchAgent zero-exit runs, second-run
idempotency, equal tmp child inventories, final Scheduler/Deployment
consistency, pointer-first Cold Recovery, unchanged Fresh identities, healthy
Store with zero missing/unreferenced Blobs, zero secret matches and Planner
validation with no evidence gap or warning.

These dynamic host facts cannot be placed truthfully into this pre-commit Git
report. Their immutable Store Artifacts and Current Deployment Pointer are the
authority.

## Known Limitations

- Historical session content remains outside repository control; credential
  rotation remains user-governed.
- Runtime snapshots and Current Deployment Pointer are single-host state.
- The official Factor Lab source path existed during preflight but contained
  zero files. This task did not modify it.

## Compatibility and Rollback

Existing App and environment snapshots remain immutable. Historical Scheduler
and Deployment Artifacts remain browsable. Older Scheduler payloads retain
backward-compatible optional fields. Rollback restores the prior pointers,
config, plist and Agent without deleting any Artifact.

## Git State

- Pre-commit task status: `completed_uncommitted`.
- Result commit: null until the containing commit exists.
- Commit policy: one new commit; no amend, reset, rebase or push.
- Suggested commit: `fix(qm2): complete fresh runtime state hardening`.
