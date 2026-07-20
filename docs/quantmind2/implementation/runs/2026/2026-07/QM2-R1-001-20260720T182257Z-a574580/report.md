# Implementation Report — QM2-R1-001

## 1. Task Summary

Implemented and executed Tushare Expanded-feature Agent Factor Iteration v2.
The task recovered the three existing Factor definitions, built a 24-feature
PIT-safe Fixed-100 Dataset, ran six bounded external-Agent rounds with four
independent walk-forward Folds per Template, performed formal Qlib comparison,
locked one research-only Candidate, published immutable Store evidence, and
verified cold recovery and exact replay.

## 2. Goal

Return from strategy-parameter tuning to Factor research and test whether an
expanded Tushare daily price/volume Feature space can produce a more stable,
less correlated and tradable Factor under a fixed strategy protocol.

## 3. Scope

- Existing formal Factor-definition recovery and failure-memory sanitization.
- Tushare Feature Catalog/Dataset v2 for the immutable Fixed-100 universe.
- Feature quality and structural/equivalence redundancy gates.
- Bounded `openai_codex_cli` structure proposals and factor-only parameter
  search through four expanding walk-forward Folds.
- Fixed formal Qlib evaluation, Candidate eligibility and ordering.
- Post-lock 2025/2026H1 retrospective reports and old/new comparison.
- Immutable Artifact Store publication, cold recovery, exact replay, CLI,
  tests, contract documentation and Project Memory.

## 4. Explicit Non-goals

- No Strategy parameter or combination-weight search.
- No universe, Label, benchmark, cost, lag or execution-price change.
- No 2025/2026H1 selection or Agent feedback.
- No Fixed-100-relative selection evidence.
- No Tushare network collection or retired QuantMind data.
- No Fresh Validation, Frozen Test, Promotion, approval, activation,
  production Alpha, LightGBM, API, database or UI work.

## 5. Preflight State

- Repository: `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com/`
- Branch: `master`
- Base commit: `a574580a61b57c17c0215f69ae350efadbdb37be`
- Working tree: clean
- Unrelated dirty files: none
- Factor Lab formal path was read-only; at final verification it contained no
  source files outside `__pycache__`, so its earlier content digest could not
  be re-established. No Factor Lab file was read as runtime authority or
  modified by this task.

## 6. What Changed

Added the `expanded_factor_iteration` domain, formal artifact kinds and Store
validation/cache routing, a nine-command CLI, focused and opt-in real tests,
the v2 contract, Project Memory updates, and this Implementation Run.

## 7. Why It Changed

The prior Strategy Optimization proved that changing TopK/n_drop/rebalance did
not repair weak and unstable Factor behavior. This task isolates Factor quality
by expanding only PIT-safe input features while freezing the portfolio and
formal Qlib execution contract.

## 8. Existing Factor Definition Audit

All three existing formulas were recovered before the first Agent call:

1. `cs_rank((rolling_mean(mom_ret_1d,window=momentum_window) /
   (liq_volume_ratio_5 * (absolute(style_beta_20) + 1))))`
2. `cs_zscore((rolling_mean(liq_volume_ratio_5,window=liquidity_window) -
   absolute(style_beta_20)))`
3. `cs_rank((rolling_max(mom_ret_1d,window=peak_window) /
   (rolling_mean(style_idio_vol_20,window=peak_window) + 1)))`

Audit `efda_289b89c147a0c0e539c71130daec20ba1ee75a94ca563d1a6c7a8e8d58bc052a`
binds the complete AST, Template/Instance, parameters, orientation, values,
Unified Signal, fingerprints, economic hypothesis, risks and explanations.

## 9. Feature Catalog and Quality

Catalog `tfc2_7d996ee8101ddc7710e2997347b3e8e8a4e0249a25de8aa651d3a575c821c21e`
selected 24 of 26 computed features. Dataset
`tfd2_ee90879ccb5b311f9690ab418b832548ff74637c6a83d51fb3a9095e5ca2e407`
contains 180,241 Fixed-100 rows for 2019-01-02..2026-06-23 in
Parquet/Zstandard. All selected features pass overall >=90% and annual
2021--2024 >=85% finite coverage, Infinity 0 and duplicate keys 0. Computation
uses adjusted prices where specified, continuous cross-year rolling state and
no forward/backward/zero fill.

## 10. Experiment Runtime and Rounds

The experiment completed six rounds, six successful real external Agent calls,
12 admitted Templates, 38 factor-parameter Trials and 50 formal Qlib calls.
Per-round admitted/trials/eligible counts were 2/2/0, 2/6/0, 2/9/0, 2/6/0,
2/9/0 and 2/6/1. All four evaluation Folds were retained. Rounds did not
continuously improve; the run stopped only after the sixth-round ceiling.

## 11. Candidate and Four-fold Result

The sole eligible Candidate is Template `ft_e05bf43fe114790376fb10d27499f43f848cf536b34e1e3f9485c5eb0157d8c7`,
Instance `fi_e2dd60578eb2d4a08b83096b53a549c3e8375768b0496adc5d14ed2be0d8576f`:

`cs_rank((rolling_mean(amount_ratio_5,window=change_window) /
(absolute(delta(price_vs_ma_60,periods=change_window)) + 1)))`

Each Fold independently selected `change_window=15`. RankIC by 2021--2024 is
0.001418, 0.001463, 0.010168 and -0.004723. CSI300 net excess is 21.36%,
14.49%, 9.91% and 19.26%. Median turnover is 35.317, below the formally derived
weak-factor median, and maximum old-factor correlation is 0.2757.

