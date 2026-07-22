# Strategy Optimization Policy v2

Status: accepted and effective from `QM2-R1-006`.

The canonical default is TopK 20, n_drop 5, rebalance interval 5,
equal-weight, signal lag 1 and open-price execution. It is evaluated first. A
passing default freezes immediately with zero strategy-optimization calls.

Only an explicit default-gate failure permits the exact local neighborhood:

```text
[20,5,5] [10,5,5] [30,5,5] [20,0,5]
[20,10,5] [20,5,1] [20,5,10]
```

All configurations keep `n_drop < topk`; the total neighborhood contains at
most seven evaluated configurations. A rescue is research-only, records
default metrics/reasons, selected parameters, gain, turnover and cost change,
and never upgrades strategy state automatically.

The historical 24-configuration space is
`full_strategy_search_diagnostic`. It is disabled by default, requires
`allow_full_strategy_search_diagnostic`, cannot select a Candidate, cannot
write back to Strategy Spec, and cannot authorize Promotion.

Machine contract:
`docs/quantmind2/implementation/schemas/strategy_optimization_policy_v2.schema.json`.
