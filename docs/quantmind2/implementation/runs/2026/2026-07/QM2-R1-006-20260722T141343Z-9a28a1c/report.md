# QM2-R1-006 Implementation Report

## 1. Task Summary

- Task: `QM2-R1-006 — Default-first Optimization Governance v2`
- Result: completed, pending the containing commit and post-commit Planner
- Base: `9a28a1cf363d221a6228335f3c5da4ab9782265a`
- Branch: `master`
- Governance Decision: `ogd1_7de0ba81247dc226aa305c42f2e893225a0906cfae0d30f881b3c7d5f911f7f5`

## 2. Goal

Apply the completed-corrected R1-005 business decision to new research:
evaluate explicit Agent defaults first, stop after a pass, permit only bounded
one-hop local rescue after failure, and suspend combined Factor/Strategy
parameter optimization.

## 3. Scope

- FactorOptimizationPolicyV2 and StrategyOptimizationPolicyV2.
- CombinedOptimizationPolicyV1 suspension and Plan-time hard failures.
- Default-first evaluations, local-neighborhood planning and rescue evidence.
- Diagnostic-only full-search modes, Candidate metadata and search accounting.
- CLI gates, machine-readable schemas and human-readable contracts.
- Four immutable policy/decision artifacts, cold recovery and exact replay.
- Tests, Project Memory, Report and Manifest v2.

## 4. Explicit Non-goals

- No Agent, Factor Optimization Trial, Strategy Optimization Trial, Qlib,
  Tushare or network execution.
- No Candidate, Registry lifecycle, Promotion, Factor Template, Factor
  Instance, Unified Signal, Strategy Result, Dataset, Label or historical
  Artifact mutation.
- No rewrite of R1-003, R1-004, R1-005 or R1-005F evidence.
- No dependency, lockfile, database, API or Qlib algorithm change.

## 5. Preflight State

