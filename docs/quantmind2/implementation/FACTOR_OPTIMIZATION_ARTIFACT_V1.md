# Factor Optimization Artifact v1

## 1. Artifact authority

The Study artifact is the immutable local authority for one completed or
partially completed deterministic optimization execution. It references, but
does not copy, immutable Factor Values artifacts. It is not a Registry record
or predictive validation record.

## 2. Directory layout

```text
<optimization-root>/<study_id>/
  spec.json
  manifest.json
  summary.json
  trials/<trial_id>.json
```

The root is runtime configuration and is not part of Study identity.

## 3. Spec

`spec.json` is canonical JSON for the admitted embedded Template, Snapshot ID,
parameter roles, normalized search spaces, budget, quality gate, and frozen
candidate-ordering name. Its SHA-256 is recorded in the manifest.

## 4. Manifest

`manifest.json` records schema/engine versions, Study/Result/Template/Snapshot
identities, search space, budget, status counts, eligible count, ordered Trial
IDs, `validation_candidate_order`, stable Study manifest hash, timestamp, and
hashes for every payload file. `created_at` is evidence only and is excluded
from all content identities.

## 5. Trial records

Each Trial JSON records ordinal, parameters, Factor Instance ID, status,
Factor Values ID and Parquet hash when successful, mechanical metrics,
eligibility, structured ineligibility reasons, and a safe error code. Full
values and raw exception text are not stored.

## 6. Factor Values references

Validation resolves each successful/replayed reference and proves Template,
Instance, Snapshot, bound parameters, Parquet hash, quality, metrics, and key
lineage. The Study never duplicates Factor Values Parquet.

## 7. Identity

Study, Trial, Result, and stable manifest hashes follow the rules in
`FACTOR_OPTIMIZATION_V1.md`. File hashes cover canonical payload bytes. The
validator recomputes every identity rather than trusting stored strings.

## 8. Atomic publish

The publisher writes a unique sibling staging directory, fsync-independent
canonical payloads, computes the inventory hashes, and publishes with one
atomic rename. Staging cleanup occurs on success or failure.

## 9. Exact existing

When the final Study directory already exists, execution performs full
validation and returns it with `exact_existing=true`. It does not append,
rewrite timestamps, or execute additional Trial work.

## 10. Validation

Validation checks readable JSON, schema marker, Study/Spec identity, exact file
inventory, every file hash, Trial plan/parameter/Instance identity, referenced
Factor Values lineage, recomputed metrics and eligibility, candidate ordering,
status counts, stable manifest hash, Result ID, and non-predictive summary.

## 11. Conflict handling

Missing, extra, mutated, or mismatched files and references are hard failures.
A completed Study is never overwritten or merged. A changed Spec or search
space must produce a new Study ID.

## 12. Consumer boundary

Factor Validation may consume only eligible Trial references in
`validation_candidate_order`; it must independently establish predictive
evidence. Registry, LightGBM, Qlib, Signal, and production consumers cannot
treat this artifact as validation or promotion authority.
