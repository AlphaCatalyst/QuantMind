# Implementation Report: QM2-P0-002B

## 1. Task Summary

- Task: `QM2-P0-002B — Manifest Parser, Git Consistency and Ledger Indexer`
- Run: `QM2-P0-002B-20260715T090630Z-d33f281`
- Result: completed, pre-commit
- Base: `d33f2815b96053c2e0eba1320d666862d0337997`
- Repository: QuantMind main repository, branch `master`

## 2. Goal

Implement the committed Git Report/Manifest to PostgreSQL Ledger indexing
boundary using strict Manifest v1 parsing, trusted logical repository binding,
Git consistency evidence, complete Domain Bundle admission, and the existing
A3 Repository/Unit of Work.

## 3. Scope

- Manifest v1 parser and stable errors/results.
- Exact committed Report and canonical payload hash validation.
- Explicit logical repository identity to local worktree binding.
- Git snapshot discovery, containing/base/result commit, immutable-file,
  changed-file, mode, and artifact evidence.
- Source-to-resolved Run status without automatic canonical promotion.
- Evidence-only Domain Bundle builder with no field invention.
- Multi-pass, fail-before-write, idempotent Ledger Indexer and JSON CLI.
- ADR-0010, Indexer contract, context/handoff updates, tests, and this Run.

## 4. Explicit Non-goals

No Project Knowledge HTTP API/UI, watcher, webhook, daemon, production database
deployment, historical Manifest rewrite, Factor Lab indexing, TDX, Dataset
Snapshot, DSL, optimization, validation runtime, Factor Registry, LightGBM
change, Qlib change, dependency installation, lockfile update, or push.

## 5. Preflight State

- Working tree: clean.
- Unrelated dirty files: none.
- Git `fsck`: reachable graph valid; only pre-existing dangling blobs reported.
- Docker: 29.6.1; local `postgres:15-alpine` available.
- psql: 15.18.
- Factor Lab: `c83192c2278767e03f008bc39197b1ba33bfb6a9`, clean and read-only.

## 6. What Changed

Added an API-side `indexing` package, a single CLI, ADR-0010, the formal
Indexer contract, four focused test modules, context validation coverage, and
Project Memory updates. Existing Domain, ORM, Mapper, migration, Repository,
and UoW semantics were not changed.

## 7. Why It Changed

Git is the immutable implementation-record authority while PostgreSQL is the
query index. A separate boundary is required to prove that a committed Run is
internally consistent and can populate every required Ledger Domain value
before any database write.

## 8. Files Changed

See the paired Manifest for the exact repository-relative inventory. Changes
are limited to Project Knowledge indexing, its CLI/tests/contracts, Project
Memory, ADR index, bootstrap validation, and this immutable Run.

## 9. Important Classes / Functions / Documents

- `bind_repository`: explicit logical identity/worktree binding.
- `ImplementationManifestParser`: strict schema/path parser without enrichment.
- `GitSnapshot`: bounded committed Git-object reader.
- `ImplementationRunPlanner`: discover and validate all selected Runs first.
- `GitConsistencyService`: mandatory/informational evidence separation.
- `DomainBundleBuilder`: formal-field mapping and explicit evidence gaps.
- `LedgerIndexer`: Task, Run/children, then Relationship passes via A3 UoW.
- `index_implementation_runs.py`: plan, validate, status, and index CLI.
- ADR-0010 and `LEDGER_MANIFEST_INDEXER_V1.md`.

## 10. API Changes

No HTTP API was added. The new Python application boundary and CLI are local
Project Knowledge interfaces only.

## 11. Database Changes

No migration, table, ORM model, constraint, or production data change. A
disposable PostgreSQL 15 container received one complete synthetic bundle for
verification and was removed.

## 12. Configuration / Environment Changes

None. Repository identity/path are required runtime CLI inputs. No absolute
binding configuration, credentials, dependency, or lockfile was committed.

## 13. Runtime Flow

```text
explicit binding + ref
→ committed Run discovery
→ Manifest/Report parse and hashes
→ Git consistency evidence
→ complete Domain Bundle admission
→ topological Tasks
→ each Run plus children atomically
→ Relationships after all Runs
→ deterministic result
```

