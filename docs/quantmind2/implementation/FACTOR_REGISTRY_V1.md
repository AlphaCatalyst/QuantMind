# Factor Registry v1

## Scope and authority model

Factor Registry v1 is an immutable, file-backed research-governance boundary. It
registers existing Factor Instances and references authoritative Optimization,
Validation, Candidate Selection, Frozen Test, and QM2-P0-006F correction
evidence. It does not recompute research metrics, copy Factor Values, approve a
Factor, train a model, or run a backtest.

The four authorities remain separate:

```text
Research Evidence != Registry Entry != Promotion Decision != Registry Snapshot
```

Research artifacts remain authoritative for measurements. A Registry Entry is
the current evidence-derived state of one existing Factor Instance. A Promotion
Decision is an explicit human or control-layer action. A Registry Snapshot is an
immutable view of entries, decisions, and policy.

## Entry identity and evidence lineage

`factor_instance_id` is the Entry identity; Registry never creates a replacement
Instance. Each Entry binds the Template/family, unchanged parameters, Dataset
Snapshot, Factor Values IDs, Optimization Study and Trial, Validation Dataset and
Result, Candidate Selection, optional Frozen Result, Train-derived orientation,
metric summaries, evidence file hashes, and protocol names. Missing Frozen
evidence is `null`, never a synthetic zero. `family_id` equals `template_id` in
v1; `redundancy_group` remains `null`.

The builder validates formal artifact identities and hashes, exact
Optimization-to-Validation parameter lineage, Template lineage, Selection and
Frozen candidate-set parity, Frozen orientation, and the separate QM2-P0-006F
correction relationship. It reads metrics only from validated immutable
artifacts.

## Status model and derivation

The closed status set is `research_registered`, `validation_rejected`,
`validation_passed_not_selected`, `frozen_rejected`, `promotion_candidate`,
`approved`, `active`, `retired`, and `invalidated`.

Evidence derives the first five states. Incomplete Validation remains research;
failed Validation is rejected; a passed but unselected Trial records that exact
fact; a selected Trial that fails Frozen promotion gates is Frozen-rejected; only
all-machine-gates-passed evidence becomes a candidate. Decisions alone derive
approved, active, retired, or invalidated states. Reasons are deterministic and
stored with each Entry.

## Registry Snapshot, immutability, and exact existing

The identity is `frs_<sha256(canonical registry state)>`. Canonical state binds
schema version, full Promotion Policy, entries sorted by Factor Instance ID,
decisions sorted by `(created_at, decision_id)`, and the previous Snapshot ID.
It excludes publication time, absolute paths, usernames, and randomness.

Publication writes a staging directory, calculates a closed file inventory and
SHA-256 map, then atomically renames it. Reload verifies every hash, count,
identity, index, policy, Entry, and Decision. Rebuilding identical state returns
the existing Snapshot without mutation; any corrupt or conflicting existing
artifact is rejected. Runtime artifacts are placed under an explicit output root
(the QM2-P0-007 proof uses `/private/tmp/qm2-p0-007-registry`) and are not
committed.

## Reader and Agent boundary

The reader provides `load_registry_snapshot`, `get_registry_entry`,
`list_registry_entries`, `list_by_status`, `list_by_family`,
`promotion_candidates`, and `active_factors`. It returns frozen domain objects,
does not read Parquet or labels, does not rerun Validation, and cannot mutate a
Snapshot.

Future Agent Research may read tried Templates, parameters, families, failures,
and restrictions. It cannot edit entries, remove failures, access Frozen details,
approve or activate Factors, or tune the same parameter space after Frozen
observation. A new research iteration must create a new ResearchDecision and
Study.

## Current 14-entry proof

The real QM2-P0-005 and QM2-P0-006 artifacts produce Snapshot
`frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`
under policy
`fpp_6ca41655ea0ec5692ef2799674ef743a8bf91a6cf58718e124163bf033e255a3`.
It contains 14 entries in two Template families: 10 `validation_rejected`, one
`validation_passed_not_selected`, and three `frozen_rejected`. It contains zero
promotion candidates, approved Factors, or active Factors. A second build is an
exact-existing replay with the same identity.

This proves registration and governance behavior only. It does not prove an
Alpha, economic value, production readiness, or backtest return.

## Deferred persistence and API

Registry database tables, API/UI, durable artifact storage, actor authorization,
automated correlation-based redundancy, downstream LightGBM/Qlib consumption,
and activation operations are deferred. The immutable artifact is v1 authority.
