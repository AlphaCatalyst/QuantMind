# Parameter Optimization Overfit Ablation v1

Status: implemented by `QM2-R1-005`
Evidence class: `retrospective_parameter_optimization_ablation`

## Purpose and boundary

This contract diagnoses whether historical factor and strategy parameter selection generalizes. It does not create factors, mutate the two `QM2-R1-003` candidates, promote research, or change the behavior of the existing factor or strategy optimizers. The 2025 and 2026H1 periods have already been observed and are report-only evidence. Results therefore have `predictive_claim=false`, `usable_for_promotion=false`, and `eligible_for_production=false`.

The immutable inputs are:

- experiment `srme1_072b0d1a70762482c5fac657568a80b2b01de92e08442b29d1c60a6704d1ab3c`;
- candidate locks `srmcl1_56201db3ca8a2b4ccd88be58abfddc127d4c077e16407c400a3f4312edd9f95b` and `srmcl1_4e0abd499038faf0ecc9f178b89712d7055790e91d3e391f41a0e338352c80b4`;
- equal-weight ensemble `srmen1_7200c57baf718a80992e812e28de0241a479f443e5e64bb2581830fecbe25ab2`;
- momentum feature dataset `mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c`;
- provider `tushare-pro-v1`, Fixed-100 universe, and CSI300 benchmark.

The `QM2-R1-004` semantic audit is presentation-only context. Candidate A is displayed as a medium-horizon momentum baseline deviation; Candidate B is displayed as skip-recent momentum plus pullback reward. No DSL, AST, parameter, orientation, or historical ID is changed.

## Recovered parameter authority

Default values, parameter schema, full search space, fold-selected values, final reporting values, orientation, and source trial IDs must be recovered from the immutable Proposal, Template Definition, Candidate Lock, and Trial Detail artifacts. A missing default or schema blocks execution with `PARAMETER_BASELINE_UNRESOLVED`; the runtime must not invent values.

Factor modes are:

- F0: Agent default only;
- F1: the default and each legal immediate predecessor or successor, changing one parameter at a time, at most seven trials;
- F2: the original frozen full search space, without expansion.

The recovered candidates each have one parameter and three explicit values. Consequently F1 and F2 contain the same parameter points for this study. They remain separately identified in artifacts, but this study cannot attribute a difference to a larger F2 factor search space.

Strategy modes are:

- S0: `(topk=20, n_drop=5, rebalance=5)`;
- S1: the seven frozen one-hop configurations around S0;
- S2: the 24 legal configurations from `topk=[10,20,30]`, `n_drop=[0,5,10]`, and `rebalance=[1,5,10]`, excluding `n_drop >= topk`.

Combined intensity is O0=F0S0, O1=F1S1, and O2=F2S2. Factor-only studies keep S0 fixed. Strategy-only studies keep F0 fixed.

## Time and selection isolation

The four folds use research/evaluation intervals 2019–2020/2021, 2019–2021/2022, 2019–2022/2023, and 2019–2023/2024. Selection never reads the evaluation year, 2025, or 2026H1. Each selected Trial is assigned a content-derived `poafl1_` Fold Lock identity before evaluation metrics are requested; aggregate artifacts preserve these locks. The immutable ordering is:

1. positive RankIC year count;
2. median RankIC;
3. worst RankIC;
4. positive CSI300 excess year count;
5. median CSI300 excess;
6. worst CSI300 excess;
7. absolute maximum drawdown;
8. turnover;
9. transaction cost;
10. Trial ID.

Equivalent parameter/signal/strategy configurations receive a mode-independent
`poac1_` configuration identity. It is used for the final tie-break so that F1
and F2 cannot select different parameters merely because their mode labels
produce different record IDs.

The fixed formal execution contract is equal weight, signal lag one session, open execution, CSI300 benchmark, and `CnExchange` costs. Formal returns and risk are accepted only from the existing Qlib chain.

## Diagnostics

Each fold records RankIC, RankICIR, RankIC positive rate, net return, CSI300 return and net excess, Sharpe, maximum drawdown, turnover, transaction cost, best-ten-day contribution, and return excluding the best ten days.

Optimization gain is optimized minus the matching unoptimized mode. Generalization gap is 2019–2024 research gain minus the mean of the 2025 and 2026H1 report gains. Trial stability records Spearman and Kendall correlations and the selected trial's later percentile. Winner's curse compares the selected trial with the trial median in research, evaluation, 2025, and 2026H1.

Fold consistency records exact-match rate, adjacent-match rate, dispersion, and instability. A direct neighbor belongs to a parameter plateau when RankIC is no more than 0.003 below the selected value and CSI300 excess is no more than 0.10 below it. Ratios of at least 0.70, at least 0.50, and below 0.50 are `broad_plateau`, `acceptable_plateau`, and `sharp_peak` respectively.

Search intensity records trial count, eligible count, best and median research metric, and their spread. Cost analysis records turnover change, transaction-cost change, gross and net improvement, and whether positive gross improvement was consumed by costs.

## Classification and decision

`likely_robust` requires positive research excess gain, non-negative gain in both report periods, plateau ratio at least 0.50, and fold adjacent-match rate at least 0.50. `likely_overfit` applies when positive research gain has negative average report gain; when the selected trial is below the median in both report periods; or when a sharp peak accompanies a CSI300-excess generalization gap above 0.05. Other evidence is `inconclusive`.

Factor, strategy, and combined layers independently choose one diagnostic recommendation from `keep_full_optimization`, `replace_full_with_local_optimization`, `default_first_optimize_only_on_failure`, and `suspend_parameter_optimization`. Recommendations are not applied automatically.

## Artifacts and replay

The Store kinds are `parameter_optimization_ablation_spec`, `factor_optimization_ablation`, `strategy_optimization_ablation`, `combined_optimization_ablation`, `optimization_trial_rank_stability`, and `optimization_overfit_assessment`. Content-derived IDs, file hashes, lineage, formal domain validation, cold recovery, inventory, and integrity checks are mandatory.

Exact replay restores the complete six-artifact bundle and performs zero Factor Optimization, Strategy Optimization, Qlib, Agent, network, or promotion calls; it creates zero artifacts and blobs. Candidate status remains `research_registered`.

The command entry point is `tools/quantmind2/run_parameter_optimization_ablation.py`. Its execute commands publish one atomic immutable study; after the first publication, any repeated execute command resolves to exact Store-backed replay.
