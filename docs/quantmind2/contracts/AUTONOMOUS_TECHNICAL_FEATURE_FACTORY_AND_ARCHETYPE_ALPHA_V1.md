# Autonomous Technical Feature Factory and Archetype-aware Alpha v1

## Status and evidence class

This contract is implemented by `QM2-R2-004`. Its evidence is retrospective
autonomous research. It is not Fresh Validation, Frozen Test, predictive,
Promotion, or production evidence.

The only market-data authority is `tushare-pro-v1`. The Factory and Program
read existing Store artifacts and make zero Tushare or market-network calls.

## Technical Terminal Feature Factory

`AutonomousTechnicalFeatureFactorySpecV1` is immutable and precedes every
Feature Agent call. Formal Factory `technical_feature_factory_001` is bounded
to eight calls, 24 Proposals, 16 Admissions/materializations and one repair
attempt per call.

The Feature Agent receives primitives, authorized operators, existing names
and structural fingerprints, unlabeled failure summaries and family coverage.
It never receives labels, forward returns, RankIC, returns, backtests,
Candidate performance, or 2021–2026 evidence.

`TechnicalTerminalFeatureGrammarV1` authorizes only operators with existing
formal executable PIT semantics:

```text
add subtract multiply safe_divide negate abs clip
lag delta rolling_mean rolling_std rolling_min rolling_max
```

The contract names `rolling_sum`, `rolling_corr` and `log1p`, but the current
formal DSL has no authorized implementation for them. Proposals using them
fail `FEATURE_OPERATOR_NOT_AUTHORIZED`; the Factory does not create operators.
Windows are exactly 5, 10, 20, 40, 60 and 120. A Feature has at most four
primitives, two distinct windows, AST depth six and eight operators.

Admission uses only 2019–2020 and enforces parse/AST/PIT, finite coverage,
daily membership, infinity/duplicate/PIT counts, cross-sectional dispersion,
unique values, rank persistence, structural novelty and signal novelty.
Passing objects are `research_terminal_feature`, never approved, active or
production.

`TechnicalFeatureCatalogV2` contains existing formal Terminal Features and
new research Terminal Features with source, state, AST, fingerprints and
materialization references. It is frozen before the first Alpha Agent call.

## Alpha Archetypes

`AlphaArchetypeContractV1` allows one pre-registered primary Archetype:

- `monotonic_rank_factor`: primary observation is daily official-label
  RankIC; locked test uses HAC lag 10.
- `top_tail_selection_factor`: primary observation is the non-overlapping,
  fixed-10-session Top20 equal-weight future gross return minus the observable
  universe; locked test uses HAC lag 1.

Every Proposal declares `primary_archetype`, `primary_hypothesis`,
`primary_test_statistic` and expected holding horizon before any numerical
evaluation. Missing declarations fail `ALPHA_ARCHETYPE_MISSING`; a change
after evaluation fails `POST_HOC_ALPHA_ARCHETYPE_SWITCH`.

## Program 002

`technical_alpha_program_002` freezes three Lanes, both Archetypes, budgets,
fixed strategy and evidence partitions before Agent execution. Adaptive
research is 2019–2020. Locked Validation is 2021–2024. 2025 and 2026H1 are
survivor-only contaminated reports.

Adaptive execution is:

```text
static admission
→ default parameters
→ optional one-hop local rescue
→ development lock
→ Archetype-specific annual gate
```

Full Factor Search, Strategy Optimization and Combined Optimization are
forbidden. The strategy is TopK20, n_drop5, 10-session rebalance, equal
weight, signal lag one, open execution and CSI300 benchmark.

The Program cannot stop for lack of improvement before 12 rounds/calls, seven
factor families, three completed Lanes, 18 Admissions and both Archetypes.
Budget exhaustion remains a legal terminal path when those admission
conditions cannot be reached.

After all Agent, Planner and Memory inputs close, the immutable Union Lock
freezes formula, parameters, orientation, Archetype and Adaptive order with
zero Validation reads. Validation is pass/fail and never reranks. Exactly one
primary p-value per Union object enters global Benjamini–Hochberg FDR at 10%.
Only an Archetype-gate and FDR survivor can become `research_registered`.

## Recovery and replay

Agent responses, adaptive evaluations, Union Lock, each Validation,
multiple-testing control, failure records, Candidate/Fresh Locks and terminal
Report are Store artifacts. Resume reuses persisted responses and completed
evaluations. Terminal replay must produce zero Agent, optimization, Qlib,
Tushare/network, Feature, Registry, Fresh-Lock, Promotion, new Artifact and
new Blob counts.

## Formal QM2-R2-004 evidence

- Factory Spec:
  `atffs1_59f2c98666d95c2e5d2414b0837863908df38cbcd12bf86333465ea4cc3cf288`
- Catalog v2:
  `tfc2_229f1939bdd3023e0410d3def332f1a9fdbd8cb4193cc71e7e6a8660138cf5e6`
- Archetype Contract:
  `aac1_853b0df7f8146c0024b3b95f94ea20ed87a2a35c096d8d64813b5d649fe8e961`
- Final Program Spec:
  `aap1_30e59bce48153a721dd29b459548dafc98271f6eef4236c07a8569b70acd0100`
- Union Lock:
  `aausl1_47e18224e6c1d15d7cb8f66aa689e785e08eab24c6cb96c81ad787751d27d239`
- Multiple-testing control:
  `amtc1_fae10b7f2dafe0d81552a68e3d34226f12050cb6492a7b0045d7f7011d2dd7d1`
- Program Report:
  `aapr1_e344e138cb76bd1c0307920426b879c0b0a1019b4e3083cc3f373a739df4f6e3`

The Factory admitted two of ten proposed Features. The final Program ran 18
Agent calls, 36 Proposals, 19 Admissions, 11 local rescue Trials, 58 Adaptive
Qlib calls, nine locked Validation objects and both Archetypes. All nine
failed the unchanged Archetype gate and/or global FDR. The terminal state is
`completed_no_validation_survivor`; Registry, Fresh Lock, contaminated report
and Promotion writes are zero.