Lock `afcl_27fb695b24bf92a63fb8a57e55bfdb102a675935e951b12184d7b9e8f6aba51e`
is `research_registered`; predictive claim, Promotion and production flags are
false.

## 12. Later-period Reports

The Candidate was frozen before opening later periods. In 2025 it records
RankIC 0.012743, net return 10.83%, CSI300 return 21.75%, CSI300 excess -10.91
points, Sharpe 0.675, drawdown -7.11%, turnover 32.58 and best-ten-days
contribution 19.87%.

In 2026H1 it records RankIC 0.012733, net return -16.56%, CSI300 return 4.27%,
CSI300 excess -20.84 points, Sharpe -2.735, drawdown -17.94%, turnover 16.94
and best-ten-days contribution 13.37%.

These are retrospective reports, not independent out-of-sample evidence.

## 13. Contract Revision

The first immutable Candidate Lock contained canonical AST but omitted the
explicit readable `canonical_dsl` field required by the task contract. No
Artifact was overwritten and no research was repeated. Contract revision 2
published a superseding Candidate Lock, Assessment and Experiment derived only
from the existing immutable evidence. Revision publication made zero Agent,
Optimization, Qlib, network or Promotion calls. Exact replay selects the unique
highest revision.

## 14. Files and Important Symbols

- `backend/services/engine/expanded_factor_iteration/`: audit, feature
  computation/quality, redundancy, protocol, artifact and orchestration logic.
- `tools/quantmind2/run_agent_factor_iteration_v2.py`: nine-command CLI.
- `backend/services/tests/test_expanded_factor_iteration*.py`: synthetic and
  real Store-backed verification.
- `EXPANDED_FEATURE_AGENT_FACTOR_ITERATION_V2.md`: frozen executed contract.
- Important functions: `build_existing_factor_audit`,
  `compute_feature_candidates`, `quality_and_selection`, `assess_template`,
  `run_experiment`, `replay_experiment`, `validate_artifact`.

## 15. API, Database, Configuration and Dependencies

No API endpoint, database migration/table, runtime configuration, dependency,
lockfile, model, UI or trading code changed. The existing Python environment
and installed Qlib/Parquet stack were reused.

## 16. Architecture Impact

Introduces an executed bounded research orchestration component over existing
Tushare authority, Factor DSL/Optimization, Research Agent, Artifact Store and
formal Qlib boundaries. It does not replace those components or change their
authority. Agent remains structure-only; Control selects parameters; Registry
status remains research-only.

## 17. Security and Data Lineage Impact

No secret or token is accepted or persisted. Agent Memory excludes daily
labels/IC/returns, stock contributions, later-period results and Fixed-100
relative evidence. Dataset lineage binds Tushare normalized bars, Fixed-100
lock, Feature Catalog and Label Dataset. All large values remain in immutable
Store/Parquet artifacts.

## 18. Artifact Store, Cold Recovery and Replay

Final Inventory `sai_5a2ff03af923402be13f2882a4018dfb7db38e427505153f5daee82ad35c17ac`
records 285 artifacts / 2,508 unique blobs, healthy, Missing 0 and Unreferenced
0. Fifteen original/superseding v2 Artifacts cold-recover and validate. Final
Experiment is `afi2_78fe313863910ce2cd47409ac1fbe66dbedaea1bfc8815a0e09f261288d57fcf`.
Exact replay returns this ID with zero Agent, Optimization, Qlib, network,
Promotion, new Artifact and new blob counts.

## 19. Tests Executed and Results

- Domain tests: 10 passed.
- Opt-in real Store/replay/cold-recovery tests: 5 passed.
- Combined relevant regression: 144 passed.
- Manifest v2, Ledger Indexer and Context pytest regression: 42 passed.
- Context Bootstrap: 42 checks passed.
- All nine CLI commands executed successfully, including formal `execute`,
  replay `execute`/`validate-experiment`, and inspection commands.
- `py_compile`, JSON parsing and Git whitespace checks pass before commit.

## 20. Known Limitations

- Evidence is retrospectively contaminated and cannot support a predictive
  claim or Promotion.
- Only one Candidate passed; it underperformed CSI300 in both exposed later
  periods despite positive RankIC, so the result is mixed.
- Candidate turnover improves only marginally versus the weak-factor median;
  best-day dependence is not uniformly below every existing Factor.
- The runtime is single-process and local-Store based; no API, UI, distributed
  worker or LightGBM consumer is introduced.
- Existing formal Qlib logs attempt an optional model-registry resolution and
  report missing `asyncpg`; supplied signal execution nevertheless completes
  through the formal chain and is asserted from result artifacts.
- The official Factor Lab `/tmp` source directory currently has no source
  files outside cache entries; this task did not modify or depend on it.

## 21. Compatibility, Rollback and Remaining Work

Artifact kinds and cache routing are additive. Rollback is the single task
commit; immutable Store artifacts remain historical evidence and should not be
deleted or rewritten. No migration is required. No next task is authorized by
this contract; a future explicit task must decide whether and how to validate
the research Candidate.

## 22. Git / Workspace State

The task is prepared as one commit with message
`feat(qm2): run expanded feature factor iteration`. No amend or push is
performed. Post-commit Planner verification is required before final handoff.

## 23. Artifact Index

- Existing audit: `efda_289b89c...bc052a`
- Feature Catalog: `tfc2_7d996ee8...21c21e`
- Feature Dataset: `tfd2_ee90879c...2e407`
- Candidate Lock revision 2: `afcl_27fb695b...ba51e`
- Assessment revision 2: `afia_51634883...ee7ff`
- Experiment revision 2: `afi2_78fe3138...7fcf`
- Store Inventory: `sai_5a2ff03a...c17ac`
