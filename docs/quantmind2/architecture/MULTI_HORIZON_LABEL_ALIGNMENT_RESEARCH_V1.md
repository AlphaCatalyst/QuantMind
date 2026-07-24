# Multi-Horizon Label Alignment Research v1

Status: accepted implementation contract for `QM2-R2-008`.

## Boundary

This retrospective study audits the legacy metadata, executable training
expression, materialized training label, and Qlib holding protocol as separate
facts. It does not replace the production label, regenerate Features, alter a
Feature Bundle, tune LightGBM or strategy parameters, write the Registry, or
promote a result.

## Frozen Label family

All three labels are frozen before any training or metric read:

| Name | Entry | Exit | Overlap | HAC lag |
|---|---|---|---:|---:|
| `technical_return_1d` | adjusted open at T+1 | adjusted close at T+1 | false | 10 |
| `technical_return_5d` | adjusted open at T+1 | adjusted close at T+5 | true | 10 |
| `technical_return_10d` | adjusted open at T+1 | adjusted close at T+10 | true | 15 |

T+n means the nth official trading session after signal date T. Entry and exit
must both have finite adjusted prices and be tradable. Missing observations,
suspensions, and lifecycle exits remain missing; no forward fill, last-price
substitution, delisted-member replacement, or fourth horizon is allowed.

Each raw return remains available for economic interpretation. The model label
is independently transformed per date with the frozen 5-MAD winsorization and
population z-score rule.

## Frozen experiment

The study reuses the three `QM2-R2-007` Feature Bundles, canonical LightGBM
configuration, three equal-weight seeds, four expanding outer folds, and fixed
Qlib strategy. Bundle C membership remains train-only and label-free. Purge is
`max(10, label_horizon_sessions)`.

The formal retrospective matrix is 3 labels x 3 bundles x 4 folds x 3 seeds:
108 trainings, 36 ensemble predictions, and 36 Qlib runs. All nine
label-bundle hypotheses enter one Benjamini-Hochberg family at FDR q=10%.
Neither 2025 nor 2026 observations may select a label, bundle, configuration,
Candidate, or Supervisor outcome.

## Artifacts and state

The authoritative Artifact sequence is Label Family, Executable Label Audit,
Label Materialization, Label Quality Assessment, Fold Result, Horizon Alignment
Assessment, global Multiple Testing, conditional Retrospective Model Candidate,
conditional Fresh Lock, and terminal Research Report.

Candidates remain `retrospective_model_candidate`. A Fresh Lock begins strictly
after the project contamination maximum and forbids backfill. No artifact in
this study is `validated`, `approved`, `active`, or `production`.

Cycle 004 is an explicitly invoked multi-horizon model-alpha cycle. It never
creates Cycle 005 automatically. A zero-survivor result is valid and records
the authorized technical feature, fixed-model aggregation, and multi-horizon
alignment spaces as exhausted.
