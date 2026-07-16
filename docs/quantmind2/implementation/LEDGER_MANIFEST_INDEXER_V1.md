# Ledger Manifest Indexer Contract v1

## Scope and authority

This contract covers committed Implementation Run discovery, Manifest v1
parsing, Git evidence, Domain Bundle admission, and writes through the existing
PostgreSQL Repository and Unit of Work. Git blobs and commit graph are the
implementation-record authority. PostgreSQL is a query index. The worktree,
untracked files, report prose, and Manifest commands are never authority.

ADR-0010 requires an explicit runtime binding from a stable logical repository
ID to an absolute local worktree root. The Manifest v1 absolute
`repository_root` is retained only as informational execution evidence.

## Git snapshot input and Run discovery

The caller supplies `repository_id`, `repository_path`, and a ref. The ref is
resolved once to a full commit. All reads use Git objects at that commit;
there is no checkout, fetch, remote access, hook execution, or command from a
Manifest. Runs are discovered only at canonical paths:

```text
docs/quantmind2/implementation/runs/YYYY/YYYY-MM/<run-id>/manifest.json
```

Each manifest must have a paired `report.md` in the same directory. A single
Run filter narrows this discovered set without reading the worktree.

## Parser and Report validation

The parser accepts recognized schema `1.0.0` and `2.0.0`, applies the matching
strict Schema, validates canonical path/Run identity, and performs no repair,
defaulting, prose extraction, or field invention. The report SHA-256 is checked
against the exact committed report bytes. `manifest_payload_hash` is checked
with the existing canonical JSON rule that excludes only that hash field.

## Containing commit and immutable Run files

The containing commit is the sole first-add commit shared by Manifest and
Report. Each path must appear in exactly one history commit, and its blob at the
target ref must equal the containing-commit blob. The containing commit must be
reachable from the target ref. These rules reject later edit, delete/recreate,
split-add, and blob drift.

The declared base commit must exist and be an ancestor of the containing
commit. The declared changed-file set must equal the base-to-containing diff;
declared additions and deletions must agree with Git statuses. Run files must
be ordinary blobs, not symlinks. Declared artifact hashes are checked at the
containing commit.

For v2, the full `integrity.git_changed_paths` must still equal the real diff.
The business ChangedFile comparison excludes only the current Run's canonical
Manifest path from both sides. Report, other Run Manifests, arbitrary JSON and
all unknown extra paths remain mandatory business changes. New self-referential
payloads are rejected by the producer and semantic validator.

A committed v2 payload that already lists its exact `run.manifest_path` as a
ChangedFile is handled by a general compatibility rule: its impossible
before/after hash is not checked, no ChangedFile Domain object is constructed,
and evidence records structured warning
`LEGACY_V2_MANIFEST_SELF_REFERENCE_IGNORED`. This does not waive any other
check, does not change payload hashing, and contains no Run-ID exception.

## Source status and resolved status

A committed Manifest that truthfully recorded `completed_uncommitted` resolves
to Domain `completed_committed` with the containing commit as result. Likewise,
`partial_uncommitted` resolves to `partial_committed`. If a Manifest already
declares `result_commit`, it must equal the containing commit. Failed and
blocked states remain failed/blocked. A running Run does not become successful.
No resolved Run is automatically canonical.

Source status, resolved status, containing commit, and every evidence check are
kept separately. Mandatory evidence gates indexing. Informational evidence is
reported but cannot waive a mandatory failure. There is no force bypass.

## Domain Bundle

The writable bundle separates Task, Run, ChangedFile, ChangedSymbol,
TestExecution, Artifact, ComponentReference, ADRReference, Limitation,
RecommendedTask, and Relationship values. Mapping uses only formal Manifest and
Git fields. Missing business identities, enum semantics, timestamps, or
relations are explicit evidence gaps.

Manifest v1 cannot supply an independent Task status or Task creation time. Its
child arrays also omit Ledger identities and several required semantics. The
current historical v1 Runs therefore validate as Git evidence where applicable
but cannot produce a complete writable Domain Bundle. The Indexer does not
derive those values from prose, array positions, timestamps, paths, or hashes.
A future Manifest version may close the contract gap; this task does not alter
historical Runs.

## Indexing passes and transaction boundaries

Indexing first discovers, parses, validates, and builds every selected Run with
zero database access. Any mandatory Git failure or Domain evidence gap aborts
before opening a database connection.

After admission:

1. unique Tasks are topologically ordered and each is replayed or inserted in
   its own Unit of Work;
2. each Run and all eight child families are passed to the existing atomic
   `record_run_details_atomic` operation in one Unit of Work;
3. Relationships are sorted deterministically and written only after all Runs,
   each through its own Unit of Work;
4. a deterministic result summarizes indexed, replayed, skipped, failed, and
   relationship counts.

Exact existing values are replay. The existing Repository's immutable
conflicts are surfaced as stable Indexer conflicts. Repository batch semantics
prevent a failed child from leaving a partial Run bundle. Relationship writes
cannot begin until every selected Run bundle succeeds.

## CLI

The single entry point is:

```text
python tools/quantmind2/index_implementation_runs.py <plan|validate|status|index> \
  --repository-id <logical-id> \
  --repository-path <absolute-worktree-root> \
  [--ref <commit-ish>] [--run-id <run-id>]
```

`plan` is a dry run and reports all checks and gaps. `validate` exits nonzero if
any discovered Run fails mandatory Git consistency. `status` compares the Git
snapshot with the configured Ledger database. `index` performs the complete
pre-write admission pass before importing persistence or opening a database.
All output is JSON and excludes report content and secrets.

## Error safety and historical backfill

Errors have stable classes and safe context; raw subprocess stderr and database
credentials are not emitted. Git commands use fixed argv templates, disabled
hooks, terminal prompts off, bounded output, and no network operation.

At base `d33f2815b96053c2e0eba1320d666862d0337997`, 16 Manifest v1 Runs are
discovered. Fifteen pass mandatory Git evidence, one fails the declared result
commit rule, and zero can form a complete Domain Bundle because of formal v1
schema gaps. Consequently no historical row was written to the disposable or
production Ledger as a purported backfill. Disposable PostgreSQL verification
uses an explicit complete synthetic Domain Bundle to prove the A3 write,
replay, immutable-conflict, and rollback path; it is test evidence, not history.

## Ledger closure boundary

Parser, trusted binding, Git consistency, admission, Indexer, CLI, and isolated
write-path verification close the Ledger infrastructure implementation stage.
Production deployment/backfill, Project Knowledge API/UI, watcher, webhook,
and daemon remain outside scope. The next task is `QM2-P0-004 — Factor DSL v1
on Real Legacy Feature Dataset Snapshot`.
