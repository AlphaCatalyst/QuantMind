# QM2-P0-012 Implementation Report

## Task Summary

`QM2-P0-012 — Artifact-backed External Agent Campaign Production Dry Run`
executed one new bounded Campaign through the Store-required runtime. The real
Provider calls succeeded at transport level but both structured responses
failed the unchanged Proposal parameter contract, so the correct task result is
`partial`.

## Goal

Prove the production path from Git-governed Goal and Store inputs through a
real Codex Agent call, strict Decision admission, bounded execution, Store
publication, cold recovery and exact replay without legacy fallback or access
to Validation, Frozen or Fresh evaluation.

## Scope

- New content-addressed Research Goal restricted to four catalog features.
- Explicit production-dry-run budget and canonical Registry binding in CLI.
- Runtime read/publication counters and Campaign graph recovery.
- Store-ready immutable quarantined Development bundle support for successful
  future Campaigns.
- One real external Campaign, immutable Inventory, cold-cache recovery, exact
  replay, Project Memory, tests and this Manifest v2 Run.

## Explicit Non-goals

No relaxed Decision/novelty/DSL gate; no third Agent call; no new operator,
Optimizer algorithm, Validation, Frozen access, Fresh result, promotion,
Candidate Lock change, LightGBM, Qlib, model, signal, API, UI or database.

## Preflight State

- Repository `quantmind-main`, branch `master`, base
  `ded5c10c1650b98478633278201a42cb70c98e53`, clean worktree.
- Factor Lab stayed read-only; recorded source digest remained
  `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`.
- Codex CLI `0.145.0-alpha.18` was authenticated through ChatGPT.
- Baseline Inventory `sai_a0b9e618...55d312`: 65 artifacts, 280 blobs,
  healthy, zero issues and zero unreferenced blobs.
- Baseline artifact-set hash `9fbadcfb...6205`; blob-set hash
  `29803aae...5f1` under newline-sorted Domain IDs / blob hashes.

## What Changed

- Added mutable operational evidence counters to the otherwise immutable
  Runtime context and wired descriptor lookup, cache and publication events.
- Added Store-backed Campaign publication summaries, quarantined Development
  bundles and source-independent Campaign graph recovery.
- Made Registry-before and the exact tiny budget explicit CLI inputs while
  retaining the existing bounded defaults.
- Removed the hard-coded canonical Registry from recovery; Project Memory or
  an explicit recovery argument now supplies it.
- Added Goal `rg_6929cb83...1f55ce`, focused tests and current Inventory/Run
  references in Project Memory.

## Why It Changed

The QM2-P0-011 runtime could resolve and replay historical artifacts, but a new
Campaign still inherited an old Registry constant and the default large budget,
and had no observable Store counters or independent Development recovery seam.
Those gaps prevented a truthful production dry run under this task's fixed
contract.

## Files Changed

The Manifest `changed_files` is the authoritative business inventory. Its own
Manifest is excluded from business ChangedFiles and included in Git integrity
inventories; this Report remains included.

## Important Classes / Functions / Documents

- `ArtifactRuntimeEvidence`, `resolve_artifact`, `publish_domain_artifact`
- `publish_campaign_execution`, `resolve_development_result`
- `recover_research_state`, `recover_campaign_graph`
- `publish_development_bundle`, `validate_development_bundle`
- production-dry-run budget profile and new Research Goal

## API Changes

No network API. Python/CLI contracts add runtime evidence, optional canonical
Registry recovery, Campaign graph recovery, explicit Registry-before and one
named bounded budget profile.

## Database Changes

None. No database was connected or migrated.

## Configuration / Environment Changes

No dependency, lockfile or deployment configuration changed. Formal execution
used `store_required` and cache-only staging below the user's cache directory;
no physical path participates in a Campaign identity or Store descriptor.

## Runtime Flow

Git Goal plus Store Dataset/Development Dataset/canonical Registry/all existing
Study descriptors were resolved into verified cache materializations. The
Agent received only Goal, sanitized fingerprints and the closed Decision
contract. Strict parsing ran before any DSL, Optimization or Registry action.

## External Agent Result

Campaign `rc_16bf5717...b7ea` bound Provider `openai_codex_cli`, explicit model
`gpt-5.6-terra`, Registry-before `frs_c2ef675c...0237b5` and the fixed budget.
Both CLI calls exited 0. Call 1 used 15,832 input / 810 output / 255 reasoning
tokens; the one repair used 15,839 / 810 / 370. Both request/response SHA-256
values, CLI version, effective model, exit code and repair flag are in Campaign
events. Complete prompts and credentials were not stored.

