# Immutable Fresh Runtime Deployment v1

## Status and scope

Status: accepted implementation contract for `QM2-R2-011`.

This contract resolves only the host execution boundary exposed by
`QM2-R2-010`. It does not change the Fresh Cohort, Candidate, Lock, Label,
Bundle, model, seed, validation, strategy, Registry, Promotion, or schedule.
The existing Supervisor heartbeat and Fresh Heartbeat Scheduler remain the
only business and scheduling executors.

## Runtime boundary

The only formal runtime root is:

```text
~/Library/Application Support/QuantMind
```

It contains versioned Git app snapshots, versioned Python environment
snapshots, atomic current pointers, public runtime configuration, writable
checkpoints and temporary files, logs, and deployment history. The LaunchAgent
may additionally use its plist below `~/Library/LaunchAgents`. It must not
require `Documents`, `Desktop`, `Downloads`, Mobile Documents, or iCloud Drive.

The Artifact Store remains the existing single canonical writable Store at
`~/.quantmind2/artifact-store/v1`. It is already outside protected paths, so
`QM2-R2-011` records `relocation_required=false`; it does not create a second
writable Store.

## Dependency audit

`FreshRuntimePathAuditV1` records source, interpreter, base interpreter,
site-packages, LightGBM, libomp, PyArrow, Artifact/Blob Store, market-data,
checkpoint, temporary, and log dependencies. Each row distinguishes read and
write requirements, protected-directory location, and relocation need.

Pre-deployment protected dependencies are evidence that must be relocated.
Formal runtime validation independently requires the effective dependency
count to be zero and fails with `PROTECTED_RUNTIME_PATH_DEPENDENCY`.

## App snapshot

An app snapshot is extracted only from `git archive <commit>` into:

```text
runtime/apps/<full-commit>
```

The snapshot has no `.git`, worktree-only content, cache, local environment,
or logs. Its sorted file inventory, source bundle hash, tracked file count,
entrypoint checksums, and commit are recorded by
`FreshRuntimeAppSnapshotV1`. Write bits are removed after validation. The
`runtime/current-app` symlink is switched with atomic rename; prior snapshots
are retained.

## Environment snapshot

`qmenv1_<sha256>` binds Python version and architecture, critical package
versions, the installed-distribution inventory hash, and checksums of
LightGBM, libomp, and PyArrow native libraries. A protected source venv is
deployed once to:

```text
runtime/envs/<environment-fingerprint>
```

APFS clone is preferred; `ditto` is the bounded fallback only when the storage
gate permits. No dependency resolver or network installer is allowed.
Validation requires relocated `sys.prefix`, NumPy/Pandas/PyArrow/LightGBM/
Qlib/SciPy imports, Parquet write/read, a two-round LightGBM train/predict
smoke, and matching arm64 architecture. The validated tree becomes read-only
and `runtime/current-env` switches atomically.

## Runtime configuration

`config/runtime.json` conforms to
`fresh-runtime-config-v1` and contains only public paths and immutable
identities. The file is mode `0600`; it never contains credentials. The
loader rejects missing fields, invalid identity forms, secret markers, and
protected required paths.

The deployed entrypoint obtains `TUSHARE_TOKEN` only through `/bin/zsh -lc`,
checks presence without exposing value metadata, creates one run-specific
directory below `state/tmp`, and delegates to the existing scheduler. The
scheduler retains lock ownership and invokes the existing Supervisor
heartbeat.

## LaunchAgent

The label and 15 frozen local-calendar triggers remain:

```text
com.quantmind.fresh-model-heartbeat
Monday-Friday 21:30 and 23:30
Tuesday-Saturday 07:30
```

The installed plist references only Application Support paths for its
entrypoint, working directory, and logs. Loaded state is insufficient:
formal activation requires bootstrap, print, kickstart, a completed
launchd-originated zero-exit run, a legal heartbeat status, an Operational
Artifact, zero protected dependencies, and a healthy Scheduler Status.

The second launchd kickstart on the same market date must be exact replay or
no-new-data with zero Tushare, training, prediction, Label, strategy,
Artifact, and Blob additions.

## State, rollback, and cleanup

State relocation occurs only if the canonical Store is protected. A migration
would require exclusive locking, verified clone/copy, Store integrity, a
read-only source backup, and exactly one writable canonical Store. The current
deployment does not relocate the already external Store.

Rollback boots out the Agent and preserves all app/environment snapshots,
state, backups, logs, and Fresh evidence. Automatic cleanup is forbidden.
Candidates are merely reported with allocated bytes, last access, and
rollback dependency.

## Immutable evidence

The Artifact Store owns:

- `fresh_runtime_path_audit` (`frpa1_`);
- `fresh_runtime_app_snapshot` (`fras1_`);
- `fresh_runtime_environment_snapshot` (`fres1_`);
- `fresh_runtime_state_migration` (`frsm1_`);
- `fresh_runtime_deployment_status` (`frds1_`).

Cold recovery reads these artifacts, runtime configuration, Scheduler Status,
Cohort, and Heartbeat without launchctl, network, copies, migrations, or
pointer writes. Exact replay adds no Artifact, Blob, scheduler, business, or
system mutation.

## Security and authority

No token, token length/hash/fragment, shell environment, password, Git/SSH
credential, or private key is persisted. Source Git commit, environment
fingerprint, runtime config checksum, plist checksum, wrapper checksum, and
Artifact lineage provide the deployment identity. Git remains code authority;
the Artifact Store remains immutable operational evidence; the external Store
remains market/research state authority.
