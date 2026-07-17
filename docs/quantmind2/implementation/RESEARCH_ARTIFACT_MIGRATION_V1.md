# Research Artifact Migration v1

The migration is copy-and-verify. It does not move, rewrite, delete, touch or
recompute `/private/tmp` research artifacts.

The plan starts from canonical Registry
`frs_c2ef675c...0237b5` and the Git-authoritative Fresh candidate lock,
protocol, exposure ledger and watermark. It follows formal Registry,
reconciliation, campaign, optimization, Factor Values, validation and Dataset
lineage. Git-only control IDs are optional roots; their Git authority is not
copied into the large-artifact Store.

Source discovery is an explicit catalog of formal published roots, never a
filename guess or bulk import of `qm2-*`. Each reachable source undergoes a
security scan and its existing Domain Validator before content-addressed import.
Missing and unresolved references are fail-visible and never trigger research
reruns.

## Current migration proof

- Reachability Plan: `rap_f3aca751ad751c976888fd9b464f9f56dd4913339b226786c0c3a7ef65ccc247`
- Reachable and migrated artifacts: 65
- Missing/unresolved sources: 0 / 0
- Logical bytes: 107,663,971
- Unique Blob bytes: 107,518,972 across 280 Blobs
- Deduplicated bytes: 144,999
- Logical-to-unique deduplication ratio: 1.0013485899
- Store Inventory: `sai_a0b9e6183a7bed95d9dbcce918a19c9e2f63a67ffbc7617a2091b7a37955d312`
- Integrity: healthy; zero issues and zero unreferenced Blobs

The migrated graph includes two Dataset Snapshots, 44 Factor Values, seven
Optimization Studies, Validation Dataset/Result/Frozen Result, five Registry
Snapshots, reconciliation, admission and two Campaigns. Unreferenced test and
diagnostic temporary directories were not migrated and were not deleted.
