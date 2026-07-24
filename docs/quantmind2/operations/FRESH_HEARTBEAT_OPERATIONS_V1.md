# Fresh Model Heartbeat Operations v1

Status: project-local operations contract for `QM2-R2-009`.

## Command

```text
TUSHARE_TOKEN=<environment-only> \
python tools/quantmind2/run_autonomous_research_supervisor.py \
  run-fresh-heartbeat
```

The credential is accepted only from `TUSHARE_TOKEN`. It must not be supplied
as a CLI argument, persisted, logged, hashed, or included in any Artifact.

The heartbeat freezes or recovers the two-member model Cohort before its first
Fresh market-data request, collects only the five approved incremental Tushare
endpoints, publishes an immutable first-seen snapshot, applies the frozen
Bundle/model/retraining/strategy contracts, and accumulates label and portfolio
observations. It never promotes a model or changes Registry state.

## Idempotency and recovery

Replaying a completed heartbeat for the same requested-through date returns
the immutable run with all external/computation/write counters at zero.
Interrupted execution resumes from Store-backed cohort, snapshot, training,
prediction, label, strategy, assessment, and heartbeat artifacts.

## Scheduling boundary

`tools/quantmind2/supervisor_fresh_heartbeat.sh` is the project-local scheduler
entry. A system scheduler may invoke it after the A-share close, with a
restricted environment containing `TUSHARE_TOKEN`.

This task does not install, load, bootstrap, or modify `launchd`, cron, or any
other system scheduler. System-level activation requires separate explicit
authorization.
