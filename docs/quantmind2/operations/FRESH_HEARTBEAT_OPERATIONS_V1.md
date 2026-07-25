# Fresh Model Heartbeat Operations v1

Status: automatically active through the immutable Application Support runtime.
The current activation and recovery authority is
`deployments/current-deployment.json`, not repository paths or Artifact ID
ordering.

## Boundary

The scheduler triggers the existing Supervisor `run-fresh-heartbeat` command.
It does not implement market collection, feature computation, monthly
retraining, prediction, label maturity, strategy evaluation, or Cohort state
transitions itself. Those decisions remain in the Store-backed Fresh Cohort
runtime.

The Agent label is `com.quantmind.fresh-model-heartbeat`. It is a current-user
LaunchAgent only. No root service, LaunchDaemon, cron entry, shell-profile
change, dependency installation, power-setting change, Candidate mutation,
Registry write, Promotion, or trading is authorized.

## Current installation status

R2-011 introduced the immutable Application Support runtime and R2-012
activated it. R2-013 requires the final Scheduler revision to bind the current
App, Deployment and second operational run, then atomically publishes the
Current Deployment Pointer. Cold Recovery resolves this explicit pointer and
keeps historical runtime Artifacts separately browsable.

## Schedule

The plist uses local macOS time:

- Monday through Friday at 21:30;
- Monday through Friday at 23:30;
- Tuesday through Saturday at 07:30.

It also sets `RunAtLoad=true`, `ProcessType=Background`,
`LowPriorityIO=true`, and `ThrottleInterval=300`. It does not use KeepAlive.
Sleep can delay a trigger. Shutdown prevents execution; no catch-up while the
machine is off is promised.

## Credential requirement

`TUSHARE_TOKEN` must already be visible to `/bin/zsh -lc`. The value must
never be placed in the plist, repository, command arguments, logs, status,
history, or Artifact Store. Preflight reports only availability.

## Management commands

Use the validated project Python and its existing libomp path:

```text
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py preflight
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py render
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py install
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py load
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py validate
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py status
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py show-next-runs
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py run-now
```

Use the deployed management command for activation and recovery. The legacy
repository-local manager remains a development surface and is not the current
runtime authority.

`validate` is intentionally stricter than `launchctl print`: it requires a
loaded Agent, matching plist/wrapper checksums, and a completed zero-exit
`trigger=launchd` execution. A job that merely entered the GUI domain but
could not reach the heartbeat is invalid.

## Manual immediate run

```text
tools/quantmind2/supervisor_fresh_heartbeat.sh manual
```

The wrapper verifies the Python executable and credential presence, sets the
known libomp search path, acquires the atomic directory lock, invokes the
existing Supervisor, persists a structured summary, and propagates the exit
code. Same-market-date replay must return `exact_replay` or
`no_new_market_data` with zero external/computation/write counters.

## Paths

- Template:
  `deploy/launchd/com.quantmind.fresh-model-heartbeat.plist`
- Installed plist:
  `~/Library/LaunchAgents/com.quantmind.fresh-model-heartbeat.plist`
- Installed wrapper:
  `~/Library/Application Support/QuantMind/bin/supervisor_fresh_heartbeat.sh`
- Lock:
  `~/Library/Application Support/QuantMind/locks/fresh-heartbeat.lock`
- Standard output:
  `~/Library/Logs/QuantMind/fresh-heartbeat.stdout.log`
- Standard error:
  `~/Library/Logs/QuantMind/fresh-heartbeat.stderr.log`
- Current status:
  `~/Library/Logs/QuantMind/fresh-heartbeat.status.json`
- History:
  `~/Library/Logs/QuantMind/fresh-heartbeat.history.jsonl`

Each log rotates at 10 MB and retains at most ten historical files. Rotation
does not delete Artifact Store evidence.

## Concurrency and stale locks

Lock creation is an atomic directory operation. The owner record contains
PID, start time, hostname, and command. A live owner returns
`already_running`; a dead owner is removed as stale. The runtime releases the
lock in `finally`, including exceptions.

## Failure handling and notification

Failures are classified as credential, network, data quality, model, artifact,
contract, or unknown. Three consecutive failures cause one local notification.
The first recovery causes one notification and resets the counter. Candidate
notifications occur only on transitions to `fresh_supported`,
`fresh_rejected`, or `fresh_inconclusive`. Normal replay, no-new-data, and
accumulating status do not notify.

Failures never change Candidate, Lock, model, Label, strategy, Registry, or
Promotion state.

## Fresh evidence gate

Both frozen Candidates remain `fresh_evidence_accumulating` until each has at
least 60 Fresh trading days, five completed holding windows, three rebalance
periods, two monthly retraining events, 90% coverage, and zero PIT violations.
The scheduler cannot relax or reinterpret this gate.

## Pause, resume, and uninstall

Pause:

```text
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py unload
```

Resume after a successful preflight and resolved background-access check:

```text
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py load
```

Uninstall:

```text
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py uninstall
```

Uninstall boots out the Agent and removes the installed plist and wrapper. It
preserves the repository template, operational logs/status, Fresh data,
models, Cohort, and Artifact Store evidence. Add
`--remove-operational-logs` only when local operational logs should also be
deleted; Artifacts are never deleted.

## Recovery and replay

```text
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py cold-recover
python tools/quantmind2/manage_fresh_heartbeat_launchagent.py replay
```

Recovery reconstructs scheduler contract/status, latest operational heartbeat
reference, Candidate statuses, and Cohort status without launchctl, network,
model, prediction, label, strategy, scheduler, Artifact, or Blob writes.
Replay returns the latest immutable operational result with the same zero
mutation contract.

Recovery must not select the last lexically sorted Artifact ID. See
`FRESH_RUNTIME_STATE_CONSISTENCY_AND_RECOVERY_V1.md`.
