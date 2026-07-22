# Momentum Tail-Alpha Diagnostic v1

## Authority and purpose

This contract governs `QM2-R1-009`, a retrospective diagnostic of the
immutable R1-008 Signal D. It determines whether the signal behaves as a
broad monotonic factor, a top-tail selection overlay, a defensive relative
factor, a regime-specific factor, or has no reliable alpha. It is not Fresh
Validation, Frozen Test, Candidate selection, Strategy Optimization, Registry
promotion, or production evidence.

The only source signal is
`residual_absolute_momentum_consensus`, artifact
`lfmsa1_a4a99da30ef0dc99a03270bc5688f3edbe66bf944f899795d11aacf83a8e2262`:

```text
0.5 * cs_zscore(momentum_120_20)
+ 0.5 * cs_zscore(residual_momentum_60)
```

Weights are 0.5/0.5, orientation is 1, signal lag is one session, and none of
these values may be changed by this diagnostic.

## Metric semantics

- Formal annual RankIC is the daily cross-sectional Spearman correlation
  between the immutable signal value and the R1-008 `model_label`.
- Quantile, tail, extreme-rank, decay and gross Top-N returns use adjusted
  close forward returns at the declared T+1/T+5/T+10 horizons; decay extends
  to T+20/T+40. These diagnostics never replace the formal RankIC gate.
- Q1 through Q10 are recomputed independently on each observable trading day.
- Top-tail spread is Q10 less the mean of Q6--Q9; hit rate is the share of
  dates on which Q10 exceeds the observable-universe mean.
- Top 5/10/20/30 use fixed ten-session holding, equal weight and no n_drop.
  They are gross-only because formal trading costs are unavailable for this
  diagnostic path, and no Top-N value may be selected from the results.
- 2021--2024 are the research interval. 2025 and 2026H1 are retrospective,
  report-only, not used for selection, and not Fresh Validation.

## Exposure and stability boundaries

Beta 20/60, idiosyncratic volatility 20/60, volatility 20/60, amount ratio 20
and log circulating market value are computed deterministically from the
governed normalized market data where the frozen feature matrix does not
carry them. Industry attribution is omitted because there is no historical
PIT industry contract. Breadth uses the existing PIT-safe regime builder.
Score autocorrelation is measured at 1/5/10/20 sessions; rank transition and
Top-N membership overlap use the fixed ten-session diagnostic interval.
Component-level formal-label RankIC, adjusted-close T+1 RankIC and top-tail
excess are persisted separately for `momentum_120_20` and
`residual_momentum_60`; component failure is not inferred from their weights
or correlation with the composite.

## Classification and governance

The primary classification is exactly one of:

```text
broad_monotonic_factor
tail_selection_overlay
defensive_relative_factor
regime_specific_factor
no_reliable_alpha
```

The research decision is exactly one of
`build_momentum_selection_overlay`,
`retain_for_regime_specific_research`, or `stop_signal_d_research`. The
decision is advisory and cannot execute itself. Agent, Factor Optimization,
Strategy Optimization, Combined Optimization, Qlib strategy, Tushare,
network, Candidate Lock, Registry and Promotion counts must all be zero.

## Immutable artifacts and replay

The Store persists the diagnostic, quantile return report, rank transition
report, style exposure and classification as five distinct Artifact kinds.
Every Artifact is content-addressed and references the immutable R1-008 study
and Signal D lineage. Computation revision 3 separates formal-label RankIC
from adjusted-close forward-return RankIC and adds direct component
diagnostics; revisions 1 and 2 remain immutable historical evidence. Cold
recovery and exact replay must validate all five revision-3 artifacts with no
new Artifact, Blob, research or external call.

## Current result

Signal D is `regime_specific_factor`, with the advisory decision
`retain_for_regime_specific_research`. Narrow/weak breadth has positive
RankIC, Q10-Q1 and Top20 CSI300 excess, while broad and neutral breadth do not
jointly retain those properties. This result creates no Candidate Lock,
Registry entry, Promotion evidence or successor task.
