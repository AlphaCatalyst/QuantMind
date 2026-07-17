# Artifact Runtime Rollback v1

Status: operational compatibility contract for `QM2-P0-011`

## 1. Runtime Modes

`store_required` is the formal default. `store_preferred` is a bounded migration
mode that imports a validated explicit local artifact after a Store miss.
`legacy_local` is an emergency compatibility mode only.

## 2. Emergency Legacy Mode

Set `QUANTMIND_ARTIFACT_RUNTIME_MODE=legacy_local`, or pass
`--artifact-runtime-mode legacy_local`, only when diagnosing a Store incident or
running explicitly compatible historical tests. Supply every required local
root explicitly. The runtime does not discover old temporary trees.

An artifact produced in this mode is local staging, not a formal publication.
It becomes formal only after Domain validation and successful immutable Store
import. Do not use emergency mode to create new official research conclusions.

## 3. Cache Failure and Deletion

The materialization cache is expendable. Stop affected consumers, delete or
quarantine only the cache (never Store blobs or descriptors), choose a fresh
cache root and resolve again. Cache corruption is already handled by bounded
discard and rematerialization. A cache failure never changes Domain identity.

## 4. Store Failure Behavior

In `store_required`, missing descriptors, invalid descriptors, missing or corrupt
blobs, Domain validation failure and Store import failure are hard errors. The
runtime does not recompute an existing artifact, search a legacy path or report
a local staging result as completed. Preserve the failing evidence and diagnose
the Store before restoring formal execution.

## 5. Operational Rollback Procedure

1. Stop formal publication and record the Store verification failure.
2. Verify that the problem is Store access, not an incorrect Domain ID.
3. If read-only continuity is necessary, explicitly select `legacy_local` and
   identify the exact historical source artifact.
4. Validate that local artifact with the unchanged Domain Validator.
5. Mark all outputs non-formal until Store service is restored and the artifact
   is imported successfully.
6. Return to `store_required`, resolve from an empty cache and reverify Store
   integrity before resuming formal research.

Rollback does not authorize a new Agent Campaign, Optimization, Validation,
Frozen access, mutable Fresh watermark update, GC, or a baseline Inventory
replacement. Existing path-based low-level APIs remain only to make this bounded
procedure and legacy tests possible.

