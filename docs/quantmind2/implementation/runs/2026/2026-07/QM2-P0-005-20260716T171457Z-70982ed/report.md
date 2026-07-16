# QM2-P0-005 Implementation Report

## 1. Task Summary

Implemented Factor Optimization v1 as a bounded, deterministic, parameter-only
layer over Factor DSL v1. Two Studies executed 14 real-Snapshot trials, all
mechanically eligible. Status at report generation is
`completed_uncommitted`.

## 2. Goal

Provide the reproducible chain: admitted parameterized Template -> immutable
Study -> deterministic Trials -> compile -> Factor Values execute/replay ->
mechanical evaluation -> validation candidate order -> immutable artifact.

## 3. Scope

Strict Optimization Spec/JSON Schema, AST-checked roles, finite search spaces,
deterministic Cartesian enumeration, trial/failure budgets, Study/Trial/Result
identity, serial failure-isolated runner, mechanical metrics, validation
eligibility/order, atomic immutable artifacts, exact-existing/replay, CLI,
tests, contracts, real-Snapshot proof, and Project Memory updates.

## 4. Explicit Non-goals

No structure evolution, Agent loop, random/Bayesian/genetic search,
signal-threshold execution, label/IC/RankIC/return/Sharpe, Train/Validation/
Frozen Test, Registry, LightGBM/model optimization, portfolio optimization,
Qlib/backtest/signal/trading, API/UI/database/migration, training/Qlib changes,
dependency/lockfile changes, Factor Lab edits, amend, or push.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- Base: `70982ed804a8fce57b759cd556e3ce323b41d0dc`
- Dirty before: no; unrelated dirty files: none.
- Official Factor Lab source remained read-only. Preflight digest:
  `42d16e39b36f95c9663426d979ef950064ff76b4b4eaa8fd70acd262b14965e5`.
- Existing system Python lacked pyarrow. An existing project venv with pandas,
  numpy, pyarrow, jsonschema, and pytest was reused; nothing was installed.

## 6. What Changed

Added `backend/services/engine/factor_optimization/`, its offline CLI, strict
Spec schema, two implementation contracts, four focused test modules, and
Project Memory updates. The runner reuses Factor DSL compiler/executor/artifact
validation rather than duplicating them.

## 7. Why It Changed

Agents own factor hypotheses and parameterized structure; deterministic
services own concrete execution. Searching only typed Template parameters
prevents structure drift and keeps identities, budgets, lineage, replay, and
failure boundaries inspectable before predictive validation exists.

## 8. Files Changed

The Manifest contains the exact repository-relative inventory and hashes.
Scope is limited to the new optimization package/tests/CLI/schema/contracts,
Project Memory/context validation, and this Run. Training, inference, Qlib,
trading, dependencies, lockfiles, runtime configuration, Dataset Snapshot,
Factor Values source artifacts, and Factor Lab were not modified.

## 9. Important Classes / Functions / Documents

- `FactorOptimizationSpec`, `FactorOptimizationStudy`, `PlannedTrial`
- `FactorOptimizationTrial`, `FactorOptimizationResult`, `MechanicalMetrics`
- `parse_optimization_spec`, `validate_parameter_roles`, `plan_study`
- `execute_study`, `compute_mechanical_metrics`, `evaluate_eligibility`
- `validation_candidate_order`, `publish_study`, `validate_study`
- `FACTOR_OPTIMIZATION_V1.md`, `FACTOR_OPTIMIZATION_ARTIFACT_V1.md`

## 10. API Changes

None. `tools/quantmind2/factor_optimization.py` is an offline CLI with
`validate-spec`, `plan`, `execute`, `validate-study`, and `inspect`.

## 11. Database Changes

None.

## 12. Configuration / Environment Changes

None. Runtime roots were explicit CLI/test arguments under `/private/tmp`.

## 13. Runtime Flow

