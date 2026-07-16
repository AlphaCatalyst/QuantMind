# Factor DSL v1 Contract

## Contract coverage

1. Authority: canonical JSON parsed to the typed closed IR.
2. Factor Template: unbound structure, declarations and output.
3. Parameter Schema: integer/number, default, bounds and optional step.
4. Typed Expression IR: `ExpressionNode` with closed `NodeKind` and exact fields.
5. Terminal inventory: feature, parameter and finite constant.
6. Operator inventory: the 15 entries in `OPERATOR_CATALOG`.
7. Exact operator semantics: frozen below.
8. Shape system: scalar/series compile-time inference.
9. Admission: dataset kind, roles, bounds and resource limits.
10. Leakage gate: exact role `feature` only; no label/unknown/forbidden access.
11. Canonicalization: sorted compact UTF-8 JSON without non-finite values.
12. Template ID: `ft_<sha256>` over canonical Template.
13. Instance ID: `fi_<sha256>` over Template, parameters, Snapshot and engine.
14. Compilation: metadata-only static planning.
15. Execution: declared Snapshot terminals only.
16. Missing values: propagate; no implicit fill.
17. Determinism: stable sort, fixed semantics and content identities.
18. Resource bounds: nodes/depth/features/parameters/windows.
19. Real Snapshot proof: recorded in the QM2-P0-004 Run.
20. Factor Lab boundary: concepts only; no Python-first donor execution.
21. Deferred optimization: QM2-P0-005, not this contract.
22. Deferred validation/Registry: no IC, backtest or lifecycle claim.

## Authority and boundary

Canonical JSON parsed into the closed typed AST is the authority for a Factor
Template. Agent-provided identifiers, Python, imports, calls, paths, executable
strings, labels, metadata and unknown fields are rejected. `factor_impl.py` is
not part of this path: arbitrary Python is not a closed or statically
admissible formula, cannot receive a canonical structural identity safely, and
would require the separate Docker sandbox boundary.

The v1 node catalog is closed: `feature`, `parameter`, `constant`, `add`,
`subtract`, `multiply`, `divide`, `negate`, `absolute`, `clip`, `lag`, `delta`,
`rolling_mean`, `rolling_std`, `rolling_min`, `rolling_max`, `cs_rank`, and
`cs_zscore`. The machine contract is
`docs/quantmind2/implementation/schemas/factor_template_v1.schema.json`.
`operator_catalog.py` is the human/runtime operator inventory; it is not an
extension registry and cannot authorize an unknown JSON node.

## Objects and identities

- Factor Template: unbound formula, declarations and output metadata. Its
  `ft_<sha256>` identity hashes canonical UTF-8 JSON with sorted keys, compact
  separators and no NaN/Infinity.
- Factor Instance: Template ID plus exact bound parameter map, Dataset Snapshot
  ID and engine version. Its `fi_<sha256>` identity is distinct from Template.
- Factor Values: immutable Parquet values plus manifest and quality evidence.
  Its `fv_<sha256>` identity binds Factor Instance, Parquet hash and output
  schema. Timestamps are not identity inputs.

The parser never accepts any of these IDs from an Agent. The system derives
them. Parameters are declared once with integer/number type, default, inclusive
bounds and optional positive step. v1 permits at most eight parameters.

## Static admission and compiler

Compilation receives a validated Snapshot metadata contract, not a DataFrame.
It validates dataset kind, exact feature spelling, `column_roles` and declared
Snapshot output type. Only role `feature` with an admitted numeric type is
legal; string/categorical, label, metadata, forbidden, unknown, missing and
case aliases fail closed.
Parameter references must be declared; an unused declaration is an explicit
warning. The final value must be a series.

Resource limits are 64 nodes, depth 16, 16 feature terminals, eight parameters,
and rolling window 252. Windows are also bounded by the Snapshot's observed
date count. Lag/delta periods are positive and below the date count. The
compiler reports required terminals, shape, warm-up, bound parameters and IDs;
it does not read values or execute a Provider.

## Execution semantics

Execution first validates the Dataset Snapshot and calls only
`load_feature_matrix(snapshot_root, snapshot_id, required_features)`. It sorts
stably by `trade_date,symbol`, rejects duplicate keys, and never calls
`load_labels`.

- Time operators group by symbol in ascending date order.
- `lag` shifts by a positive period; `delta(x,n) = x - lag(x,n)`.
- Rolling operations are trailing and include the current row, use
  `min_periods=window`; standard deviation uses `ddof=0`.
- Division produces NaN where `abs(denominator) <= 1e-12` and never emits
  Infinity.
- Cross-sectional operations group by date. Rank is average percentile in
  `[0,1]`; fewer than two finite values yields NaN. Z-score uses `ddof=0` and
  yields NaN for fewer than two finite values or zero standard deviation.
- Clip requires `lower < upper`. No implicit fill, winsorization,
  standardization or label access occurs.

## Factor Values artifact

Each artifact directory contains `manifest.json`, `quality.json`, and
`values.parquet` with exactly `symbol`, `trade_date`, `factor_value`. Publish is
staged then atomically renamed. Exact identity replay returns the existing
artifact; conflicting bytes fail. Validation checks hashes, content identity,
schema, unique keys, row count, Snapshot lineage and exact Snapshot keys.

Entirely-null or infinite output blocks publish. Constant values, finite
coverage below 80 percent and dates with fewer than two finite observations are
warnings. Runtime artifacts default to `/tmp` and are not committed.

## Explicit non-goals

No optimization, IC/RankIC, backtest, Registry lifecycle, Feature Snapshot,
LightGBM, Qlib, structure evolution, Agent loop, API, UI, database migration or
Python candidate execution is implemented here.
