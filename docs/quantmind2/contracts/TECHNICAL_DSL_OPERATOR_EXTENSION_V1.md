# Technical DSL Operator Extension v1

Status: accepted
Task: `QM2-R2-006`
Base DSL: `quantmind-factor-dsl-v1`

## Scope and boundary

This contract adds a bounded set of deterministic, point-in-time-safe rolling
operators to the existing canonical Factor DSL. It does not create another DSL,
permit structural evolution, add market-data fields, or authorize production
promotion.

Authorized operators:

```text
rolling_sum
rolling_corr
rolling_median
rolling_quantile
rolling_skew
rolling_argmax_age
```

Rejected operators:

```text
rolling_cov
rolling_kurt
where
if_else
group_neutralize
industry_neutralize
rolling_regression
```

The rejected operators remain unavailable because this bounded revision has no
complete executable PIT and Qlib/local consistency contract for them.

## Common execution contract

- Inputs are `float64` series ordered deterministically by symbol and trade date.
- A rolling window includes the current row and prior rows only.
- Windows are constants from `5, 10, 20, 40, 60, 120`.
- `min_periods` equals the complete window.
- Missing observations are never filled implicitly.
- Canonical AST serialization uses stable key ordering.
- Each operator passed PIT safety, deterministic execution, canonical
  serialization, AST round-trip, NaN, boundary-window, constant-series,
  Qlib/local consistency, and bounded-performance checks.

## Operator definitions

### `rolling_sum(x, window)`

- Arity: 1 series.
- Parameters: one fixed window.
- NaN policy: requires a fully finite window.
- Zero variance: not applicable.
- Canonical AST:
  `{"type":"rolling_sum","operand":<node>,"window":<fixed-window>}`.
- Complexity cost: 2.

### `rolling_corr(x, y, window)`

- Arity: 2 aligned series.
- Parameters: one fixed window.
- NaN policy: requires pairwise-finite observations for the complete window.
- Zero variance: returns NaN when either population variance is at or below
  `1e-24`.
- Alignment is same-symbol, same-date; future alignment is forbidden.
- Canonical AST:
  `{"type":"rolling_corr","left":<node>,"right":<node>,"window":<fixed-window>}`.
- Complexity cost: 4.

### `rolling_median(x, window)`

- Arity: 1 series.
- Parameters: one fixed window.
- NaN policy: requires a fully finite window; no implicit interpolation.
- A constant window returns the constant.
- Canonical AST:
  `{"type":"rolling_median","operand":<node>,"window":<fixed-window>}`.
- Complexity cost: 3.

### `rolling_quantile(x, window, quantile)`

- Arity: 1 series.
- Parameters: one fixed window and a non-optimizable DSL constant quantile.
- Allowed quantiles: `0.20`, `0.50`, `0.80`.
- NaN policy: requires a fully finite window.
- Linear quantile interpolation is deterministic; a constant window returns the
  constant.
- Canonical AST:
  `{"type":"rolling_quantile","operand":<node>,"window":<fixed-window>,"quantile":<0.20|0.50|0.80>}`.
- Complexity cost: 3.

### `rolling_skew(x, window)`

- Arity: 1 series.
- Parameters: one fixed window; minimum valid samples is 3.
- Uses the deterministic population central-moment ratio
  `mean((x-mean(x))^3) / mean((x-mean(x))^2)^(3/2)`.
- NaN policy: requires a fully finite window.
- Near-constant windows with population variance at or below `1e-24` return NaN.
- Canonical AST:
  `{"type":"rolling_skew","operand":<node>,"window":<fixed-window>}`.
- Complexity cost: 4.

### `rolling_argmax_age(x, window)`

- Arity: 1 series.
- Parameters: one fixed window.
- Result `0` means the current row is the window maximum; `window - 1` means
  the selected maximum is the oldest row.
- Ties select the most recent maximum.
- NaN policy: requires a fully finite window.
- A constant window therefore returns `0`.
- Canonical AST:
  `{"type":"rolling_argmax_age","operand":<node>,"window":<fixed-window>}`.
- Complexity cost: 3.

## Research permissions

These operators may be used only by the bounded technical research path. Feature
Factory v2 limits each generated feature to four primitives, two window
parameters, AST depth seven, and ten operators. Cross-sectional rank/z-score,
labels, forward returns, strategy controls, dynamic positions, and regime gates
remain forbidden in feature generation.

The machine-readable authority is
`docs/quantmind2/implementation/schemas/technical_dsl_operator_extension_v1.schema.json`.
