# QM2-R3-001 Implementation Report

## 1. Task Result

`completed_uncommitted`

`QM2-R3-001 — Rolling 60-Day Blind Validation and Continuous Alpha Discovery
v1` implements the rolling historical Blind boundary and completes formal
Discovery Batch 001. Zero Survivor is the valid unchanged-gate result.

## 2. Preflight State

- Repository:
  `/Users/yj/Documents/Codex/2026-07-13/qusong0627-quantmind-git-https-github-com`
- Branch: `master`.
- Base commit: `addae3914c45089a5cb33e7a5a1e7c7151af05c6`.
- Workspace dirty before: false.
- Unrelated dirty files: none.
- Existing Artifact Store: 2,021 Artifacts and 6,753 Blobs, healthy, zero
  missing/unreferenced before execution.
- Formal Supervisor:
  `arsv1_1d07cf5c773e0fef1c7855b874235405e8c1e0e247caa1f4af51876aecabd14e`.
- The official Factor Lab `/tmp` source was read-only by contract and was not
  modified. At final verification the volatile source root no longer existed,
  consistent with the already-recorded long-term `/tmp` availability risk.

## 3. Mainline Guardrail

`mainline_blocked = false`

The formal Batch ran to a valid terminal state. No data leakage, Label error,
backtest error, damaged market authority, persistence failure or unreplayable
result remains. Optional PostgreSQL/COS resolution warnings from the reused
backtest wrapper did not replace or invalidate local formal Qlib execution.

## 4. Existing Research Audit

The implementation reuses the existing Autonomous Research Supervisor,
Archetype-aware Alpha Program, Technical Feature Catalog v3, Factor DSL,
Fixed-configuration LightGBM Program, canonical Tushare artifacts, formal Qlib
runner and immutable Artifact Store. It does not create a parallel research
system.

Existing real Fresh candidate, lock, cohort and heartbeat identities were
captured before the Batch and remained unchanged. Fresh metrics were never
read by Agent, Planner, Discovery or rolling Blind validation.

## 5. Rolling Blind Architecture

`rolling_blind_alpha_discovery` provides:

- frozen window and Batch specifications;
- two isolated Discovery lanes;
- round-level Agent response/result checkpoints;
- immutable Candidate Batch Lock;
- one Artifact per candidate/window;
- complete rolling gate and window-level one-sided test;
- one global Benjamini-Hochberg family;
- Search Exposure and Blind Submission Ledger;
- conservative Survivor and no-backfill Fresh boundaries;
- cold validation, resume and exact replay.

The Supervisor exposes `run-next-rolling-blind-batch`; existing inspect commands
read Window Set, Lock, Result, Survivor and Search Exposure artifacts.

## 6. Window Set

- Window Set:
  `rbws1_4e8166c3a9d5699d39cac1a776165a311d1b2a6da85eb3c02187cd9405c16259`.
- Requested Blind Pool: `2022-01-04..2026-07-23`.
- Canonical calendar available: `2022-01-04..2026-06-24`.
- Complete windows: 18.
- Each window: exactly 60 official sessions.
- First window: `2022-01-04..2022-04-06`.
- Last complete window: `2026-03-25..2026-06-23`.
- Excluded tail: one session, `2026-06-24`.
- Overlap: none.
- Frozen before Agent calls: true.
- Performance-selected boundaries: false.

No synthetic dates were added to reach the requested upper bound.

## 7. Discovery/Blind Isolation

Agent prompts contain only 2019—2021 Discovery context, static authorized
features/operators, structural fingerprints and unlabeled admission failures.
They contain no rolling Blind result, 2025/2026 slice or real Fresh evidence.

All Blind result artifacts record:

- `agent_visible = false`;
- `planner_visible = false`;
- `failure_memory_visible = false`;
- unchanged configuration;
- zero Promotion writes.

The final failure list explicitly records no feedback to Agent, Planner or
Failure Memory.

## 8. Batch 001 Spec

- Batch:
  `rbdb1_6ca989dfab231a2b57fb3679d2dbca8006a370bc082d1b6b2f55840479f88851`.
