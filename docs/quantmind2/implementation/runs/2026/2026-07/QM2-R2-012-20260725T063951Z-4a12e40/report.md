# QM2-R2-012 Implementation Report

## Task Summary

`QM2-R2-012 — Fresh Runtime Cleanup and Diagnostic Redaction Hardening v1`
implements the remaining runtime-hardening work identified by R2-011F.

## Goal

Guarantee exact per-run temporary cleanup, restrict operational diagnostics to
safe fields, redact secret-like material at runtime boundaries and provide a
rollback-safe immutable App cutover that reuses the existing environment and
canonical Artifact Store.

## Scope

- Deployed heartbeat shell lifecycle and signal handling.
- Temporary-directory ownership, cleanup and bounded stale cleanup.
- Safe LaunchAgent and credential diagnostics.
- Runtime redaction guard.
- Five operational hardening Artifact types.
- Deployment-locked immutable App cutover and rollback.
- Targeted unit/integration tests and Project Memory.

## Explicit Non-goals

- No Agent, Factor, model, optimization, Qlib or strategy research.
- No Candidate, Lock, Cohort, Registry or Promotion state change.
- No market-data request or dependency change.
- No environment or canonical Store replacement.
- No credential readback, persistence, hashing or automatic rotation.
- No rewriting R2-011 or R2-011F.

## Preflight State

- Repository: QuantMind main repository.
- Branch: `master`.
- Base commit: `4a12e400c24c45d6846c93e447683f5747a0cbef`.
- Workspace dirty before: false.
- Existing App Snapshot: `eeed072ecda43ae1894d61e76fc099863a58a306`.
- Existing environment fingerprint:
  `qmenv1_04c4ddf175ad805e1bac15b9cfef00f9ab686a5a4842b8997d1623a6ddd629f8`.
- Canonical Store: `~/.quantmind2/artifact-store/v1`.

## Root Cause

The entrypoint registered an `EXIT` trap and then invoked the heartbeat with
`exec`. Process replacement removed the shell that owned the trap, so normal
completion could not run cleanup.

## What Changed

- The shell now waits for a child process, preserves its return code and runs
  exact cleanup on normal and signal paths.
- Runtime tmp creation validates containment, run identity, permissions and
  owner metadata. Stale deletion requires a dead owner, age over 24 hours and
  no live Scheduler-lock reference.
- A dead Scheduler lock is removable only when both PID and runtime run ID
  match the terminated child.
- Launchctl output is parsed in memory and reduced to the frozen whitelist.
  Parse failure returns `diagnostic_parse_failed` without raw fallback.
- Runtime text crossing operational boundaries uses a redaction guard for
  credentials, authorization values, environment assignments and token-like
  values. Secret hashes are not retained.
- A deployment lock protects App pointer/config/plist cutover. Failure restores
  the old App, environment pointer, config and plist and reboots the old job.

## Public Commands

- `safe-status`
- `safe-launchctl-status`
- `safe-credential-check`
- `safe-runtime-diagnostics`
- `cleanup-stale-runtime-tmp`
- `hardened-cutover --implementation-run-id <RUN_ID>`

No raw-environment or raw-launchctl diagnostic option exists.

## Artifact Contracts

- `fresh_heartbeat_tmp_cleanup_assessment`
- `runtime_diagnostic_whitelist`
- `runtime_diagnostic_redaction_guard`
- `historical_session_diagnostic_exposure_record`
- `fresh_runtime_hardening_status`

The final hardening status binds this Implementation Run ID to the committed
source, App Snapshot, reused environment and runtime verification.

## Historical Exposure Governance

R2-011 did expose a runtime diagnostic in the historical interactive session.
This report does not repeat the content, claim platform deletion or rotate a
credential. Repository, runtime config and Artifact persistence are false;
rotation remains user-governed.

## Tests Executed Before Commit

- Targeted runtime deployment, scheduler and hardening suite:
  `70 passed, 0 failed, 0 skipped`.
- `py_compile` for changed Python runtime modules: passed.
- Isolated shell success/failure/SIGTERM/SIGINT tests: included above.
- App cutover success and injected-failure rollback tests: included above.

## Security Impact

Positive. Raw launchctl/environment output is prohibited at public diagnostic
boundaries. Canary material is replaced by a fixed marker, with only category
and count retained.

## Data Lineage Impact

No research-data lineage changes. New objects are operational governance and
deployment evidence only. Fresh business objects remain immutable unless a
real scheduled heartbeat sees naturally new official data under the frozen
protocol.

## Compatibility

The existing environment, Store, schedule, wrapper command, heartbeat service
and Fresh research protocol remain in place. Scheduler and Deployment Status
schemas add backward-compatible hardening fields with safe defaults.

## Rollback

The old App Snapshot is retained. The cutover transaction restores the prior
App and environment pointers, runtime config, public config and plist, then
bootstraps the prior LaunchAgent if any post-bootout step fails.

## Post-commit Verification Contract

After the containing commit, run `hardened-cutover` with this Run ID. The
external `fresh_runtime_hardening_status` and current Deployment Status are
authoritative for the new commit, two real LaunchAgent runs, tmp cleanup,
idempotency, Store integrity and rollback availability. These mutable host
facts are deliberately not forged into this pre-commit Git report.

## Known Limitations

- Historical interactive-session content cannot be deleted or proven deleted
  by repository code.
- Credential rotation is a user-governed action.
- Host activation is machine-local; Git records the implementation contract,
  while immutable operational Artifacts record activation truth.

## Git State

- Task status at manifest creation: `completed_uncommitted`.
- Commit policy: one new commit; no amend, reset, rebase or push.
- Suggested commit:
  `fix(qm2): harden fresh runtime cleanup and diagnostics`.
