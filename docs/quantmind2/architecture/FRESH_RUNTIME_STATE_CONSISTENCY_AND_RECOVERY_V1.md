# Fresh Runtime State Consistency and Recovery v1

Status: accepted implementation contract for `QM2-R2-013`.

## Boundary

This contract closes runtime-state and recovery gaps only. It does not change
Fresh Candidates, Locks, Cohort membership, dates, Labels, Feature Bundles,
LightGBM, strategy, evidence gates, Registry state, or Promotion state.

## Environment validation temporary directory

`FreshRuntimeDeploymentService.validate_environment` owns the Python,
PyArrow, LightGBM and Qlib relocation smoke. Every invocation uses one
validated child below `state/tmp` named with the validation purpose, process
ID and random run identity. Owner metadata and user-only permissions use the
same runtime temporary-directory contract as heartbeat runs.

The exact child is removed on success, exception, HUP, INT and TERM. The old
global `state/tmp/environment-validation` path is never created. A historical
instance may be removed once only when it is a real empty directory and no
Scheduler or Deployment lock references it; other tmp children are untouched.

## Runtime activation state

The final `FreshHeartbeatSchedulerStatusV1` is generated from one immutable
Deployment Status and the second operational run. It binds source commit, App
Snapshot, environment fingerprint, runtime/program/plist checksums,
loaded/enabled state, exit and run times, idempotency, tmp cleanup, diagnostic
guards, Deployment Status, operational run and latest heartbeat.

`FreshRuntimeStatusConsistencyValidatorV1` compares the Scheduler and
Deployment source commit, App Snapshot, runtime checksum, idempotency, tmp
cleanup and redaction count. It also verifies the Scheduler's explicit
Deployment reference. A mismatch is
`RUNTIME_STATUS_CROSS_ARTIFACT_MISMATCH` and cannot be healthy.

## Current Deployment Pointer

`deployments/current-deployment.json` is the non-secret machine-local
authority for the current activation. It contains only the final Deployment
Status ID, final Scheduler Status ID, App Snapshot ID, source commit,
environment fingerprint, runtime checksum and activation time. It is written
atomically with mode `0600` only after final status consistency succeeds.
Failure preserves the prior pointer.

## Canonical recovery

`CanonicalRuntimeArtifactResolverV1` never treats content identity as time.
It resolves the explicit Current Deployment Pointer first. Only when that
pointer is absent may it order immutable revisions by published/deployed/
created time and revision number; Artifact ID is a final deterministic
tie-breaker only. Filesystem mtime is not authority.

Cold Recovery returns separate `canonical_current_artifacts` and
`historical_artifacts`, the runtime config, current heartbeat and Fresh Cohort.
It verifies Scheduler/Deployment consistency and performs no launchctl call,
environment read, network call, copy, symlink switch, tmp deletion, business
write, Artifact publication, or Blob publication.

## Context-aware redaction

Runtime diagnostics redact credential assignments, Authorization headers,
Bearer values, launchd environment blocks, full shell-environment dumps and
explicit in-memory known-secret values. Redaction records only allowed
categories and counts.

String length alone is not secret evidence. Git commits, SHA-256 values,
registered Artifact IDs, schema/type names, approved runtime paths, enum
states, timestamps and UUIDs remain visible outside a secret-key context.
Secret values, hashes, lengths and fragments are never persisted.

## Completion evidence

The immutable completion graph adds:

- `environment_validation_tmp_assessment`;
- `fresh_runtime_status_consistency_validation`;
- `canonical_runtime_artifact_resolution`;
- `fresh_runtime_hardening_completion`.

The final completion object binds the committed source, current App,
Deployment, Scheduler, consistency result, resolution result and equal tmp
child inventories. Operational truth remains external to the pre-commit
Implementation Manifest.