Strict Spec parse -> Template role check -> Snapshot contract check -> budget
admission -> stable parameter product -> compile each binding -> execute or
replay immutable Factor Values -> revalidate lineage -> compute mechanical
metrics -> eligibility -> stable candidate order -> staged canonical JSON ->
atomic publish -> full identity/hash/reference validation.

## 14. Architecture Impact

This realizes the parameter-only Factor Optimization portion of ADR-0002,
ADR-0003, ADR-0006, ADR-0007, and ADR-0008. Factor Optimization moves from
planned to partial, not production. It remains separate from model and
portfolio optimization and has no lifecycle-promotion authority.

## 15. Security Impact

The parser is strict and closed; roles are checked against AST use; budgets are
bounded; NaN/infinity/bool/duplicates are rejected in spaces; exception text,
paths, full DataFrames, and secrets are absent from Trial errors; no arbitrary
Python is executed; label/Frozen Test/Provider/Legacy source calls are absent.

## 16. Data Lineage Impact

Study identity binds Spec, Template, Snapshot, and engine versions. Trial binds
Study, parameters, and a distinct Factor Instance. Successful Trial records
reference Factor Values ID and Parquet hash; the validator rechecks Template,
Instance, bound parameters, Snapshot, values, metrics, eligibility, and order.
The authoritative Snapshot was not changed.

## 17. Tests Executed

- Optimization suite with real Snapshot opt-in: 24 passed.
- Factor DSL, data, Manifest/Indexer and Context regression: 134 passed, one
  explicitly rerun real-Legacy test initially skipped because its environment
  variable was misspelled; the corrected opt-in run passed 1/1.
- All five CLI commands passed against the real Study A; execute returned
  exact-existing.
- Context Bootstrap passed all 38 bounded repository checks and its dedicated
  pytest suite passed 21 tests.
- Final combined relevant regression passed 159 tests with no skip.
- A first optimization invocation had 19 assertions pass and three real tests
  skip because the Snapshot variable was omitted, then failed only the global
  repository coverage floor. It was not counted as acceptance and was rerun
  correctly with `--no-cov` and real data.
- Final Context Bootstrap, JSON parsing, Python compile, Manifest planning,
  diff/scope, and donor digest checks are performed after Manifest generation.

## 18. Test Results and Real Studies

Authoritative Snapshot:
`ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`
(5,931 rows, 100 symbols, 60 dates, 152 feature roles, zero labels).

Study A:

- Study `fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2`
- Result `for_c8592f527566790981c9f4df0c586d36ad7f486bf6e111697c4c3b319cf16749`
- Stable Study manifest hash
  `b0d77fde5837f9fd6a419d25264a259ae2077e4a4eb5fcdfa8ec94d3f01b2075`
- Published `manifest.json` SHA-256
  `2a1490622afe72522ff73d372d5e4a92df7b76e9cce4969efd3458a7339dc5df`
- Five trials, three newly succeeded and two replayed existing Factor Values;
  five eligible. Candidate order is the Trial order shown below.

Study B:

- Study `fos_ac8ea3539ba0db8faa4dc223750d649584da270244ec022638faef8bdfeb5a19`
- Result `for_fa08767f043c75a3ef4aeef0165edba1ed9c2ba3e65a8f13e9402431c79f86f4`
- Stable Study manifest hash
  `a662573c8c80d3cdee34dbd4df8c520d08750fb092f29bf0ae09aeaaf4bdc1c1`
- Published `manifest.json` SHA-256
  `69b395e1cabb15fb7b3180c2e2ce24552a22e1f603be966501bd3460b83503ca`
- Nine succeeded and eligible trials. Candidate order is mechanical and appears
  in the final column as rank.

