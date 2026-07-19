# Locked-factor Signal Missingness Audit v1

This diagnostic contract traces an already locked Factor signal through source
rows, required Features, every DSL node, immutable Factor Values, orientation,
cross-sectional normalization, combination, the Dataset-derived Qlib consumer
view and the formal Qlib precheck. It cannot call an Agent, optimize, change a
Factor, fill data, relax a gate or modify an earlier experiment.

The denominator contract distinguishes the Qlib precheck's observed signal
rows from the complete locked-universe grid. Missingness is classified as row
absence, source Feature missingness, intended DSL warmup, DSL-introduced NaN,
normalization/combination propagation or Qlib alignment loss. Daily, symbol,
month, rebalance/non-rebalance, Feature and AST-node evidence is immutable.

For `QM2-P0-011BF`, the formal precheck is 3,822 / 10,867 = 35.1707%; the
complete 100 x 111 grid is 4,055 / 11,100 = 36.5315%. The missing cells are 222
complete-universe absences, 11 local row absences and 3,822 missing
`style_idio_vol_20` source values. Locked Factor recomputation is exact and all
DSL, normalization, combination and Qlib alignment stages add zero NaNs.

Because the authoritative Feature bytes are genuinely missing and their
generation provenance is insufficient for a semantics-preserving correction,
no repair or Qlib rerun is permitted. The follow-up remains `blocked`; this is
a data-source availability conclusion, not a 2026H1 performance conclusion.
