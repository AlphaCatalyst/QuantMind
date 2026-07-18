# QM2-P0-012F Implementation Report

## 1. Task Summary

Completed `External Agent Proposal Contract Alignment and Successful
Store-backed Campaign`. The frozen Proposal, DSL, Optimization, novelty,
Registry and safety contracts were not relaxed. A real external Codex Agent
produced one valid parameterized Proposal, and the complete Store-backed path
through Development, Registry, cold recovery and exact replay succeeded.

## 2. Goal

Align external Agent output with the existing Proposal parameter contract by
deriving prompt guidance from the live DSL and Optimization contracts, return
structured repair diagnostics, and prove one successful bounded Campaign.

## 3. Scope

- Proposal parameter contract summary and structured error contract.
- External Agent and repair prompt alignment.
- Provider-compatible closed output schema.
- Four new immutable Research Goals: three diagnostic Provider-schema attempts
  and the successful v4 Goal.
- Real Store-required external Campaign, Store publication, cold recovery and
  exact replay.
- Focused tests, full relevant regressions and Project Memory.

## 4. Explicit Non-goals

- No DSL, Optimizer, Registry, Artifact Store or Artifact Runtime rewrite.
- No Validation, Frozen Test, Fresh evaluation or promotion.
- No structure evolution, model, signal, Qlib backtest or trading.
- No Baseline Agent substituted for external success.
- No database, API, UI, dependency, lockfile or deployment change.
- No mutation or reclassification of P0-012 evidence.

## 5. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `32dc6af0be24468da997e9e32e9627e23d360987`.
- Worktree: clean; unrelated dirty files: none.
- Store baseline: Inventory `sai_b0c038070f5e09a4f6ab261647c8686ef09c8e99bfc924afc2ced942c2370320`,
  66 artifacts, 287 blobs, healthy, zero missing/unreferenced.
- Registry-before: `frs_c2ef675c8ad3d17e1351e6193df706bff1820f16f1d6aaa35bd9aeb7050237b5`.
- Factor Lab remained read-only at the sole official source path. The previously
  established normalized content digest is
  `f8986f2787f330b4af02d0ea1bd8e944c3f847230c69ec8979d900f07a4f2635`.

## 6. Historical Contract Failures

P0-012 Campaign `rc_16bf571792c6a91fd22cb08149cb28a3de795572b0355000d40242b76548b7ea`
and Result `rcr_6b18f4c5984c832625cc728f8b561912488d35df69aa1406e1e1fc8de5376cc3`
remain immutable `partial` evidence with two calls, zero admitted Proposals and
zero Trials.

Call 1 raw output was recovered from the prior local Codex turn-completion
evidence, not from the Store. Proposal indexes 0 and 1 both supplied a
`placeholder` Template with `parameters=[]` and constant-zero AST, while their
search rows named undeclared `window` plus `beta_weight` or
`momentum_weight`. The exact formal classification is
`search_space_parameter_unknown`; both Templates were also constant-only and
their searched parameters had no AST use.

The repair response body was deliberately not persisted and was no longer
recoverable. The historical list normalization makes role names and Search
Space names identical, and the old parser's sole generic failure branch proves
that at least one such name was undeclared. It therefore has the same
retrospective `search_space_parameter_unknown` class, but exact Proposal index,
Template fields and AST location are unknown. This report does not fabricate
them. Only hashes and the generic rejection remain authoritative Store facts.

## 7. Parameter Contract Reality and Implementation

`ProposalParameterContractSummary` is generated from:

- `ParameterType` and `ParameterRole` enums;
- DSL parser required/optional parameter-field constants;
- AST-field and role-context constants used by the real role validator;
- the real Factor Optimization JSON schema; and
- mechanical examples that are executed through the real contract validator
  before being returned.

Control enforces declared = used = searched = role-assigned parameters,
single compatible AST role, supported role, Search Space type, finite/unique
values, Template bounds/default/step and Cartesian Trial budget. Signal
threshold remains unavailable in this pre-Signal Campaign.

The structured error includes Proposal index/ID, stable error code, field path,
declared/used/unused/searched parameters, role assignments and the closed set
of allowed repair actions. The orchestrator records it and exposes it only to
the existing single repair opportunity.

## 8. Prompt and Provider Alignment

The Agent is told to design the AST first, declare only actual variables, bind
each to one valid role, keep constants as constants, use matching Search Space
names and remain inside the Trial budget. Repair must return a full replacement
Decision and cannot change Goal, features, budget, security or output format.

Codex CLI `0.145.0-alpha.18` rejected nested `oneOf`, nested `anyOf` and
`uniqueItems` in three immutable bounded diagnostic Campaigns:

- `rc_29c2c3c9...c3655`, Result `rcr_ef164293...e32b1`, descriptor
  `sad_fad7a006...ec36`;