Both responses violated `Proposal parameter contract is invalid`. Control used
the sole permitted repair, rejected it for the same reason, stopped with
`agent_contract_failure`, and published a `partial` Campaign. No Decision,
Proposal admission, Template, Study, Trial, Factor Values, Development result
or Registry successor was created. This is not an Alpha discovery.

## Store and Inventory Result

Only the partial Campaign was new: descriptor `sad_2e42bc...7b18b`, seven new
blobs, 10,371 new logical and unique bytes, zero reused blobs and zero
deduplicated bytes for this increment. Inventory
`sai_b0c03807...70320` contains 66 artifacts and 287 unique blobs, remains
healthy, and has zero missing/unreferenced blobs. Final artifact-set hash is
`f2263cc0...1623`; blob-set hash is `dd53e76f...08ea`.

## Cold Recovery and Exact Replay

A new empty cache recovered and Domain-validated the partial Campaign and
unchanged canonical Registry solely from Git controls plus Store. The recovered
graph truthfully reports null Decision/Template/Study/Development and an empty
Factor Values list. Registry remains 19 entries with promotion / approved /
active = 0 / 0 / 0.

The exact same Goal, budget, Provider/model and Registry-before returned the
same Campaign/Result/Descriptor with `exact_existing=true`, Agent calls = 0,
Optimization calls = 0, Registry writes = 0, new artifacts = 0 and new blobs =
0. The post-replay Inventory ID and counts were unchanged.

## Architecture Impact

No frozen architecture changed. The work strengthens the accepted Store and
Decision–Control–Execution boundaries. Provider success remains distinct from
Decision admission, and a partial Campaign remains immutable evidence rather
than a reason to weaken Control.

## Security Impact

The Agent subprocess remained ephemeral/read-only with an allowlisted
environment. Runtime evidence excludes Store/cache paths, usernames, secrets,
full prompts and Factor Values. Legacy fallback was false. Frozen, Validation,
Fresh and target data were not exposed to the Agent.

## Data Lineage Impact

Canonical Registry, Candidate Lock, Fresh Protocol, Exposure Ledger and
Watermark are unchanged. The new Campaign is linked to its Goal,
Registry-before, Dataset/Development Dataset, Provider/model and budget. It has
no factor lineage because strict admission never succeeded.

## Tests Executed

- First focused invocation: 53 tests passed, but the command exited nonzero
  because repository-wide coverage was 3.62% versus a 5% global threshold.
- Same focused set with `--no-cov`: 53 passed.
- Expanded Runtime/Store/Campaign/Registry unit set: 86 passed.
- Pre-run real Store recovery/regression: 6 passed.
- Post-run full relevant regression, real Store, Context, JSON, `py_compile`,
  Bootstrap, Factor Lab digest and Git diff checks are recorded in Manifest.
- Final manifest/indexer/context regression: 42 passed; Context Bootstrap
  completed all 42 checks; the Manifest v2 payload and domain bundle validate.

## Test Results

All test cases executed for behavior passed. The one command-level failure was
only the unrelated global coverage threshold and was immediately isolated and
re-run without coverage; it did not hide a test failure.

## Known Limitations

- The task is partial because no external Proposal passed the frozen parameter
  contract; therefore successful-path Study/Factor Values/Development/Registry
  publication and cold recovery were not exercised by this live Campaign.
- The new Development bundle path is covered by isolated tests only in this
  Run. It created no Development artifact for the partial Campaign.
- Store/cache remain single-host filesystem implementations.
- Fresh remains 0/60 and `awaiting_first_fresh_date`.

## Compatibility / Migration Notes

Default Campaign budgets remain unchanged; the production dry-run profile is
opt-in. Historical Campaigns and Store artifacts are immutable and replayable.
Recovery now follows Project Memory instead of a source-code Registry constant.

## Rollback Notes

Revert the containing commit to remove code/docs changes. Do not delete or edit
the immutable partial Campaign, its blobs, receipts or Inventory; they remain
truthful execution evidence. Cache directories may be discarded safely.

## Remaining Work

Create the single containing commit and perform post-commit Planner
verification. Do not retry or repair this Campaign within the same identity.

## Recommended Next Task

`QM2-P0-011B — 2019—2026 Historical Diagnostic Backtest`.

`QM2-FV-001` remains conditional and forbidden until at least 60 mature
post-lock trading dates exist.

## Git / Workspace State

This Run is produced before its single containing commit. `result_commit` is
null, task status is `partial_uncommitted`, and canonical status is
`noncanonical`. Publication status is resolved from Git after commit.

## Artifact Index

- This Report and Manifest v2.
- Goal `rg_6929cb83...1f55ce`.
- Store Campaign `rc_16bf5717...b7ea`, descriptor `sad_2e42bc...7b18b`.
- Inventory `sai_b0c03807...70320`.