| Trial | Parameters | Factor Instance | Factor Values | Initial status | Finite coverage | Eligible | Candidate rank |
|---|---|---|---|---|---:|---|---:|
| `fot_230dfb8eec1515916567d6652558ef68f6e2d163cadd312d74f05cd0ba26d116` | window=2 | `fi_d34cd8b273180eb2280abc3b284a05eff1c1c4bd8a1aa8a01d17da90ad56d7c5` | `fv_3d02e13bc1fa254ae621586e44fca782354fe2935f50a9e65a521a3feace60e1` | succeeded | 0.983139 | yes | A1 |
| `fot_f83683c30cbb564d3d634d633977a79b32cb44807cc616d05336e04c04675f9f` | window=3 | `fi_d666f5b0409763e8a2ce35c3135ac32adb82c83dd20c370f106414acf0793964` | `fv_385ed568d5b68b7ec24dc2302081f867469206d591e51002d32998085b504264` | replayed | 0.966279 | yes | A2 |
| `fot_3d75fefd2ee38a57c8357e70ddce84c2a727870f1a3eeed4d8efc94b5ef3ed17` | window=5 | `fi_67cef63af4995339fde06b7ff68581eba40dd9d315e9cdc3749a90a8b064aa7d` | `fv_d32e6bae985d9ada6845f0e3788fa31d054b3e85cc5f5b4410f7f977590966fc` | succeeded | 0.932558 | yes | A3 |
| `fot_091eef460aa28993bdc1fde30cc3d0b02931db886fa17b10d6c5df52b530974d` | window=10 | `fi_94b3fc524e46b37f97c9a7e87aca83099da507b4c7822775d28e932d48f01943` | `fv_5b83b004cd6c985f51af22c3d417656c7f24657bb2d1647607ca5a12f8fafdff` | replayed | 0.848255 | yes | A4 |
| `fot_566b33580ebf082bc08ebb234ca27954d387d91bf44349b83d2332de9d11e7ec` | window=20 | `fi_0e401b112a42090600ab9f7fa42bd914b13a98759b244bc2b71b7cc2ae93ea99` | `fv_4e81b5310ae9e80fdea1bbc72f1bf322e2e19a0f584f93d7bec36c5c0d2dd8b8` | succeeded | 0.680998 | yes | A5 |
| `fot_55d82e65c25bd5fe5d2f8353dd14b574903789d26832de21165a900a7d79b8d3` | periods=1, weight=0.2 | `fi_3daa5e41b2f9fb7632d3d7fc74c070b539811090fbf99d3dabd821b3bd526de5` | `fv_68c0f0729f0cd46f59ed5a1463ba84a81884b9fb63e38a918bb1ef9ecaee16d6` | succeeded | 0.983139 | yes | B2 |
| `fot_e6862a131db5a34f0f26a710e73ae9399dcded320cb836fd1c15f5e7a17d630e` | periods=1, weight=0.5 | `fi_ae03bc2aad44d55cffd2d241c33f31994b1a30b686c0e472b1b5954a2fddaaf9` | `fv_95f8d7bb1297f118e8c9fdcdd318f291bcf4fedaf778cda66e76e03749c1da86` | succeeded | 0.983139 | yes | B3 |
| `fot_39f0ba7061b354c54da47532dbe33750383e9c1474cbe8a844722bff48cf3481` | periods=1, weight=0.8 | `fi_7dbb667e4691f08b062b4e6df7a86f9bd5075ec8f36cf9d09bd9a9a7caaf6ca3` | `fv_dad9f31bc8ff292081899a1e995e2755911f6c8d918166d31a25c04c2f6b325f` | succeeded | 0.983139 | yes | B1 |
| `fot_4d78ce9cf3fc4be34eb581a18cae2284e32682605d3742810636d86f2b61edf2` | periods=3, weight=0.2 | `fi_79137ce1245b0ac293244d2bfcd371962ac9c65e4f09adab1f730479509eec77` | `fv_9c37014be8c5f6d53846b5407fcb0e43c17ffc6a4b25ab246d4e07495c97bd7c` | succeeded | 0.949418 | yes | B4 |
| `fot_5650e135b4c73f57e5d0da6f301b7202c547e828ba5d284dae233fc3bf39d9f5` | periods=3, weight=0.5 | `fi_901a9ca551bfc8497ef4cd38d0348a65e1e97ab94f96e7cffbc6cf10117ecaf9` | `fv_0ce88446ab3cc6509b7b6e50f3d8f4c27ee39c7e9f260e88b1ffc36f5dda0c2c` | succeeded | 0.949418 | yes | B5 |
| `fot_a181ba7ad2054ded37c93be89663090f937a701b5b3d61feb4325a3ca8409b77` | periods=3, weight=0.8 | `fi_a66ad344d67de2b1b10d202d97e36d777bad090c8f515033890fd627f5276857` | `fv_8995b787620d3f48386a163ea5ead0d2b15ae3f4618da2b5ea474a057683f6cd` | succeeded | 0.949418 | yes | B6 |
| `fot_187f33947f6348ff9d08d526f72813f0368113a605b6a6ec8aa85c0041dfe12d` | periods=5, weight=0.2 | `fi_2496486d6561f6aeffd056da31ad4ddcd39c38666e74ecdc4923cd3e2e98a234` | `fv_d78b5964c7e8c6ff68caebdd3b2c36cca8207503ac32cbc4dd6b10f9d0564026` | succeeded | 0.915697 | yes | B7 |
| `fot_ea31b7aeedba0f890acd04f77a2cd8833d379abf0d721d5873a350107d606f72` | periods=5, weight=0.5 | `fi_ae17c28690132fc3fb282b48234d309dd9e41a8b54c109f110a88b51dc05b5cd` | `fv_924201dd17891d9720cb8ab95e0036af2ac46d11bcb7186ba8da9bdf1123946e` | succeeded | 0.915697 | yes | B9 |
| `fot_19443929f3a7a724b8b3a98a7ac9a000d440433fff8aa6d360f661885728f23a` | periods=5, weight=0.8 | `fi_f9fec179d9c7cd146e6b4dbb59ef7e406441025c57c345ca9cb398d9cac5a825` | `fv_3c727c5c4d02b7a615679c9c03e4f13b168634bf43d1b2c67deb7e0ff7a8573f` | succeeded | 0.915697 | yes | B8 |