- `rc_01e211af...fcc47`, Result `rcr_78ad72c3...411f`, descriptor
  `sad_6285d618...e69d`;
- `rc_0cd43051...4cfe7`, descriptor `sad_e891411f...eb18`.

Each respected the two-call ceiling and stopped before model output, Decision,
Trial or Registry mutation. The Provider transport schema now uses only the
previously accepted closed-object/required/enum/const/numeric/array shapes,
with explicit-value rows and no optional Template `step`. Full Search Space and
semantic restrictions remain in Control. This is transport compatibility, not
contract weakening.

## 9. New Research Goal

Successful Goal:
`rg_decb8ade35d283ef078368da5d7c05e5c2c91a08b919debdf3a9208c21bf3109`.
It allows only `mom_ret_1d`, `liq_volume_ratio_5`, `style_beta_20` and
`style_idio_vol_20`, at most two Proposals, one admitted Template, six Trials,
at least one real bound parameter and contaminated 2025 Development only.

## 10. External Agent and ResearchDecision

Campaign `rc_4432a5d38895f7fb52d827d06050a13fb0efa89c6384096cd2cdc89281c04b56`
used `store_required`, `openai_codex_cli` and explicit `gpt-5.6-terra`. One
Provider call exited 0; no repair was attempted. Request SHA-256 is
`89e2cf78b13373380be1b023803b0b967deeeaeddbc04a497f65d46d81198f14`
and response SHA-256 is
`ce781c6e03c0fc81fd2df73f7c8b7be74423ce1b527c1a1cf42494a481727a99`.
No full prompt, secret or implicit reasoning is persisted.

Decision `rd_142a0fa45f4d6b84f52f22c8fc92a94ced5a549dc1daf27f9ed0fe3460ab9838`
contained one admitted Proposal `proposal_relative_momentum_liquidity_delta`.
Template `ft_115afad9b2575687b86343a217135f4b84b62cd1a2973d44ee2e808e0170aef1`
uses `liquidity_delta_periods` as both delta periods and rolling window and
`signal_weight` as the multiply scalar. Search is explicit values `[3,5]` and
`[0.4,0.7,1.0]`, respectively. Parameter contract, structural novelty and DSL
admission all passed.

## 11. Optimization and Development

Study `fos_22c2f3b6abfcdf72c33a86c6c7efc9364a090b5eea5ea867304c1b34919e8a84`
executed six of six Trials successfully with no failure or replay. The selected
Trial is `fot_cd22d4e13e1e2cbf150677855c51d7fb5edd1e9d183e4f024f1fec06bf0990db`,
parameters `liquidity_delta_periods=3`, `signal_weight=0.4`, selected Factor
Values `fv_937e5df1864bfd9afd48e1cf24cd09992b6f01e2ac98263d363e78023fda571a`.

Development result
`der_b8669e6b9b1452165208e7ea4fc281e734df677365e179a0d43ee50a1f89a92e`
records 242 valid 2025 dates, mean RankIC `0.03267607014444102` and RankICIR
`0.2933676647810775`. It also records `adaptive_research_only=true`,
`contaminated_period=true`, `predictive_claim=false`,
`eligible_for_registry_promotion=false`, `is_validation_evidence=false` and
`is_frozen_evidence=false`. These metrics are not an Alpha or OOS claim.

## 12. Registry and Store Publication

Registry `frs_9f61af9b95c3464833324ea82307d730f87239a30830b6fa726be60e29992052`
linearly references the required Registry-before, contains 20 Entries and adds
one `research_registered` Entry. Promotion / approved / active counts remain
0 / 0 / 0. No Fresh Admission was rerun.

The successful graph contains one Campaign, one Study, six Factor Values, one
Development bundle and one Registry: ten new domain Artifact IDs. The
Campaign-local runtime counter is captured before the final Campaign/Registry
wrapper publications (`published_artifacts=8`); the publication receipt and
Inventory establish all ten.

Across this task's three immutable diagnostics plus successful graph, Inventory
advanced to `sai_820983dba2894a3ddc3b8f0f94da7714bfdcaaddddc6c13da863aabb59ae5e68`:
79 artifacts, 339 unique blobs, 111,678,346 logical bytes, 111,482,350 unique
bytes and 195,996 deduplicated bytes. Delta from baseline is 13 artifacts, 52
new blobs, 31 reused-blob publication references, 4,004,004 logical bytes,
3,953,007 unique bytes and 50,997 deduplicated bytes. Integrity is healthy,
missing = 0 and unreferenced = 0. The baseline Inventory remains immutable.

## 13. Cold Recovery and Exact Replay

