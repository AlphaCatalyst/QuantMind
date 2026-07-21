# Research Artifact Completeness v1

Status: implemented by `QM2-R1-003`.

This contract prevents a research summary from becoming a non-replayable
"ghost candidate". `/tmp` and `/private/tmp` are disposable workspaces only.
Every stage must validate, publish to the Research Artifact Store, cold
materialize into an empty destination, and validate again before its output may
be consumed by the next stage.

The immutable artifact chain is:

```text
Raw Agent Response → Proposal → Template Definition → Trial Detail
→ Fold Candidate Lock → Eligibility Evidence → Research Candidate Lock
→ Retrospective Report → Assessment → Experiment
```

Raw responses retain exact bytes, SHA-256, byte length, provider/model, prompt
hash, call ID and Research Decision ID. Proposal artifacts retain the complete
normalized payload and rationale. Template artifacts retain canonical DSL,
AST, input features, parameter schema, orientation policy, structural
fingerprint, hypothesis and source Proposal. Trial artifacts retain fold,
parameters, Factor Instance, complete factor values, metrics, failure and
selection state. Fold locks retain research/evaluation periods, the selected
Trial and parameters, factor-value and signal identities, orientation and
selection metrics. Eligibility artifacts retain all four Fold results,
parameter-neighborhood rows, turnover, cost, concentration, correlation,
regime metrics and every gate result/failure.

Missing required fields or an unavailable/hash-invalid Store artifact fail
with `ARTIFACT_COMPLETENESS_FAILED`. Candidate locking cannot proceed after
such a failure. Exact replay reads Store artifacts only and must make zero
Agent, Optimization, Qlib and network calls.

Candidate eligibility and ensemble diversity are separate gates. One eligible
candidate may be locked; an ensemble requires at least two locked candidates
from distinct subfamilies. Locks are `research_registered` only and cannot
claim fresh validation, prediction, promotion or production eligibility.