Repeated enumeration reproduced all Trial IDs and order. Repeated Study
execution returned exact-existing with unchanged Result/order/hashes.

## 19. Known Limitations

- Offline serial local execution only; no distributed workers or object store.
- Only deterministic finite enumeration; no threshold, random, Bayesian,
  conditional, continuous-grid, or structure search.
- Mechanical coverage/constant/infinity gates are not predictive evidence.
- No Registry, validation, model/signal/backtest, API, or database index.
- Runtime `/private/tmp` artifacts are verification evidence, not durable
  production storage. Factor Lab's official `/tmp` source remains non-durable.

## 20. Compatibility / Migration Notes

This is a new parallel research component. Existing Alpha158/features,
training, LightGBM, inference, Qlib, and portfolio behavior are unchanged.

## 21. Rollback Notes

Revert the single QM2-P0-005 commit. Runtime Study artifacts under
`/private/tmp/qm2-p0-005-optimization` and newly generated runtime Factor Values
may be deleted independently. No database/data/config/dependency migration
requires rollback.

## 22. Remaining Work

Predictive Factor Validation with label authority, Train/Validation split,
access-isolated Frozen Test, IC/RankIC and related evidence remains absent.
Registry/model/signal/Qlib consumption remains later work.

## 23. Recommended Next Task

Only `QM2-P0-006 — Factor Validation v1 with Train, Validation and Frozen Test`.

## 24. Git / Workspace State

This report is pre-commit. The Run is noncanonical and
`completed_uncommitted`; `result_commit` is null. One independent commit is
required; no amend or push.

## 25. Artifact Index

- This report and Manifest v2 in the same Run directory.
- Optimization contracts and Spec JSON Schema in Git.
- Runtime Studies under `/private/tmp/qm2-p0-005-optimization`.
- Referenced runtime Factor Values under
  `/private/tmp/qm2-p0-004-factor-values`.
