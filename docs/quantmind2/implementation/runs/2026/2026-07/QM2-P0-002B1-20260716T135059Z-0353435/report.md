# Implementation Report: QM2-P0-002B1 — Manifest v2 Producer and Forward Indexability

## Task Summary

Implemented the default Manifest v2 production and ingestion contract so a
new Implementation Run can losslessly construct every current Ledger Domain
family. Historical Manifest v1 files remain byte-for-byte unchanged.

## Goal

Close the future Ledger evidence gap from structured Run production through
Git consistency, complete Domain Bundle construction, PostgreSQL indexing, and
exact replay.

## Scope

- Manifest v2 Schema, example, protocol, producer, and report template.
- v1/v2 parser routing, v2 integrity/Git checks, and complete Bundle mapping.
- Bootstrap/context defaults and Project Memory updates.
- Temporary Git and disposable PostgreSQL verification.
- This B1 Run as a Manifest v2 self-hosting record.

## Explicit Non-goals

- No historical Manifest rewrite or inferred backfill.
- No database schema, migration, dependency, lockfile, API, UI, watcher,
  daemon, business data, factor, model, portfolio, or backtest implementation.
- No production database connection or deployment.
- No Factor Lab modification.

## Preflight State

- Repository ID: `quantmind-main`
- Execution path: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `0353435a3c1fb4b1469a5ab32462a1a010999872`
- Dirty before: no
- Unrelated dirty files: none
- Historical Implementation Run files dirty before: none
- Factor Lab root existed, but lacked `.git`; expected branch/commit/clean state
  could not be reverified. Its source content was treated as read-only and
  bounded by a before/after digest.

## Existing Production Reality

No formal Manifest producer existed before B1. New Runs were assembled by
Codex from the v1 Schema, template, and AGENTS protocol. The v1 payload hash
removed its top-level self-hash and used sorted compact UTF-8 JSON. Parser and
Git consistency accepted v1, but 0 of 17 historical v1 Runs could supply a
complete Domain Bundle; 16 passed mandatory Git evidence and QM2-P0-001F kept
its result-commit mismatch.

## What Changed

- Added strict Manifest v2 and an entirely recomputable example.
- Added the formal `new`, `finalize-payload`, and `validate` producer commands.
- Added canonical v2 integrity and version checks.
- Routed v1 and v2 independently through Parser, Git evidence, and Bundle.
- Mapped Task, Run, Relationship, four Detail, two Reference, and two
  Annotation families without report prose or array-position identities.
- Updated future Codex protocol, Bootstrap, context, Handoff, issues, roadmap,
  and component evidence.
- Added real temporary-Git and isolated-PostgreSQL coverage.

## Why It Changed

Continuing to emit v1 would leave every future Run non-indexable despite the
existing Ledger Repository and Indexer. v2 supplies the missing structured
facts while retaining Git as committed-byte authority and preserving v1
history.

## Files Changed

The Manifest `integrity.git_*_paths` inventory is the exact Git path authority.
Structured `changed_files` records identify the principal semantic changes;
the Manifest file omits its own byte hash because that would be recursive.

## Important Classes / Functions / Documents

- `validate_manifest_v2_payload`
- `finalize_manifest_v2_payload`
- `canonical_manifest_v2_payload_hash`
- `ImplementationManifestParser.parse`
- `GitConsistencyService.analyze`
- `DomainBundleBuilder.build_source_v2`
- `create_implementation_manifest.py`
- `IMPLEMENTATION_MANIFEST_V2.md`

## Runtime Flow

```text
structured input -> producer new -> pre-commit finalize -> Schema/Domain validate
-> Git commit -> trusted binding -> Git consistency -> resolved Run
-> complete Domain Bundle -> existing LedgerIndexer/UoW -> PostgreSQL
```

The producer never sets a result commit. The Indexer resolves the containing
commit and committed status from Git.

## Architecture Impact

Manifest v2 becomes the default forward Implementation Run exchange protocol.
Logical repository ID is independent of execution path. The accepted ADRs,
frozen Domain, Mapper, ORM, migration, Repository, and UoW shapes are unchanged.
The Ledger infrastructure stage is closed after B1; API/UI work is not resumed.

## API Changes

None.

## Database Changes

None. Migration 0001 and all table shapes are unchanged. Only disposable
PostgreSQL 15 was used for tests.

