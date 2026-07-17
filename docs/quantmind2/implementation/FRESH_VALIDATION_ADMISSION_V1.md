# Fresh Validation Admission v1

## Scope

This gate decides which contaminated Development candidates may consume future unopened data. It is not formal Validation, Frozen Test, promotion, or evidence of alpha.

## Why fresh data is scarce

Forward data can be used only after candidate lock and maturity. Admission therefore has a total budget of three candidates and one candidate per structural family.

## Development-only evidence

Admission reads immutable 2025 Development summaries already produced by the Campaign. It does not recompute metrics, access labels, select a different Trial, flip orientation, or inspect 2026/Frozen evidence. Orientation must have been frozen on the pre-2025 research period.

## Safety gates

The research-only Registry status, valid Campaign/Optimization/Development/Factor Values artifacts, no label leakage, no Frozen access, contaminated Development marking, pre-Development orientation, non-constant output, and zero infinities are mandatory and cannot be disabled.

## Statistical gates

The fixed v1 minimums are 120 valid RankIC dates, 100 median daily observations, 0.60 finite coverage, non-negative oriented mean RankIC, non-null oriented RankICIR, and 0.50 oriented RankIC positive rate. Signed metrics are used; absolute RankIC is forbidden.

## Family limit and candidate ordering

Candidates are ordered by oriented mean RankIC, RankICIR (null last), positive rate, finite coverage, then Factor Instance ID. The family and total budgets are applied after safety/statistical gates.

## Artifact and Registry evidence

The immutable `fvar_` artifact contains one bounded summary per candidate plus admitted/rejected lists. The canonical Registry stores only policy ID, result ID, outcome, reasons, and rank; the main status remains `research_registered`.

## No Fresh Validation execution / no Frozen reuse

QM2-P0-008G creates only an eligible pool. It creates no future Label Dataset, Fresh Validation metrics, Frozen evidence, Promotion Candidate, approval, or activation.

## Current proof

Policy `fvap_e8af2fd66f311a35160e073258c3f910fe13fe767d0cd4389b90f536c6394efa` produced result `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`: 3 admitted and 2 rejected. External factor `fi_207c3b82f4b9f3a77e064513ad03a64e6e2d69dc939e6fc1e68aa4fc8fad0549` retains orientation `+1`; its oriented Development mean RankIC is `-0.03098286034429056`, so it was rejected by `DEVELOPMENT_MEAN_RANK_IC_BELOW_GATE`.
