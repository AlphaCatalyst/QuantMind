# Combined Optimization Policy v1

Status: accepted, `suspended`, effective from `QM2-R1-006`.

One Candidate research chain may not change Factor parameters and Strategy
parameters from their defaults. Such a plan or result hard-fails with
`COMBINED_PARAMETER_OPTIMIZATION_SUSPENDED`.

Allowed paths are:

- `F0S0`: default Factor and default Strategy;
- `F1S0`: local Factor only, after default Factor failure;
- `F0S1`: local Strategy only, after default Strategy failure and with a
  passing/frozen default Factor.

`F1S1`, `F1S2`, `F2S1`, `F2S2` and equivalent two-layer searches are
forbidden. If both defaults fail, the runtime holds Strategy at default,
permits only local Factor search, then stops. It never proceeds to Strategy
search in that Candidate chain.

The policy separates the three evidence classes used by new research:
`default_parameters`, `local_optimization_research`, and
`full_search_diagnostic`. Their order describes lower-to-higher overfit risk,
not predictive strength. Historical evidence is explicitly
`historical_legacy_optimization`.

Machine contract:
`docs/quantmind2/implementation/schemas/combined_optimization_policy_v1.schema.json`.
