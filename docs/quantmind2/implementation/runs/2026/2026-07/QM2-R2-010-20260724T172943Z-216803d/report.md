# QM2-R2-010 Implementation Report

## 1. Task Result

Partial uncommitted before the final commit. Repository implementation, manual
heartbeat, exact replay, recovery, Artifact integrity and uninstall behavior
are complete. Real automatic activation is blocked by macOS background access
to the repository and Python runtime under `~/Documents`; the nonfunctional
Agent was uninstalled.

## 2. Preflight State

Repository was the QuantMind main repository on `master` at
`216803d23a62fdca81d700a760eba366eb3e8e4a`. The worktree was clean and
there were no unrelated dirty files. The current GUI domain was available,
the login-shell credential availability check passed, and the known Python
environment imported pandas, NumPy, PyArrow, and LightGBM. No secret value,
hash, or fragment was recorded.

## 3. Existing Heartbeat Audit

The implementation reuses
`tools/quantmind2/run_autonomous_research_supervisor.py run-fresh-heartbeat`
and the existing Store-backed Fresh Model Cohort. No second market-data,
feature, retraining, prediction, label, strategy, or Cohort executor was
created.

## 4. Scheduling Architecture

The current-user LaunchAgent is a trigger boundary only. It delegates to an
installed operational wrapper, which delegates to the scheduler service,
which invokes the existing Supervisor heartbeat. Scheduler state and
operational evidence are separate from the immutable Fresh Cohort evidence.

## 5. Launch Context Credential Audit

`/bin/zsh -lc` confirmed credential availability without printing or hashing
the value. The plist has no EnvironmentVariables or token marker. Repository
files, installed plist/wrapper, local structured logs, and new Artifacts were
scanned without finding the credential or forbidden secret markers.

## 6. LaunchAgent Template

`deploy/launchd/com.quantmind.fresh-model-heartbeat.plist` contains the fixed
label, absolute installed-wrapper and working paths, local calendar, RunAtLoad,
Background process type, low-priority I/O, 300-second throttle, and absolute
stdout/stderr paths. KeepAlive and secrets are absent.

## 7. Schedule

The exact 15 triggers are Monday-Friday at 21:30 and 23:30 plus
Tuesday-Saturday at 07:30 in local macOS time. `show-next-runs` derives future
local timestamps from the same frozen schedule.

## 8. Wrapper Script

The repository wrapper uses explicit repository, Python, and libomp paths,
requires an executable interpreter and credential presence, establishes the
working directory, invokes only the management CLI `run-now` path, and
propagates its exit code. Install copies a checksum-identical executable
wrapper into the authorized Application Support directory.

## 9. Concurrency Lock

The scheduler uses atomic directory creation at
`~/Library/Application Support/QuantMind/locks/fresh-heartbeat.lock`.
Owner evidence includes PID, start time, hostname, and command. Live locks
return `already_running`, dead locks are removed, and `finally` releases
acquired locks.

## 10. Log Paths

Operational stdout, stderr, current status and JSONL history live under
`~/Library/Logs/QuantMind`. The structured summary records timing, exit,
market dates, execution counts, Candidate/Cohort status, failure class, and
immutable Artifact references without environment dumps.

## 11. Log Rotation

Each text log rotates at 10 MB and keeps at most ten historical files.
Rotation never touches the Artifact Store.

## 12. Scheduler Status

`FreshHeartbeatSchedulerStatusV1` publishes an immutable `fhss1_` identity
with template/installed checksums, loaded/enabled observations, run/failure
state, next expected run, credential-availability boolean, and repository HEAD
at install. The formal drill published
`fhss1_9bbdf90ca010507ebd48234478710926a0397c1e95e23e8229dac235722f53d2`.

## 13. Failure Handling

Failures classify into credential, network, data-quality, model, artifact,
contract, or unknown categories. Persistent consecutive-failure state is
updated without Candidate or model mutation. The third failure notifies once;
the first subsequent success notifies recovery and resets the counter.

## 14. Local Notifications

Notifications use macOS `osascript` and are edge-triggered only for the third
consecutive failure, recovery, or Candidate transitions to supported,
rejected, or inconclusive. Exact replay, no-new-data, and accumulating status
are silent.

## 15. Install CLI

The CLI supports preflight, render, install, load, unload, uninstall, status,
run-now, validate, show-next-runs, cold-recover, and replay. It uses
`gui/<uid>`, `enable`, `bootstrap`, `bootout`, and `print`; it does not use the
legacy ambiguous `launchctl load` command.

## 16. Installation Result

Plist and installed-wrapper copies were created with matching checksums and the
Agent entered the current GUI domain. RunAtLoad then exposed the host blocker:
macOS denied or blocked background access when execution reached source and
Python paths under `~/Documents`. The Agent was booted out and uninstalled.
Final installed and loaded values are both false.

## 17. launchctl Status

The formal drill observed one loaded GUI-domain job with the correct label and
calendar. The original repository-script attempt exited 126; the installed
wrapper started, but its Python process blocked during interpreter path
initialization under Documents. Final `launchctl` state is absent after safe
uninstall. `validate` now requires a completed zero-exit launchd-triggered run,
so mere GUI-domain presence cannot be reported as operational health.

## 18. Run-now Result

