# Registry Reconciliation v1

## Registry branch problem

Registry continuation and Registry reconciliation are distinct operations. QM2-P0-008 and QM2-P0-008F both consumed the same immutable Registry and independently published sibling snapshots. Neither sibling contains the other.

## Common ancestor and source snapshots

The common ancestor is `frs_436f4a966ea0c00ee2182c665813cd74cc13bb900a7022604ad9efc26849f2d9`. The sources are the sorted pair `frs_7ab0a844d791abf4dbd62c5558a7261078875bbc0b3606aa1b02ce591cf01054` and `frs_d40bfd7497ad56d3f71fd16dd7363222d32a5528e8780ca3765c27ca3c584718`.

## Entry merge

`factor_instance_id` is the merge key. A one-branch Entry is retained unchanged. Canonically identical duplicates are deduplicated and recorded. Differing content for one identity fails with `REGISTRY_ENTRY_MERGE_CONFLICT`; timestamps, metrics, Campaign type, or apparent quality never resolve a conflict.

## Decision merge and conflict handling

`decision_id` is the Decision key. Exact duplicates are deduplicated; differing content fails. Reconciliation does not create approve, activate, retire, or invalidate Decisions.

## Multi-parent lineage and canonical Registry

Reconciled snapshots use `factor-registry-snapshot-v2`, sorted `parent_registry_snapshot_ids`, and a `reconciliation_artifact_id`. Their identity binds the policy, full Entries, Decisions, and all parents. Legacy v1 snapshots retain `previous_registry_snapshot_id` and their original identity algorithm.

## Exact replay

Reconciliation and snapshot publication are immutable. An identical existing identity is validated and returned; differing content is never overwritten.

## Current reconciliation proof

`frr_9112702e368326365d6f4adb144633c7d0cf3ae59baa61ed76270ae86e93cb32` records 32 source Entry occurrences, 19 union Entries, 14 exact duplicates, zero conflicts, zero Decisions, and resulting snapshot `frs_f0a08cc472270cf80f2ae8c1141de17871dacbe2edccba8eb4ffe05ca45d3ba4`.
