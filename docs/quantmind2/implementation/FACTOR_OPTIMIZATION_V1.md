# Factor Optimization v1

## 1. Scope

Factor Optimization v1 is the bounded, deterministic parameter-search layer
between an admitted Factor DSL Template and later supervised Factor Validation.
It consumes one immutable Dataset Snapshot and produces an immutable Study
artifact whose trials reference Factor Values artifacts. It does not evaluate
predictive value.

The frozen flow is:

```text
Parameterized Factor Template
-> deterministic parameter enumeration
-> compile one Factor Instance per binding
-> execute or replay Factor Values
-> mechanical quality metrics
-> eligibility gate
-> validation_candidate_order
```

## 2. Why optimization is parameter-only

The Research Agent owns hypotheses and structure. This optimizer may bind only
parameters already declared by the Template. It cannot edit the AST, introduce
operators, infer parameters from names, or search model/portfolio settings.
This preserves the accepted separation in ADR-0008 and makes every trial
reproducible from the Spec.

## 3. Study, Trial, and Result

- `FactorOptimizationSpec` binds the Template, Snapshot, parameter roles,
  search spaces, budgets, quality gate, and one frozen ordering rule.
- `FactorOptimizationStudy` is the immutable admitted plan and ordered set of
  `PlannedTrial` objects.
- `FactorOptimizationTrial` records one binding, its distinct Factor Instance,
  referenced Factor Values, status, metrics, and eligibility.
- `FactorOptimizationResult` records Study status, counts, candidate order,
  artifact hash, and exact-existing state. It is not a Factor Instance or a
  Factor Values identity.

## 4. Parameter roles

`lookback_window` is admitted only at typed AST window/period positions.
`factor_internal_weight` is admitted only at scalar arithmetic or clip-bound
positions. The `signal_threshold` enum is reserved, but v1 rejects its use
because Factor DSL v1 has no Signal node. Roles are checked against actual AST
references rather than parameter names.

## 5. Search spaces

`integer_range` is inclusive, has a positive integer step, and is intersected
with the Template parameter bounds. `explicit_values` accepts finite integer or
number values, rejects bool/NaN/infinity/duplicates, preserves declaration
order, and validates each value against the Template. Continuous float grids,
random sampling, conditional spaces, and dynamic expansion are absent.

## 6. Deterministic enumeration

Parameter names use Unicode code-point ascending order. Values retain their
formal Search Space order. The enumerator takes the Cartesian product and
assigns ordinals before execution. It never depends on mapping/set iteration,
concurrency, or completion order. An over-budget product is rejected in full;
it is never truncated.

## 7. Budget

`max_trials` admits at most 256 trials. `max_failed_trials` admits at most 32
failures, and `stop_on_first_error` is explicit. The runner stops scheduling
after the configured failure condition, preserves completed trials, and marks
remaining bindings `not_run`. v1 has no wall-clock cancellation or background
worker.

## 8. Identity

The frozen versions are schema `1.0.0`, engine `1.0.0`, and canonicalization
`factor-optimization-canonical-json-v1`.

- `fos_<sha256>` binds canonical Spec, Template ID, Snapshot ID, DSL engine,
  and optimization engine.
- `fot_<sha256>` binds Study ID, canonical parameter values, and Factor
  Instance ID.
- `for_<sha256>` binds Study ID, stable trial summaries, candidate order, and
  the stable Study manifest hash.

Timestamps, absolute paths, random values, and exception messages do not enter
identity.

## 9. Trial execution

Each binding reuses `compile_template`, `execute_compiled`, and
`validate_values`. The runner accesses the validated Snapshot consumer view,
not a Provider or Legacy source. An existing Factor Values identity is replayed
exactly; complete Study artifacts are validated and returned exact-existing.
Trials run serially and do not access labels, models, Qlib, or backtests.

## 10. Mechanical metrics

Metrics cover row/null/finite counts, symbol/date coverage, warm-up, daily
finite-symbol coverage, global finite-value distribution, uniqueness,
constant output, and infinity count. They are computed only from Factor Values
quality metadata and Parquet values. No IC, RankIC, future return, Sharpe, or
sign-based preference is calculated.

## 11. Eligibility

`eligible_for_validation` means only that execution, lineage, key alignment,
non-empty finite output, non-constant output, infinity safety, and configured
coverage/size gates passed. The non-disableable safety checks remain active.
Ineligible and failed trials remain in the immutable Study record.

## 12. Candidate ordering

Eligible trials are ordered by finite coverage descending, median daily finite
symbols descending, null count ascending, warm-up periods ascending, then
Trial ID ascending. The field is named `validation_candidate_order`. It is a
mechanical readiness order and never a best-factor or predictive ranking.

## 13. Failure isolation

One Trial exception becomes a bounded error code and does not expose exception
text, absolute paths, DataFrames, or secrets. Other trials continue until the
failure budget stops admission. Study status is `succeeded`, `partial`, or
`failed`; unexecuted bindings are not misreported as failures.

## 14. Resume and replay

A complete target Study is validated byte/hash/identity/lineage-wise and
returned exact-existing. Stale staging directories are removed before a new
atomic publish. A conflicting completed directory fails hard and is never
overwritten or merged. Changing the search space creates a different Study.

## 15. Real studies

Both studies used Snapshot
`ds_bc82e7bb2c63d2c47677b11cf0f4fc1e5aa11a0ed18ee0bb27e3c8ab667d2ee7`.

- Rolling Rank window Study
  `fos_969d431e553ad29d1d7bcdd4d912a6ab92471b5c4faf833a18abe2607baa1cb2`
  enumerated windows `[2, 3, 5, 10, 20]`, produced five eligible trials, and
  returned Result
  `for_c8592f527566790981c9f4df0c586d36ad7f486bf6e111697c4c3b319cf16749`.
- Weighted Delta Study
  `fos_ac8ea3539ba0db8faa4dc223750d649584da270244ec022638faef8bdfeb5a19`
  enumerated `periods=[1,3,5]` by `weight=[0.2,0.5,0.8]`, produced nine
  eligible trials, and returned Result
  `for_fa08767f043c75a3ef4aeef0165edba1ed9c2ba3e65a8f13e9402431c79f86f4`.

All 14 trials reference Factor Values on the same real Snapshot. The second
Study execution returned exact-existing. Study A also proved Trial-level
Factor Values replay for the previously materialized window 3 and 10 instances.

## 16. Factor Lab boundary

The donor `Campaign`/candidate-run/budget/failure/artifact concepts informed
Study, Trial, budget, isolation, and lineage. Its Python-first candidates,
Agent/evolution loops, predictive evaluation, Campaign Memory, and temporary
source path are not dependencies of this implementation. Donor inspection
also found parameter search disabled in the surviving v7 session contract.

## 17. No predictive claim

Every summary carries `predictive_claim: false`. Eligibility and ordering are
data/execution readiness only. No label, IC, RankIC, return, model, signal,
position, or backtest result exists in this layer.

## 18. Deferred validation

Train/Validation/Frozen Test boundaries, label access, IC/RankIC, stability,
turnover, cost, correlation, and regime evidence belong to QM2-P0-006. The
Optimizer must never access Frozen Test.

## 19. Deferred registry

Registry lifecycle, promotion, consumer references, model feature admission,
and production status remain unimplemented. A completed Optimization Study
does not change Factor lifecycle state.