- Name: `rolling_blind_discovery_batch_001`.
- Maximum rounds/Agent calls/proposals/admissions: `24/24/72/48`.
- Maximum local rescue/model hypotheses/Qlib: `72/6/300`.
- Maximum Blind submissions/Survivors: `20/5`.
- Strategy: TopK 20, n_drop 5, rebalance 10, equal weight, lag 1,
  open execution, CSI300.
- Strategy Optimization calls: 0.
- Combined Optimization calls: 0.
- Promotion writes: 0.

## 9. DSL Lane

The DSL lane ran 18 automatic Agent rounds across three authorized lanes, at
least eight families and both predeclared Archetypes. It used explicit defaults
and only four one-hop local rescue trials. Full parameter search and post-hoc
Archetype switching were absent.

The first four rounds were preserved as truthful failed checkpoints while a
date-key compatibility defect was diagnosed. The runtime then resumed without
repeating those Agent calls. Later rounds produced 18 admitted DSL objects, but
none satisfied the complete unchanged Discovery gate, so no DSL object entered
the Batch Lock. The gate was not lowered.

## 10. Model Lane

Six fixed, unlabeled Feature Bundle hypotheses used the existing canonical
LightGBM configuration and frozen three-seed equal ensemble. Hyperparameter
optimization, best-seed selection, new Label creation and Blind-driven Feature
selection were zero.

Two model hypotheses passed the 2019—2021 Discovery gate:

1. `trend_path_subset`,
   `rbmb1_8556b3a5a3202a80c38b02f9939b08475354d3b542a9fb277b2de419afacf2db`.
2. `trading_confirmation_subset`,
   `rbmb1_1cc00926e341d68ddc577b76b0927b88795ff445037a7ecef7453e60681e8e65`.

The versioned QuantMind runtime already contained OpenMP at its immutable
native path. Exporting that existing path enabled LightGBM 4.6.0; no dependency
was installed and no environment or lockfile changed.

## 11. Autonomous Round Summary

- Total rounds: 24.
- Agent rounds/calls: 18/18.
- Model hypothesis rounds: 6.
- Minimum pre-stop coverage: satisfied.
- Distinct DSL families: at least 8.
- Both lanes completed: true.
- Manual intervention count: 0.
- Manual round-planning count: 0.
- Automatic Batch 002 created: false.

## 12. Proposal Summary

- Agent proposals: 42.
- Proposals per call: 2.3333333333333335.
- Duplicate structures: 0.
- Rejected structures: 18.
- All rejected proposals remain included in Search Exposure.

## 13. Admission Summary

- Total admissions: 24.
- Admission rate: 0.5714285714285714.
- DSL admissions: 18.
- Fixed model hypotheses: 6.
- Local rescue trials: 4.
- Discovery-to-Blind rate: 0.08333333333333333.
- Blind submissions: 2.

## 14. Discovery Evaluation

Discovery used only `2019-01-02..2021-12-31`. It enforced coverage, finite/PIT,
positive mean RankIC, turnover, concentration and maximum absolute existing
correlation. Passing Discovery was treated only as Blind admission, never proof
of Alpha.

## 15. Candidate Batch Lock

- Lock:
  `rbcbl1_616dfc39faca7136ccc8a04f20f02b83792baa85e286b6f0be6a794ce7aba705`.
- Object count: 2.
- Agent closed: true.
- Planner closed: true.
- Blind reads before publication: 0.
- Label: `technical_return_1d`.
- Seeds: `20260701`, `20260702`, `20260703`.
- Formula/model configuration, Bundle membership, primary statistic, strategy
  and Discovery rank are immutable.

## 16. Blind Window Results

Both locked candidates ran all 18 complete windows. No candidate stopped early.

`trend_path_subset`:

- primary positive-window rate: 55.56%;
- primary median: 0.0022600209631735303;
- worst-20% primary mean: -0.01514006686015582;
- CSI300 excess positive-window rate: 55.56%;
- CSI300 excess median: 0.01503024598960051;
- turnover median: 3.878765897558411;
- concentration median: 0.12659648215020358;
- one-sided t-statistic/p-value: 0.620565764772494 /
  0.27155805441781034;
- gate: failed.

`trading_confirmation_subset`:

