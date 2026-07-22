# Factor Optimization Policy v2

Status: accepted and effective from `QM2-R1-006`.

## Boundary

This policy governs newly created research Candidates. Historical Studies,
Trials, Candidate Locks and Registry entries remain immutable and keep
`optimization_policy_version=legacy_or_v1` semantics.

The Agent must declare `default_parameters` explicitly. Missing or null
defaults hard-fail with `AGENT_DEFAULT_PARAMETERS_MISSING`; no midpoint,
first-Trial, historical-best or code-default inference is permitted.

## Default-first flow

The default Factor Instance is evaluated first. If the bound Eligibility gate
passes, the defaults are frozen with `selection_reason=default_parameters_passed`,
one evaluated Trial and zero optimization calls. Higher return, RankIC, Sharpe,
excess or lower drawdown never authorizes continuing the search.

If the default fails, the only selection-capable search is the default plus
the immediately previous and next legal value of each optimizable parameter,
changing one parameter at a time. The budget is
`min(1 + 2 * parameter_count, 7)`. Failed Trials count toward effective search.

A local rescue is `local_optimization_research`, sets
`optimization_rescued=true`, and may become `research_registered` only. It
does not by itself authorize Validation, Promotion, approved, active or
production status; new-time evidence is required.

## Diagnostic full search

`full_search_diagnostic` is disabled by default and requires the explicit
`allow_full_factor_search_diagnostic` gate. Its outputs are diagnostic only:
they are never usable for Candidate selection, Candidate Lock parameters or
Promotion.

Machine contract:
`docs/quantmind2/implementation/schemas/factor_optimization_policy_v2.schema.json`.
