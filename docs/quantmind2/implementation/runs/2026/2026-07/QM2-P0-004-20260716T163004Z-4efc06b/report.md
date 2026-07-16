# QM2-P0-004 Implementation Report

## 1. Task Summary

Implemented Factor DSL v1, its bounded compiler/executor, and immutable Factor
Values v1. Five parameter instances were executed and validated against the
real 003L Legacy Feature Dataset Snapshot. Status at report generation is
`completed_uncommitted`.

## 2. Goal

Establish the first safe standard factor formula path:
canonical JSON -> typed closed IR -> static dataset admission -> bound Factor
Instance -> deterministic Snapshot computation -> immutable Factor Values.

## 3. Scope

- Strict Factor Template schema/parser and closed 18-node catalog.
- Parameter declaration, binding, resource limits and static shape checks.
- Canonical Template, Instance and Values identities.
- Dataset Snapshot role/leakage admission and required-terminal planning.
- Exact time-series/cross-sectional semantics and safe division.
- Atomic Parquet Factor Values publication, validation and replay.
- Offline CLI, unit/integration tests, contracts and Project Memory updates.

## 4. Explicit Non-goals

No optimization, factor validation metrics, Registry, model/portfolio
optimization, Frozen Test, Agent loop, structure evolution, Python candidate
path, LightGBM/Qlib switch, backtest, API, UI, database, migration, deployment,
dependency installation, lockfile update, Factor Lab edit, commit amend or push.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `4efc06b8099e180a583eceadfc0f1b270113d7d7`
- Dirty before: no
- Unrelated dirty files: none
- Official Factor Lab source was read-only. Its preflight content digest was
  `42d16e39b36f95c9663426d979ef950064ff76b4b4eaa8fd70acd262b14965e5`.
- The identical aggregate command at close returned the same digest; donor
  before/after equality passed.
- No dependency or runtime configuration changed.

## 6. What Changed

`backend/services/engine/factor_dsl/` now contains the closed parser, immutable
models, canonicalization/identity functions, Snapshot contract admission,
compiler, executor, quality rules and artifact validator. The CLI exposes
validate-template, compile, execute, validate-values and inspect operations.
Checked-in contracts define both Template JSON and Values artifacts. Four test
modules cover parser, compiler/leakage, operator semantics and real Snapshot
execution. Project Memory marks DSL/compute partial and selects QM2-P0-005.

## 7. Why It Changed

Agent-generated arbitrary Python cannot be the standard path because its
structure, effects, data access and identity are not closed or statically
admissible. Factor Lab's surviving contract/runbook evidence supports static
admission, leakage categories, sandbox boundaries and artifact lineage, but its
current official bounded directory references absent FactorSpec,
CandidateManifest, admission, evaluator and sandbox source modules. No donor
code was copied.

## 8. Files Changed

Changes are limited to the new factor DSL package/tests/CLI/contracts, Project
Memory/context validation, and this Implementation Run. The Manifest contains
the exact repository-relative inventory and hashes. No training, inference,
Qlib, model, trading, database, dependency, lockfile or Factor Lab path changed.

## 9. Important Classes / Functions / Documents

- `FactorTemplate`, `ExpressionNode`, `SnapshotContract`, `CompiledFactor`
- `parse_template`, `snapshot_contract`, `compile_template`
- `factor_template_id`, `factor_instance_id`, `factor_values_id`
- `execute_compiled`, `publish_values`, `validate_values`, `factor_quality`
- `FACTOR_DSL_V1.md`, `FACTOR_VALUES_V1.md`, Factor Template JSON Schema

## 10. API Changes

None. The CLI is an offline developer/research entry, not an HTTP API.

## 11. Database Changes

None.

## 12. Configuration / Environment Changes

None. Tests used an existing Python environment with pandas, pyarrow,
jsonschema and pytest. No package was installed.

## 13. Runtime Flow

Template JSON -> strict parse -> Snapshot metadata validation -> feature-role
admission -> parameter bind/shape/resource compile -> `load_feature_matrix`
for required terminals -> stable key sort -> typed operator evaluation ->
quality gate -> staged Parquet/JSON -> atomic rename -> hash/identity/key
validation. The compiler does not read factor values. The executor never calls
the label reader.

## 14. Architecture Impact

This realizes a bounded portion of ADR-0002/0003/0007: Template, bound Instance
and Values are separate identities; Dataset Snapshot is the only data authority;
and Python `factor_impl.py` remains outside the v1 standard path. Factor DSL and
Factor Compute move from planned to partial, not production.

## 15. Security Impact

Positive bounded impact: closed nodes and exact fields, no imports/calls/code,
safe identifiers, secret-like description rejection, role-based terminal
admission, no label access, finite numeric validation, resource budgets, safe
divide and atomic immutable output. This is not a general Python sandbox.

