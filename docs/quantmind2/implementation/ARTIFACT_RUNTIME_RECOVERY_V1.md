# Artifact Runtime Recovery v1

Status: verified by `QM2-P0-011`

## 1. Empty-cache Recovery

Recovery starts with a new empty cache and `store_required`. The resolver reads
only immutable Store descriptors and blobs, materializes into that cache and
runs every Domain Validator. Legacy `/private/tmp` source artifacts are neither
arguments nor fallback inputs.

The recovery drill restored and validated these eight artifact roles without
changing their Domain IDs: Factor Values, Optimization Study, Validation
Result, Frozen Result, canonical Registry, baseline Campaign, external Codex
Campaign and Fresh Admission Result. Every materialized root was below the new
cache. The authoritative Store remained 65 artifacts and 280 blobs; no Inventory
was published.

## 2. Source-independent Research State

`recover_research_state(context, repository_root)` reconstructs read-only
`RecoveredResearchState` from Git Project Memory, Git Fresh control artifacts
and Artifact Store descriptors. It does not parse historical report prose.

The verified state is:

- canonical Registry: `frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5`;
- Registry entries: 19;
- Optimization Studies: 7;
- Campaigns: baseline and external Codex campaigns;
- Validation: `fvr_b9f247e42487267754d5e6128beb4f90a379b77853462b6ca25f0f2918c51ab0`;
- Frozen: `fvt_734478fcc0291910667321669e5b5293f64594efe6f0e5b1334779f4d921c787`;
- Fresh Admission: `fvar_89e61fe674bff1d10d46c9bea3913a456f236bbc191578291529736480a831ab`;
- Fresh eligible dates: 0, status `awaiting_first_fresh_date`;
- promotion candidates / approved / active: 0 / 0 / 0.

Candidate Lock, Exposure Ledger, Fresh Protocol and Watermark remain small Git
control artifacts. Recovery reads them but does not refresh mutable market data.

## 3. Campaign and Registry Recovery

The external Campaign
`rc_0b13d7f235ac948a10c97092c6ce3bbad99ecdefc2c20c93c3648644a5d9401c`
was resolved and validated from the Store with `exact_existing=true`,
`agent_calls=0`, `optimization_calls=0` and `registry_writes=0`. The baseline
Campaign is recovered in the same way. Registry recovery loads the canonical
snapshot directly and confirms 19 entries with no promotion candidate, approved
or active entry.

## 4. Validation Recovery and Frozen Boundary

Validation Result and Frozen Result recovery validates immutable content rather
than recomputing metrics. It does not grant the Agent, Optimizer or Campaign
Memory access to Frozen data. A Store miss is reported and is never treated as
permission to rerun Validation or reopen Frozen.

## 5. Hash, Identity and Write-path Proof

Descriptor verification checks the Store descriptor and all referenced blobs;
Domain validation checks each recovered artifact. Exact-existing publication of
one Registry, one Campaign and one Optimization Study returned their existing
references and left artifact and blob counts unchanged. Different cache roots
therefore cannot create a different Domain identity or Store object.

## 6. Recovery Procedure

1. Verify Store format and integrity against the recorded baseline Inventory.
2. Select `store_required` and a new empty cache.
3. Resolve the eight recovery roles by Domain Artifact ID.
4. Run `recover-state` and compare logical identities and counts.
5. Replay external Campaign and assert all execution counters are zero.
6. Reverify Store counts and integrity; do not publish a replacement Inventory.

Failure at descriptor, blob, cache or Domain validation stops recovery. It must
not trigger local-source discovery or recomputation.

## 7. QM2-P0-012 Partial Campaign Recovery

The subsequent production dry run published one immutable partial Campaign
after two bounded external Provider responses failed the strict Proposal
parameter contract. Inventory `sai_b0c03807...70320` contains 66 artifacts and
287 blobs with healthy integrity. A new empty cache recovered the Campaign and
unchanged canonical Registry from Store; exact replay returned Agent,
Optimization, Registry-write, new-artifact and new-blob counts of zero. No
Study, Factor Values, Development result or Registry successor exists for that
partial Campaign.
