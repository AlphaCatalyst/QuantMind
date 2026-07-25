# Immutable Fresh Runtime Operations v1

## Formal deployment

The deployment manager is:

```text
tools/quantmind2/manage_fresh_runtime_deployment.py
```

The formal single-command flow is `deploy`. It performs path and storage
audit, app and environment snapshots, conditional state migration, runtime
configuration, validation, plist installation, launchctl activation, two
launchd kickstarts, Scheduler Status publication, Deployment Status
publication, and cleanup-candidate reporting. It safely uninstalls the Agent
if final acceptance fails.

The individual audit and recovery commands are:

```text
audit
estimate-storage
build-app-snapshot
build-env-snapshot
migrate-state
render-runtime-config
validate-runtime
install-launchagent
activate
run-now
status
rollback
uninstall
cold-recover
replay
```

## Fixed paths

```text
~/Library/Application Support/QuantMind/runtime/apps
~/Library/Application Support/QuantMind/runtime/envs
~/Library/Application Support/QuantMind/runtime/current-app
~/Library/Application Support/QuantMind/runtime/current-env
~/Library/Application Support/QuantMind/state
~/Library/Application Support/QuantMind/config/runtime.json
~/Library/Application Support/QuantMind/logs
~/Library/Application Support/QuantMind/deployments
~/.quantmind2/artifact-store/v1
~/Library/LaunchAgents/com.quantmind.fresh-model-heartbeat.plist
```

The source repository and source venv are deployment inputs only. They are not
formal runtime dependencies after validation.

## Status and verification

`status` reports installation, loaded state, current immutable pointers,
deployment metadata, and local heartbeat status. `validate-runtime` verifies
pointer identity, app commit, relocated environment smoke, Store integrity,
entrypoint checksum, runtime config checksum, and zero protected dependencies.

Operational success requires a completed launchd-triggered zero exit, legal
heartbeat state, immutable Operational Artifact, and a second idempotent
trigger. “Loaded” alone is never reported as healthy.

## Credentials

The LaunchAgent uses `/bin/zsh -lc`. Only credential presence is checked.
Configuration, plist, logs, artifacts, history, and deployment records must
not contain the value or any value-derived metadata.

## Lock, temporary data, and logs

The existing Scheduler lock remains:

```text
state/locks/fresh-heartbeat.lock
```

The deployed wrapper allocates `state/tmp/<UTC-RUN-ID>-<PID>` and removes it
on success, error, or signal. Logs remain below the runtime root and retain the
R2-010 rotation and notification contracts.

## Recovery and rollback

`cold-recover` reads immutable runtime and Fresh evidence without launchctl,
network, copies, migration, or pointer changes. `replay` asserts all declared
mutation counters are zero.

`rollback` boots out and uninstalls the Agent while preserving snapshots,
state, logs, backups, and Fresh artifacts. It marks current deployment
metadata rolled back. It never deletes cleanup candidates.

## Storage

APFS clone is preferred. If clone is unavailable, physical copying is blocked
when estimated allocation exceeds 3 GiB or free space is below 15 GiB.
Automatic snapshot, environment, state-backup, or R2-010 log deletion is
forbidden.
