# Fresh Heartbeat LaunchAgent and Operations v1

Status: accepted repository contract; host activation partial.

## Purpose

The current-user macOS LaunchAgent is a trigger boundary around the existing
Store-backed Fresh Model Cohort heartbeat. It owns scheduling, installation,
single-run exclusion, local status/history, bounded logs, failure
classification, and local notification. It owns no research or model decision.

```text
launchd calendar / RunAtLoad
  -> installed wrapper
  -> scheduler lock and operational envelope
  -> existing Supervisor run-fresh-heartbeat
  -> immutable heartbeat and scheduler operational evidence
```

## Identities

`FreshHeartbeatSchedulerStatusV1` is a content-addressed operational snapshot
with prefix `fhss1_`. It binds label, schedule, template/installed checksums,
loaded/enabled observations, last-run state, next expected run, credential
availability boolean, and repository HEAD at install.

`fresh_heartbeat_operational_run` is a content-addressed operational result
with prefix `fhor1_`. It binds a scheduler status, the immutable
`fresh_model_heartbeat_run`, Cohort/Candidate states, exit and failure class,
and execution counters. It does not claim market-data authority and does not
replace the Fresh Cohort Artifact.

Both kinds preserve secret scanning, file hashes, immutable identity,
lineage, Store integrity, and zero-Promotion validation. The Tushare
`provider_id` invariant applies to market/research Artifacts, not to these
host-operational facts.

## Scheduling contract

The frozen schedule is Monday-Friday 21:30 and 23:30 plus Tuesday-Saturday
07:30 in local time. The Agent uses the current GUI domain, RunAtLoad,
Background process type, low-priority I/O, and a 300-second throttle. KeepAlive
is absent.

## Execution contract

Only one heartbeat may run. The directory lock is atomic, carries owner
evidence, rejects a live owner, removes a dead owner, and is released in a
finally boundary. The scheduler delegates monthly retraining and all other
business decisions to the existing Fresh Cohort runtime.

The local status and history are operational caches. Artifact Store records
are immutable evidence. Cold recovery and replay may read both but perform no
launchctl mutation, network call, model work, business write, scheduler write,
Artifact publication, or Blob publication.

## Credential and notification contract

The credential source is login-shell environment only. Only availability may
be recorded. Token value, hash, prefix, suffix, CLI argument, plist
EnvironmentVariables, or environment dump is forbidden.

Notifications are edge-triggered: third consecutive failure, first recovery,
or a Candidate terminal-status transition. Ordinary accumulating and replay
states are silent.

## Host activation evidence

On 2026-07-25 the repository implementation passed plist, unit, manual
heartbeat, exact replay, Store, cold recovery, and uninstall verification.
The real GUI-domain job reached RunAtLoad but macOS denied or blocked access
to the repository and Python runtime under `~/Documents`. The Agent was
uninstalled and logs/Artifacts preserved.

This is an environment boundary, not a successful production activation.
Copying the virtual environment or business source into Application Support
was deliberately not performed because it would introduce a second deployed
runtime without a separately approved version/update/rollback contract.