- primary positive-window rate: 22.22%;
- primary median: -0.005809470690319829;
- worst-20% primary mean: -0.011345808573321922;
- CSI300 excess positive-window rate: 72.22%;
- CSI300 excess median: 0.018385062697007994;
- turnover median: 3.8925293075006593;
- concentration median: 0.11974327792190664;
- one-sided t-statistic/p-value: -1.8105884334928555 /
  0.9560425895769862;
- gate: failed.

## 17. Window Consistency

- Complete windows per candidate: 18/18.
- Candidate/window result Artifacts: 36.
- Early stopped candidates: 0.
- Configuration mutations: 0.
- Missing/non-finite metric handling: fail closed.
- Model training calls: 126, representing the frozen three-seed ensemble for
  six Discovery hypotheses and 36 Blind model windows.

## 18. Search Exposure

- Search Exposure:
  `rbse1_2d92206458b91ea5f0928d6d2b07c71d967de2a5bb6d1dd376f2110adf8b6030`.
- Blind Submission Ledger:
  `rbsl1_f00af94e3fb50c58e7208beca56366da45ae9bbd461b40a1c3c4a31f8052ff59`.
- Agent calls/proposals/admissions/rejections: `18/42/24/18`.
- Duplicate/local rescue/model hypotheses: `0/4/6`.
- Batch and cumulative historical Blind submissions: `2/2`.
- Ledger exposes submitted structure keys and consumed budget only; it contains
  no metrics or failure reasons.

## 19. Multiple-testing Control

- Multiple Testing:
  `rbmt1_74f1f2bbcfd879527d9a658fcef40198d58bd01ed6f469321dfd45588d58f42c`.
- Method: global Benjamini-Hochberg across both lanes.
- FDR: q=10%.
- Hypothesis count: 2.
- Adjusted q-values: 0.5431161088356207 and 0.9560425895769862.
- Passed hypotheses: 0.

## 20. Blind Failures

Both candidates failed the primary-metric consistency gate. The first also
missed the CSI300-excess positive-window rate. These failures appear only in
the final Report and are not reusable adaptive failure memory.

## 21. Blind Survivors

- Survivor count/writes: 0/0.
- Blind survival rate: 0.
- Gate relaxation: false.
- Budget increase: false.
- Retuning after Blind: false.

## 22. Registry

Registry writes: 0. No failed Blind candidate was registered, approved,
activated, promoted or labeled production-eligible.

## 23. New Fresh Locks

Fresh Lock writes: 0 because there was no Survivor. The no-backfill contract is
implemented but was not invoked.

## 24. Existing Fresh Cohort Isolation

Existing Candidate B/C, their Fresh Locks, Cohort
`mfcc1_faab1ee6f07fe1ce46bb13ab8403e104433c5781058d3e8c6720e6ffd7bde6dc`,
heartbeat, LaunchAgent and Runtime Deployment were unchanged. Batch 001 read no
real Fresh metric.

## 25. Research Efficiency

- Qlib calls: 64.
- Qlib calls per Blind candidate: 32.
- Qlib calls per Survivor: null.
- Compared with annual Holdout, each locked object covers 18 independent
  60-session market windows and exposes positive-window rate, median and
  worst-window-tail behavior. The cost is repeated pre-window model training
  and 18 formal Qlib runs per object.

## 26. Batch Final Status

`completed_no_blind_survivor`

`historical_pseudo_fresh = true`, `real_fresh_validation = false`,
`mainline_blocked = false`, `automatic_batch_002_created = false`.

## 27. Artifact Store

- Terminal Report:
  `rbrr1_8c19f12bca2e6f78256054b000b9af19e254ec9032389af609f4fa057d2a4121`.
- New Artifacts/Blobs reported by the final uninterrupted completion run:
  73/170.
- Integrity: healthy.
- Missing: 0.
- Unreferenced: 0.

## 28. Cold Recovery

`validate_batch` recovered the Window Set, Candidate Lock, both aggregate
Candidate Results, Multiple Testing, Search Exposure, Submission Ledger and
terminal Report: 8 terminal Artifacts, zero evidence gaps, healthy Store.

## 29. Resume Test