- Repository root: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`
- HEAD/base: `9a28a1cf363d221a6228335f3c5da4ab9782265a`
- Worktree: clean
- Unrelated dirty files: none
- `git diff --check`: passed
- The R1-004, R1-005 and R1-005F Reports, Manifests, contracts and Project
  Memory were read before implementation.

## 6. Source Decision

R1-005 Assessment `poa1_15e9398...c69f1a` records
`default_first_optimize_only_on_failure` for Factor and Strategy and
`suspend_parameter_optimization` for Combined. R1-005F corrects only Git
evidence and establishes the supported `completed_corrected` Ledger
interpretation. This task does not change any ablation result.

## 7. What Changed

- Added an independent `optimization_governance` domain with immutable policy
  objects, explicit evidence classes, pure planners/evaluators, Candidate Lock
  metadata validation, Store publication and replay.
- Registered four Artifact kinds and cache locations with formal domain
  validation.
- Added an offline CLI with the four requested mode/diagnostic flags.
- Added three accepted policy contracts and four JSON schemas.
- Added 37 focused tests and updated Project Memory/current-task validation.

## 8. Factor Policy Runtime

Agent defaults are mandatory. Missing/null defaults hard-fail as
`AGENT_DEFAULT_PARAMETERS_MISSING`; midpoint, first-Trial, historical-best and
code-default inference do not exist. A passing default yields one evaluation,
zero optimization calls, `default_parameters` evidence and
`selection_reason=default_parameters_passed`.

After a default failure, the local set contains the default plus immediately
adjacent legal values, changing one parameter at a time. The planned and
runtime budget is bounded by `min(1 + 2*n, 7)`. A passing local result sets
`optimization_rescued=true`, retains default evidence/reasons, neighborhood,
selected local parameters, gain and counts, and remains ineligible for
Promotion.

## 9. Strategy Policy Runtime

The immutable default is TopK 20, n_drop 5, rebalance 5, equal-weight, lag 1,
open execution. A pass stops with zero strategy-optimization calls. A failure
permits only the exact seven configurations in the contract, always satisfying
`n_drop < topk`. Rescue evidence retains default metrics/reasons, local Trials,
selected parameters, gain, turnover change and cost change.

## 10. Full Search Diagnostic Boundary

Factor and Strategy full-search modes default to disabled and require their
explicit `allow-full-*-search-diagnostic` flags. Their evidence is
`full_search_diagnostic`, `usable_for_candidate_selection=false` and
`usable_for_promotion=false`; it cannot source Candidate Lock parameters or
write historical-best values back to a Strategy Spec.

## 11. Combined Optimization Boundary

Combined status is `suspended`. Simultaneously non-default Factor and Strategy
plans or outcomes hard-fail with
`COMBINED_PARAMETER_OPTIMIZATION_SUSPENDED`. Allowed paths are F0S0, failure-
gated F1S0 and failure-gated F0S1. If both defaults fail, only local Factor
search with default Strategy is planned; Strategy search does not follow.

## 12. Candidate and Search Evidence

New Candidate Locks require all twelve optimization metadata fields. Full
diagnostic evidence and Promotion/approved/active/production claims are
rejected. Search budgets record Templates, Factor Trials, Strategy Trials,
total selection count and effective search count including failed Trials.

Evidence risk ordering is `default_parameters` greater than
`local_optimization_research` greater than `full_search_diagnostic`; it
expresses lower overfit risk, not predictive strength. Historical evidence is
explicitly `historical_legacy_optimization`.

## 13. CLI and Planner

`tools/quantmind2/optimization_governance.py` supports plan, publish, validate,
recover and replay plus Factor/Strategy modes and explicit full-diagnostic
gates. Plan emits the seven required Trial fields. Defaults plan both default
evaluations and `combined_optimization_allowed=false`; two non-default modes
are rejected before execution.

## 14. Artifact Store

Published immutable artifacts:

1. Factor policy `fop2_32ca8b27...d446161`
2. Strategy policy `sop2_f7dcc13f...4f667b7`
3. Combined policy `cop1_c7876052...265887e`
4. Decision `ogd1_7de0ba81...911f7f5`

The Decision binds tasks R1-005/R1-005F, the exact source Assessment, all
three policy artifact IDs, the three decisions, `auto_applied=true` and
`effective_from_task=QM2-R1-006`. It records no historical or Candidate-state
mutation. After publication the real Store contains 636 Artifacts and 3,329
Blobs, with Integrity healthy, Missing 0 and Unreferenced 0.

## 15. Cold Recovery and Exact Replay

Cold recovery formally validates all four artifacts. Exact replay restores
all four and reports Agent 0, Factor Optimization 0, Strategy Optimization 0,
Qlib 0, network 0, Promotion 0, new Artifacts 0 and new Blobs 0. Artifact and
Blob counts remain unchanged across replay.

## 16. Historical Compatibility

Existing Optimization Studies and Trials retain `legacy_or_v1` semantics and
their bytes. Both R1-003 locks remain `research_registered`; no default
rollback, backtest rerun, DSL/AST/orientation change or Registry transition was
performed. The v1 Factor and Strategy engines remain available behind the new
governance boundary and were not reimplemented.

## 17. Files Changed

The adjacent Manifest `changed_files` array is authoritative. Changes are
limited to the new governance package/CLI/contracts/schemas/tests, Store kind
registration/cache validation, Project Memory, its bounded validator/test,
and this Implementation Run.

## 18. Important Classes and Functions

- `FactorOptimizationPolicyV2`, `StrategyOptimizationPolicyV2`,
  `CombinedOptimizationPolicyV1`, `OptimizationEvidenceClass`.
- `require_agent_defaults`, `local_factor_neighborhood`, `evaluate_factor`,
  `evaluate_strategy`, `plan_governance`, `validate_combination`.
- `build_candidate_metadata`, `validate_candidate_lock_metadata`,
  `build_search_budget`, `execute_governance`, `replay_governance`.
- `publish_artifact` and `validate_artifact`.

## 19. API, Database and Configuration Changes

No API, database, migration, runtime service configuration, dependency or
lockfile change. ArtifactKind and runtime-cache catalogs were extended for the
four new formal kinds.

## 20. Architecture, Security and Data Lineage Impact

The change enforces ADR-0008's separate optimization layers and ADR-0007's
immutable lineage. It consumes corrected R1-005 evidence without rewriting it.
No credential, token or market-data payload is accepted. No network or
database connection occurs. Dataset, Candidate and source Assessment IDs stay
explicit and immutable.

## 21. Tests Executed

- Focused plus directly relevant optimization/Store/runtime/context regression:
  129 passed, 0 failed, 0 skipped.
- Context Bootstrap: 42 checks passed.
- All QuantMind2 JSON: parsed successfully.
- New Python package and CLI: `py_compile` passed.
- Formal CLI plan/publication/replay: passed; 4 artifacts published and 4
  recovered with all forbidden/replay call counts zero.
- `git diff --check`: passed.
- One initial aggregate pytest command referenced nonexistent
  `test_context_files.py` and ran no tests; the corrected 129-test command is
  the result claimed above.
- One attempted cleanup-plus-replay shell command was rejected by the command
  safety boundary before execution; replay was rerun in a fresh path and
  passed without cleanup.
- Post-commit Planner is pending the containing commit and is not claimed here.

## 22. Known Limitations

- Governance applies only to new research; historical objects are not
  migrated or relabeled in place.
- A local rescue remains contaminated research evidence until independent
  new-time validation exists.
- The policy layer plans and gates execution but does not invent the concrete
  Eligibility or Strategy Gate used by a research task.
- Full search remains callable only as an explicitly enabled diagnostic; this
  task executes none.
- The Store is the existing single-host filesystem implementation.

## 23. Rollback and Compatibility

Revert the single task commit to remove runtime governance, schemas, tests and
Project Memory changes. The four immutable Store artifacts are evidence and
are not deleted by source rollback. Existing v1 Studies, Trials and Candidate
Locks require no migration and remain unchanged.

## 24. Remaining Work and Recommendation

Only the containing commit and post-commit Planner admission remain for this
Run. This task authorizes no next business task and makes no recommendation.

## 25. Git and Workspace State

- Run: `QM2-R1-006-20260722T141343Z-9a28a1c`
- Task status before commit: `completed_uncommitted`
- Result commit: null before commit
- Suggested commit: `feat(qm2): enforce default first optimization governance`
- Commit: one planned; no amend; no push
- Expected final worktree: clean