## Configuration / Environment Changes

None. No dependency or lockfile was modified.

## Security Impact

The producer rejects unsafe repository artifact paths, requires explicit URI
kind, does not execute recorded test commands, and does not infer logical
repository identity from a local path. No secrets are stored in this Run.

## Data Lineage Impact

No market/research data lineage changed. Implementation lineage now records
logical repository identity, Mapper/identity versions, stable child IDs,
typed references/annotations, and canonical hashes.

## Tests Executed

1. `python tools/quantmind2/validate_context_bootstrap.py --json`
2. `python -m pytest backend/services/tests/test_project_knowledge_manifest_v2.py backend/services/tests/test_project_knowledge_manifest_parser.py backend/services/tests/test_project_knowledge_git_consistency.py backend/services/tests/test_project_knowledge_ledger_repository_contract.py backend/services/tests/test_quantmind2_context_bootstrap.py -q -o addopts=''`
3. `python -m pytest backend/services/tests/test_project_knowledge_*.py backend/services/tests/test_quantmind2_context_bootstrap.py -q -o addopts=''`
4. `QM2_LEDGER_POSTGRES_INTEGRATION=1 python -m pytest backend/services/tests/test_project_knowledge_ledger_postgres_integration.py backend/services/tests/test_project_knowledge_ledger_postgres_repository.py backend/services/tests/test_project_knowledge_ledger_backfill_postgres.py -q -o addopts=''`
5. `git diff --check`

## Test Results

- Bootstrap: passed, 38 checks.
- Targeted v2/parser/Git/contract/context: 104 passed, 10 subtests passed.
- Full Project Knowledge regression: 363 passed, 7 skipped, 247 subtests
  passed. The skipped tests were explicit opt-in PostgreSQL cases and were
  separately executed by command 4.
- Disposable PostgreSQL integration: 8 passed; containers cleaned up.
- Git whitespace check: passed.
- Post-commit B1 self-plan and isolated database indexing are final gates that
  necessarily run against the containing commit; their evidence is reported in
  the final task response rather than retroactively mutating this Run.

## Expected vs Actual

- Expected v2 lossless Bundle: actual all 11 families, no evidence gaps.
- Expected path independence: actual trusted ID binding succeeds with a
  different recorded execution path; mismatched ID fails.
- Expected exact replay: actual replayed with no duplicate rows.
- Expected conflict atomicity: actual immutable conflict preserved prior data
  and wrote no partial replacement.
- Expected v1 compatibility: actual parser and historical statistics unchanged.

## Known Limitations

- Historical v1 Runs remain incomplete and are not repaired.
- QM2-P0-001F remains Git-inconsistent.
- No production Ledger database is migrated or populated.
- Project Knowledge API/UI, watcher, webhook, and daemon do not exist.
- The Factor Lab `/tmp` root lacks Git metadata in this environment, so its
  expected HEAD/branch and Git-clean state could not be confirmed; source-byte
  digest stability is the available boundary evidence.
- Pinned SQLAlchemy/asyncpg parity and CI scheduling remain unconfirmed.

## Compatibility / Migration Notes

v1 parsing and payload hashing remain unchanged. No v1 file is upgraded.
Consumers must explicitly route `2.0.0`; unsupported Schema, Mapper, identity,
or canonicalization versions fail closed.

## Rollback Notes

Revert the single B1 commit. No database rollback, dependency rollback, data
migration, service restart, or Factor Lab restoration is required.

## Remaining Work

Only the approved TDX provider reality audit is recommended. Ledger API/UI and
historical repair are not continued by this handoff.

## Recommended Next Task

`QM2-P0-003 — TongDaXin Provider Reality Audit and Dataset Snapshot Entry`

## Git / Workspace State

The source Manifest records the true pre-commit state:
`result_commit=null`, `completed_uncommitted`, dirty after yes, canonical no.
The containing commit and resolved committed state are Git-derived after the
single required commit. No push is performed.

## Artifact Index

- This report: stable artifact `artifact-qm2-p0-002b1-report`
- Manifest v2: stable artifact `artifact-qm2-p0-002b1-manifest`
- Manifest v2 Schema and example
- Manifest v2 protocol and producer
- Test evidence recorded by stable TestExecution IDs in the Manifest