Plan and validation use Git only. Index validates every selected Run and
requires complete bundles before importing persistence or opening a database.

## 14. Architecture Impact

ADR-0010 freezes the distinction between logical repository identity and local
execution path. The implementation closes the planned Git-to-Ledger indexing
boundary without changing Git authority or adding a second persistence path.
Ledger infrastructure work ends after this task.

## 15. Security Impact

Git operations use fixed argv templates, disabled hooks/prompts/optional locks,
bounded output, no shell, no checkout/fetch/network, and no Manifest command
execution. Errors and JSON output omit report content, raw subprocess stderr,
credentials, and secrets. There is no force bypass.

## 16. Data Lineage Impact

Resolved Runs bind logical repository ID, target ref, containing commit, base,
resolved result, source/resolved status, exact committed paths, and hashes.
Workspace and untracked files are excluded. No Run is promoted to canonical.

## 17. Tests Executed

1. Context bootstrap validator and 19 context tests.
2. Parser, temporary Git, current-history, and in-memory Indexer tests: 11.
3. Relevant Domain/ORM/Mapper/migration/Repository/UoW/context/indexer suite:
   347 passed, 4 opt-in tests skipped, 247 subtests passed.
4. Opt-in disposable PostgreSQL migration, A3 Repository, and Indexer suite:
   7 passed.
5. CLI plan, expected-negative validate, and expected-negative index commands.

The Python 3.12 environment was an existing local QuantMind environment with
pytest 9.1.1, SQLAlchemy 2.0.51, and asyncpg 0.31.0. No package was installed.

## 18. Test Results

All executed positive tests passed. The current-history `validate` command
correctly exits 2 because one historical Run fails mandatory result-commit
consistency. The current-history `index` command correctly exits 2 before a
database import/write because no complete historical Domain Bundle exists.

## 19. Current Historical Compatibility

At base `d33f2815`:

- total Manifest count: 16;
- parsable schema v1 count: 16;
- schema distribution: `1.0.0 = 16`;
- source status: `completed_uncommitted = 15`, `completed_committed = 1`;
- mandatory Git-consistent count: 15;
- complete indexable Domain Bundle count: 0;
- consistency failures: 1 (`QM2-P0-001F-20260714T140245Z-5504bdb`, declared
  result commit differs from containing commit);
- formal v1 gap: all 16 lack independent Task status and Task creation time;
- populated arrays additionally lack child IDs, impacts/relations, and
  structured limitation/recommendation/relationship semantics.

The latest A3 Run passes Git consistency but is not indexable under Manifest v1.
No historical row was written and no full-history backfill is claimed.

## 20. Known Limitations

- Manifest v1 cannot encode a complete Ledger Domain Bundle.
- One immutable historical Run has a result-commit inconsistency.
- Production database deployment/backfill and privilege policy are unverified.
- `status` and successful `index` require the existing SQLAlchemy/asyncpg
  runtime and configured database; plan/validate do not.
- Git blob reads are bounded to 16 MiB per command.
- Pinned SQLAlchemy 2.0.25/asyncpg 0.29 parity remains unverified.

## 21. Compatibility / Migration Notes

No existing schema or record is migrated. A future Manifest version can supply
the missing formal fields; historical v1 is preserved unchanged. The parser
hard-fails unsupported schemas rather than guessing compatibility.

## 22. Rollback Notes

Revert the single QM2-P0-002B commit. No production database rollback is
needed because no production database was accessed. Disposable containers were
removed by test cleanup.

## 23. Remaining Work

Ledger API/UI, production deployment/backfill, and any future Manifest contract
change remain explicit separate work. They are not the recommended next task.

## 24. Recommended Next Task

`QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry`.

## 25. Git / Workspace State and Artifact Index

- Manifest source status: `completed_uncommitted`.
- Result commit: null until the containing commit is created.
- Planned commit message: `feat(qm2): index implementation runs from git`.
- Commit: performed once after final verification; no amend.
- Push: no.
- Artifacts: this report, paired Manifest, ADR-0010, Indexer contract, source,
  CLI, tests, and updated Project Memory listed in the Manifest.