A new empty cache recovered and Domain-validated Campaign, Decision, Template,
Study, selected Factor Values, Development and new Registry solely from Git
controls plus Store. It used no legacy fallback or historical staging path and
preserved every ID/hash.

The same Goal, budget, Provider/model and Registry-before, from another new
cache, returned exact-existing Campaign, Result
`rcr_cea56734ed51df813b8dba0ccfcff58bad0763e2e9773d2c3e2ad0c82b2637af`
and descriptor `sad_72603dbe5cf57b76eb3baad198fa7dfa442dccf7ad10ff0aa77cefe02ef606de`.
Replay Agent/Optimization/Development calls, Registry writes, new artifacts and
new blobs were all zero.

## 14. Architecture, Security and Data Lineage Impact

No frozen architecture changed. The work strengthens the Decision/Control/
Execution boundary by presenting the existing contract mechanically and by
making repair diagnostics precise. External output remains untrusted; only
Control admits, executes and writes research-only Registry state.

No secret, raw row, label, Frozen/Fresh detail, path, executable code or
Registry document crossed the Agent boundary. Factor Lab was not modified.
Dataset/Validation Dataset, Candidate Lock, Fresh Protocol, Exposure Ledger,
Watermark and historical Registry snapshots are unchanged. New lineage binds
Goal, Decision, Template, Trial, Factor Values, contaminated Development,
Campaign, Registry-before/after and Store descriptors.

## 15. Files and Important Symbols

Production changes are limited to exposing live DSL/role constants, the new
`ProposalParameterContractError`, `proposal_parameter_contract_summary`,
`validate_proposal_parameter_contract`, Provider schema/prompt alignment and
orchestrator structured repair. Tests cover summary derivation, valid examples,
unknown/undeclared/unused/missing parameters, role mismatch, mixed roles,
type/bounds/default/step/value/budget failures, signal-threshold rejection,
Provider schema and safe prompt/evidence behavior.

Four Goal JSON files preserve every immutable formal attempt. Project Memory,
the Agent Campaign/Decision runtime contracts and this Run record describe the
successful and diagnostic evidence without changing historical Runs.

## 16. API, Database, Configuration and Dependencies

No network API, database migration/connection, runtime configuration,
dependency declaration or lockfile changed. No package was added to the
repository. Tests used an isolated cached tool environment because the active
shell exposed no project Python environment; this did not alter dependency
files.

## 17. Tests Executed and Results

- Focused parameter/Agent tests: 24 passed before final test additions.
- All Research Campaign tests after final additions: 56 passed.
- Real Goal validation and Campaign plan: passed.
- Real external Campaign: completed, one Agent call, six Trials.
- Store cold recovery: passed with full graph and zero legacy fallback.
- Exact replay: passed with all execution/write counters zero.
- P0-012 immutable replay/inspection: passed, partial facts unchanged.
- Final full relevant regression, Store integrity, Context Bootstrap, JSON,
  `py_compile`, Git diff, Manifest v2 and Planner results are recorded in the
  finalized Manifest.

## 18. Known Limitations

- Provider transport is limited to explicit-value Search Space rows because
  the installed Codex CLI rejects the richer nested schema keywords. Control
  retains the full formal validator.
- P0-012 repair response details are irrecoverable by design; only its generic
  validator branch and hashes remain. Exact Proposal/index facts are unknown.
- All 2025 Development feedback is contaminated and cannot support promotion.
- Artifact Store remains single-host; Campaign runtime remains offline,
  single-process and has no API/UI/database worker.
- Fresh eligibility remains 0/60 and no Fresh result exists.

## 19. Compatibility, Rollback and Remaining Work

Existing normalized list and internal dictionary Proposal Search Space forms
remain readable. Formal Optimizer integer ranges remain accepted by Control;
the current external Provider emits explicit values. Historical Campaigns,
Registry snapshots and Store inventories are immutable and unchanged.

Rollback is a normal revert of the single task commit. Store artifacts are
immutable evidence and must not be deleted or rewritten; reverting code only
restores the previous prompt/parser behavior and canonical Registry selection
in Project Memory.

The next task is only `QM2-P0-011B — Fixed-100-Universe 2019—2026 Agent
Iteration and Historical Backtest`. `QM2-FV-001` remains conditional and may
run only after at least 60 mature post-lock trading dates.

## 20. Git / Workspace State and Artifact Index

- Task status before commit: `completed_uncommitted`.
- Result commit: null in this immutable pre-commit Manifest.
- Intended commit: `fix(qm2): align agent proposals with parameter contract`.
- No amend and no push.
- Artifacts: this Report/Manifest, four Git Research Goals, four new Campaign
  artifacts (three diagnostic, one completed), one Study, six Factor Values,
  one Development result, one Registry successor and Inventory
  `sai_820983db...e5e68`.