Interactive formal run-now completed against the existing heartbeat
`fmhr1_224de05ef7b20675ec4227eaa0efa487de73918cf0a1a1f55297812927f9fe42`
with `exact_replay`, zero Tushare/model/prediction/Label/strategy work, and
operational Artifact
`fhor1_ebc673206f814ebad5126e56641522f2a475d59a42ecd3956ad16134efd8f5d4`.

## 19. Idempotency Result

The repeated manual run returned the same heartbeat and operational Artifact,
`exact_existing=true`, `new_artifacts=0`, and `new_blobs=0`. All business
execution counts remained zero.

## 20. Fresh Cohort Status

The immutable Cohort remains `fresh_evidence_accumulating` on data through
2026-07-24. No Fresh evidence threshold, model configuration, monthly
retraining rule, Label, or strategy protocol changed.

## 21. Candidate B Status

Candidate
`mhrmc1_6b1a97e5b5a19052387ac06c64c3d1cea998a502542479b47c535b1eb24527c3`
remains `fresh_evidence_accumulating`.

## 22. Candidate C Status

Candidate
`mhrmc1_83272b1d8093eccb6b3823d62fa618685c139497269bde5742006311ce856c23`
remains `fresh_evidence_accumulating`.

## 23. Operations Documentation

The operations guide now documents current partial activation, exact schedule,
commands, paths, credential policy, locking, logs, rotation, failure handling,
notifications, Fresh minimum evidence, sleep/shutdown behavior, pause/resume,
uninstall, recovery, and replay.

## 24. Uninstall Verification

Real uninstall booted out the job and removed both installed plist and wrapper.
Operational logs/status and all Artifact Store evidence were preserved.
Post-uninstall status reports installed=false, installed_wrapper=false, and
loaded=false.

## 25. Artifact Store

Two new kinds are registered:
`fresh_heartbeat_scheduler_status` (`fhss1_`) and
`fresh_heartbeat_operational_run` (`fhor1_`). They retain content identity,
file hashes, secret scan, lineage and zero-Promotion checks, while correctly
not claiming Tushare market-data authority. Store verification reported
healthy, 1996 Artifacts, 6703 Blobs, Missing 0, and Unreferenced 0.

## 26. Cold Recovery

Cold recovery restored scheduler Artifact status, local operational status,
latest operational run, heartbeat reference, both Candidate statuses, and
Cohort status. Launchctl, network, Tushare, model, prediction, Label, strategy,
scheduler, Artifact, and Blob mutation counts were all zero.

## 27. Exact Replay

Explicit replay returned the same `fhor1_` and `fmhr1_` identities with every
declared external/computation/write counter equal to zero.

## 28. Files Added

Added the scheduler package, focused tests, LaunchAgent template, management
CLI, architecture contract, JSON Schema, and this Implementation Run.

## 29. Files Modified

Extended Artifact kind/formal-validation registries, narrowed the market-data
authority invariant for the two host-operational kinds, upgraded the wrapper,
updated operations documentation, Current State schema, and Project Memory.
No Candidate, Lock, Cohort, model, Label, strategy, Registry, Promotion,
dependency, lockfile, shell configuration, Factor Lab, or trading file changed.

## 30. Tests Executed

- Focused scheduler suite: 28 passed with `--no-cov`.
- Fresh Scheduler, Fresh Cohort, Supervisor, Artifact Store/Runtime and Context
  regression: 177 passed.
- Context Bootstrap: 42 checks passed.
- The same 28 assertions passed under default pytest; the process returned
  nonzero only because a one-file run yields 3.58% repository-wide coverage
  below the global 5% threshold.
- `py_compile`, plist lint, JSON parsing, context/schema validation, Store
  verification, secret scans, and `git diff --check` passed.
- Real preflight, render, install, bootstrap, RunAtLoad observation, manual
  run-now twice, cold recovery, replay, bootout, uninstall, and final status
  were executed. RunAtLoad host activation is the one blocked acceptance area.

## 31. Expected vs Actual

Repository scheduling and operations behavior matches the contract. Manual
business execution is idempotent and immutable. Actual host activation differs
from expected because launchd lacks usable background access to the
Documents-hosted source and Python environment. No ungoverned runtime copy or
privacy-setting mutation was used to hide the blocker.

## 32. Implementation Run

Run ID is `QM2-R2-010-20260724T172943Z-216803d`. Manifest v2 accompanies this
report. Pre-commit status is `partial_uncommitted`; the task will create one
independent commit without amend or push. Post-commit Planner is expected to
validate the evidence, while preserving the partial task status.

## 33. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues, Roadmap, their
machine-readable forms, Current State schema, architecture contract and
operations guide record the repository-complete/host-blocked split, immutable
Artifact IDs, unchanged Fresh state, and final uninstalled system state.

## 34. Known Limitations

Automatic scheduling is not active. This Mac requires an explicit,
user-governed resolution for background access to the source and Python
runtime, or a separately designed immutable runtime deployment contract.
Only one Fresh date and zero mature L1 Labels exist. The Artifact Store remains
single-host. No successor task is authorized here.

## 35. Git State After

The task will create one commit with message
`feat(qm2): schedule automated fresh model heartbeats`, without amend or push.
The intended final worktree is clean. System state remains safely uninstalled;
logs and immutable Artifacts remain available for audit.