The execution was intentionally interrupted twice while diagnosing a
date-key compatibility defect and once blocked before model training by a
missing dynamic-library search path. Immutable round checkpoints prevented
repetition of every completed Agent call. The terminal `run-next` returned
`exact_existing=true` with all runtime counts zero.

## 30. Exact Replay

Exact replay returned zero Agent, model training, Qlib, Tushare, network,
candidate, Survivor, Fresh Lock, Registry, Promotion, new Artifact and new Blob
counts. Evidence gaps were zero and Store integrity remained healthy.

## 31. Files Added

- Rolling Blind engine package (`__init__.py`, `models.py`, `engine.py`).
- `test_rolling_blind_alpha_discovery.py`.
- `ROLLING_BLIND_ALPHA_DISCOVERY_V1.md`.
- This Run report and Manifest.

## 32. Files Modified

- Artifact kind, prefix and validator registries.
- Autonomous Research Supervisor exports/orchestrator.
- Supervisor CLI.
- Context Bootstrap test/tool current-task assertion.
- Project Memory Current State, Handoff, Component Catalog and Roadmap in
  human- and machine-readable forms.

No runtime deployment, LaunchAgent, Fresh Cohort, dependency, lockfile, market
data, model artifact or production configuration changed.

## 33. Tests Executed

- Rolling Blind targeted suite: 27 passed.
- Related Supervisor, Agent, Feature, DSL, LightGBM, Artifact Store and Context
  regression: final result recorded in the Manifest.
- Formal Batch 001: completed.
- Cold validation, terminal resume and exact replay: passed.
- Context Bootstrap, JSON parse, `py_compile`, Git inventory,
  `git diff --check` and secret scan: final result recorded in the Manifest.

The initial narrow pytest run had 27 passing tests but exited nonzero only
because repository-wide coverage was 4.22% below a 5% global threshold. Formal
narrow verification uses `-o addopts=''`/`--no-cov`; no test was skipped to
hide behavior.

## 34. Expected vs Actual

- Expected at least 18 rounds/calls before stopping; actual 24 rounds and 18
  calls.
- Expected both lanes; both completed.
- Expected up to 20 Blind submissions; only two passed unchanged Discovery.
- Expected all frozen candidates to run all windows; actual 36/36.
- Expected zero Survivor to be legal; actual zero and no gate relaxation.
- Expected requested Blind upper bound 2026-07-23; authoritative calendar
  availability stopped at 2026-06-24, producing 18 full windows plus one
  excluded tail session.

## 35. Implementation Run

- Run ID: `QM2-R3-001-20260725T112004Z-addae39`.
- Base commit: `addae3914c45089a5cb33e7a5a1e7c7151af05c6`.
- Manifest: v2.
- Pre-commit status: `completed_uncommitted`.
- Suggested commit: `feat(qm2): add rolling blind alpha discovery`.
- Commit policy: one commit, no amend/reset/rebase/push.

## 36. Project Memory Updates

Current State, Handoff, Component Catalog and Roadmap now identify Batch 001,
its immutable IDs, 18-window calendar limitation, zero-Survivor outcome,
isolation constraints, replay result and prohibition on automatic Batch 002.

## 37. Known Limitations

- The canonical calendar available during Batch 001 stops at 2026-06-24, not
  the requested 2026-07-23.
- The reused Qlib wrapper emits optional PostgreSQL/COS resolution warnings
  before successful local formal Qlib execution.
- Formal LightGBM needs the already-versioned QuantMind native OpenMP directory
  on the dynamic-library search path.
- The official Factor Lab source remains volatile under `/tmp` and was absent
  at final verification; this task never modified it.
- Batch 001 produced no Survivor and therefore no new real Fresh Lock.

## 38. Final Research Conclusion

The rolling protocol rejected both Discovery-selected LightGBM hypotheses.
The apparent 2019—2021 signal did not generalize consistently across the 18
non-overlapping 60-session windows. The correct outcome is zero Survivor,
not parameter rescue, gate relaxation or targeted formula feedback.

## 39. Git State After

Before commit the workspace contains only task-scoped source, test,
architecture, Project Memory and Implementation Run changes. No dependency or
lockfile changed. Final post-commit Planner and clean-worktree evidence are
recorded after the single containing commit.
