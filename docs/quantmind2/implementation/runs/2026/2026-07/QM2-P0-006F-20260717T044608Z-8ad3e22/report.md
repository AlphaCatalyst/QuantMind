# QM2-P0-006F Implementation Report

## 1. Task Summary

Recorded an immutable evidence correction for one manually mistyped
`before_hash` in the QM2-P0-006 Manifest. The original Run remains unchanged
and Git-inconsistent. Status at report generation is
`completed_uncommitted`.

## 2. Goal

Preserve the historical error while adding independently verifiable Git-blob
evidence, a strict correction Artifact, and an explicit `corrects`
relationship that can be indexed and replayed.

## 3. Scope

The scope is the correction JSON and schema, correction-specific validation,
Project Memory, isolated PostgreSQL index/replay proof, and this Implementation
Run.

## 4. Explicit Non-goals

No edit of the target Run, Factor Validation production code, Dataset, Label,
Factor Values, Validation Result, Candidate Selection, Frozen Result, Registry,
database schema/migration, API/UI, dependencies, lockfile, Factor Lab, amend,
push, or production database.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch/base: `master` / `8ad3e22575f9339955dd5fde4255269d87e9b138`
- Dirty before: no; unrelated dirty files: none.
- Target Run report SHA-256:
  `2e622a9c90fbd7b7c7f75a01a28ea0343daafa72fd6494e031a1c5eb4a92b5b0`.
- Target Run Manifest SHA-256:
  `e3e07381c6e4ca47267ae639de8d74422470f1a91cf0b0b8c017ef31157eea4e`.
- Factor Lab content digest v1 before:
  `8d06c49e622b8d8031eb6283caa4e1d2df81642a108e3b0d1650d01b845c9aee`
  over 18 non-cache files.

## 6. What Changed

Added a strict evidence-correction schema and Artifact, correction tests, a
disposable PostgreSQL correction index/replay test, Project Memory updates,
and this Run. The existing context validator now checks the Artifact against
the raw base Git blob and immutable target Run hashes.

## 7. Why It Changed

The QM2-P0-006 Manifest recorded
`11db9e00e1babe3ee77c18b9a38a29461c3afba33519e401b3f321eadf07ae4a`
for `handoff_v1.schema.json`. Raw bytes from the declared base commit hash to
`11db9e00e1aabe3ee77c18b9a38a29461c3afba33519e401b3f321eadf07ae4a`.
Immutable history prohibits patching the old Manifest, so the correction is a
new Artifact and Run.

## 8. Files Changed

The Manifest records every repository-relative path and exact before/after
SHA-256. The old QM2-P0-006 report and Manifest are absent from this Run's
changed files.

## 9. Important Classes / Functions / Documents

- `implementation_evidence_correction_v1.schema.json`
- `QM2-P0-006-evidence-correction-v1.json`
- `test_implementation_evidence_correction.py`
- `test_real_006f_correction_indexes_relationship_artifact_and_replays_exactly`
- `validate_bootstrap` correction invariants

## 10. API Changes

None.

## 11. Database Changes

None. Migration `0001` is exercised only in a disposable PostgreSQL 15
container; no production database is contacted.

## 12. Configuration / Environment Changes

None. No package was installed and no dependency or lock file changed. Tests
use the existing Python 3.12 environment with pytest 9.1.1, SQLAlchemy 2.0.51,
asyncpg 0.31.0, pandas 2.3.3, and pyarrow 24.0.0.

## 13. Runtime Flow

Read target base Git blob as raw bytes -> compute SHA-256 -> validate strict
correction JSON -> preserve old Run -> create `corrects` relationship -> plan
the new Run -> index a target dependency plus Correction Run in disposable
PostgreSQL -> exact replay -> cleanup.

## 14. Architecture Impact

Conforms to ADR-0005, ADR-0007, and ADR-0010: Git remains authoritative,
accepted history is not rewritten, and PostgreSQL remains a query index. This
adds no generalized correction service or new architecture.

## 15. Security Impact

The Artifact contains only repository-relative paths, public identities and
hashes. It rejects additional properties and contains no secret, absolute
runtime path, command payload, validation metric, or promotion authority.

## 16. Data Lineage Impact

None. Dataset
`vd_1ac71a8b1bab36f7d4304fe13c14cbb936f073d0426b76e0c73096a819c3ed62`,
Validation Result
`fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0`,
Selection
`fvs_f679a63089f076c11315f522f4d59dc8248731863ec6aafc02b70c9762819e9c`,
and Frozen Result
`fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787`
are references only and remain byte-for-byte unchanged.

## 17. Tests Executed

- Historical Planner reproduction: exit 2, zero validated/indexable, sole
  mandatory failure `changed_file_hashes`.
- Correction tests before commit: 2 passed, 1 explicitly skipped because Git
  containing-commit evidence does not exist until commit.
- Full related pre-commit regression: 153 passed, 1 same explicit skip.
- Context unittest: 21 passed; Context Bootstrap: 39 checks passed.
- First disposable PostgreSQL candidate run: 4 passed, 1 test-only failure
  caused by comparing the Repository's tuple result with a list. The assertion
  was corrected to the public tuple contract; no production code changed.
- Final candidate and post-commit Git/PostgreSQL results are recorded in the
  Manifest test executions and final task response.

## 18. Test Results

All executable pre-commit assertions passed. The only pre-commit skip is the
deliberate committed-Git boundary; it must become a real passing test after the
single task commit. The old Run failure remains reproducible by design.

## 19. Known Limitations

- The original QM2-P0-006 Run remains permanently Git-inconsistent; consumers
  must present its separate correction relation without rewriting history.
- The correction Artifact is repository/Git evidence, not a generalized API or
  database correction workflow.
- Frozen observations are not Registry promotion evidence; no factor is
  promoted or production-ready.
- Real TDX and durable storage limitations remain unchanged.

## 20. Compatibility / Migration Notes

No production compatibility or migration change. Existing Manifest v1/v2,
Planner, Indexer, Repository and migration semantics are unchanged.

## 21. Rollback Notes

Revert the single QM2-P0-006F commit. This removes only the additive correction
evidence, tests, context updates and Run; it does not affect Validation data or
require database rollback.

## 22. Remaining Work

Factor Registry admission and promotion rules remain unimplemented. The
Registry must consume exact immutable evidence without treating the current
three Frozen candidates as automatically promoted.

## 23. Recommended Next Task

Only `QM2-P0-007 — Factor Registry v1 and Promotion Contract`.

## 24. Git / Workspace State

Pre-commit noncanonical Run; `result_commit` is null. One independent commit
is required. No amend or push is authorized.

## 25. Artifact Index

- Evidence correction JSON and strict schema.
- This Implementation Report and Manifest v2.
- Target Run references and `corrects` relationship.
- Test evidence for raw Git blob, immutable target hashes, Planner, Domain
  Bundle, disposable PostgreSQL index/replay, and related regression.