## 16. Data Lineage Impact

Template identity binds canonical formula; Instance binds Template, exact
parameters, Snapshot and engine; Values binds Instance, Parquet bytes and
schema. Manifest retains required terminals and Dataset Snapshot. The real
Snapshot and its source bytes were not modified.

## 17. Tests Executed

- Final Factor DSL suite with real Snapshot opt-in: 29 passed.
- Dataset/Legacy/TongDaXin regression: 41 passed, 1 expected skip because real
  tqcenter is unavailable.
- Context Bootstrap tests: 21 passed.
- Context Bootstrap validator: 38 checks passed.
- All QuantMind 2.0 JSON parsed; new Python compiled.
- CLI validate-values and inspect passed on runtime proof artifacts.
- Git diff/scope, Factor Lab digest and final Manifest checks are recorded at
  task close.

An initial Factor DSL pytest invocation also had all 18 tests pass but exited
nonzero because repository-wide coverage was 1.15% against a 5% global floor.
The same bounded suite was rerun with the repository-supported `--no-cov` mode
and passed; no test was hidden or skipped.

A later combined pre-finalization run had 89 pass, one expected tqcenter skip,
and one Context failure because this Report had just changed after Manifest
payload finalization. The Manifest was regenerated from the new bytes before
the final combined rerun; this sequencing failure did not indicate a context or
production-code defect.

## 18. Test Results

The real Snapshot proof used
`ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`
(5,931 rows, 100 symbols, 60 dates, 152 legal features, zero labels). Five
distinct Values IDs were produced:

- rolling mean/rank window 3: `fv_385ed568d5b68b7ec24dc2302081f867469206d591e51002d32998085b504264`
- rolling mean/rank window 10: `fv_5b83b004cd6c985f51af22c3d417656c7f24657bb2d1647607ca5a12f8fafdff`
- weighted delta (0.3, 2): `fv_346461783ca9956c2e90d66e04c028ffb90eb2ee08724ec58e64d01423f54bc9`
- weighted delta (0.7, 5): `fv_bb8d92e8ecc4d13f8c4d2e0d91c56b133186cb97ebeb32ec83b9c2f6b4b162a3`
- normalized spread: `fv_c200a1c6d2f9d86527650073bf7184cfba1d43929832ecbeb9ff98b620a753c9`

Their ordered Parquet SHA-256 values are respectively
`ce98cf28c91913471fb786674958fa7b2e0a7a875fc7f4d691ee9e3f2b580f1c`,
`4112b52c2d9708c6e9e0bcd85dd3ffd51438bf3ca4bb7cf383fa38ebe585ea8f`,
`cad8789b4b4a6bee736d2c4bed041a552fe59d36baa0553a95ce098c0a4a90eb`,
`084e6c46994a236c4bc1590e740975a3b81384ccd97bbb82db16dd5caa127734`
and `9df8b7f12ba41901b63e19c2496abeb2c7bb2f9547ba589c00b2de640963bc52`.

Each contains exactly 5,931 Snapshot keys and revalidates. Re-executing the
first instance returned the existing identical artifact. Runtime proof root is
`/private/tmp/qm2-p0-004-factor-values` and is not authoritative durable
storage or Git content.

## 19. Known Limitations

- v1 is offline, single-process and pandas/Parquet based.
- No optimizer, Registry, validation/IC, Frozen Test, Agent loop, API/UI,
  distributed execution or object-store publication exists.
- Warm-up dates legitimately create nulls; quality records this and warns when
  a date has fewer than two finite observations.
- Real TDX remains unavailable. Existing training/Qlib consumers remain
  unchanged.
- Factor Lab's official `/tmp` location remains non-durable and its current
  bounded source directory is incomplete as described above.

## 20. Compatibility / Migration Notes

No existing consumer is switched. Existing Alpha158/legacy features,
LightGBM, inference and Qlib behavior are unchanged. This is a new parallel
research contract.

## 21. Rollback Notes

Revert the single QM2-P0-004 commit. Runtime proof artifacts under
`/private/tmp/qm2-p0-004-factor-values` may be deleted independently. No schema,
database, configuration, dependency or data migration needs rollback.

## 22. Remaining Work

Factor parameter optimization and trial lineage remain absent. Registry,
validation, model/signal and official Qlib consumption remain later tasks.

## 23. Recommended Next Task

Only `QM2-P0-005 — Factor Optimization v1 on Parameterized DSL`.

## 24. Git / Workspace State

This report is pre-commit. The Run is noncanonical and
`completed_uncommitted`; `result_commit` is null. The task requires a later
single independent commit and no push.

## 25. Artifact Index

- This report and its Manifest v2 in the same Run directory.
- Factor DSL/Values contracts and JSON Schema in Git.
- Five runtime Values artifacts under `/private/tmp/qm2-p0-004-factor-values`.
