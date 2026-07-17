# Factor Promotion Contract v1

## Promotion Policy

`FactorPromotionPolicy` version `1.0.0` is content-addressed by `policy_id` and
`canonical_hash`. Its thresholds are conservative Registry governance gates,
not claims of predictive truth or return guarantees.

The non-disableable safety gates require complete Git and Validation evidence,
Frozen evidence, no label leakage, respected development quarantine,
Train-only orientation, immutable Frozen candidate selection, and no Frozen
reselection. Frozen coverage requires at least 60 valid dates and median 100
daily observations. Oriented Frozen statistics require mean RankIC >= 0.01,
RankICIR >= 0.10, positive-rate >= 0.52, and the same oriented sign as
Validation. Negative values are not made positive with absolute value.

## Human approval and no automatic promotion

All machine gates produce only `promotion_candidate`. The policy fixes
`requires_human_approval=true`, `allows_auto_approval=false`, and
`allows_auto_activation=false`. Agent, Optimizer, Validation service, and
Registry cannot approve or activate. Decision source is closed to `human` and
`control_layer`.

## Decisions and state transitions

An immutable `FactorPromotionDecision` binds its Factor Instance, current
Registry Snapshot, Policy, action, reason, actor, source, time, and evidence
hash. Applying it produces a new Snapshot linked to its predecessor. A stale
Snapshot or Policy reference is rejected.

Allowed transitions are:

```text
promotion_candidate -> approved (approve)
promotion_candidate -> frozen_rejected (reject)
approved -> active (activate)
approved|active -> retired (retire)
any non-invalidated state -> invalidated (invalidate)
```

Approval is allowed only for a promotion candidate; activation is a separate
decision. Rejection never changes research metrics. Retirement preserves
history. Invalidation records pollution, lineage errors, leakage, revoked
evidence, or protocol invalidity. Direct rejected/research-to-approved or
non-approved-to-active transitions are forbidden.

## Frozen no-reselection contract

Validation selects the immutable Frozen candidate set before Frozen access.
Registry verifies that exact set and Train-derived orientation. Frozen results
cannot reorder parameters, trigger reselection, weaken policy, or feed Agent,
Optimizer, or Campaign Memory. A Frozen failure remains registered evidence.

## Current result

All three existing Frozen observations fail Policy v1. The real Registry has
zero promotion candidates, zero approved Factors, and zero active Factors. No
Promotion or Activation Decision was created for real evidence by QM2-P0-007.
