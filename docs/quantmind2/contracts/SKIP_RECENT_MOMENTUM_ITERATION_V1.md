# Replayable Skip-Recent Momentum Deep Dive v1

Task `QM2-R1-003` uses only Catalog
`mfc1_51dc0901c6d01ce07eec6228f881d49bb57ade13c8b6a7adb85bf14ae633b47c`
and Dataset
`mfd1_9bb7172510693b69deaedf0d211bce79dcad8a0178a34d70a4a01f654c08db2c`.
The source `QM2-R1-002` Experiment remains unchanged and its unrecoverable
candidate is comparison evidence only.

Six fixed rounds cover classic skip-recent, multi-horizon consensus, path
quality, relative/residual, risk-adjusted and failure-driven hybrid structures.
The bounded campaign permits at most 12 Agent calls, 18 admitted Templates and
144 unique Trials. Agent creates structure; mechanical Optimization searches
only factor windows and internal weights. Strategy parameters are frozen at
Qlib TopK 20, n_drop 5, five-session rebalance, open-price execution, one-day
signal lag and CSI300 benchmark.

Four expanding research folds select and persist parameters before each next
year evaluation. The Fold-4 research-period parameters are frozen for the
read-only 2025 and 2026H1 reports. Neither later period, Fixed-100-relative
metrics nor regime diagnostics participates in selection.

Canonical Experiment:
`srme1_072b0d1a70762482c5fac657568a80b2b01de92e08442b29d1c60a6704d1ab3c`.
It explored all six subfamilies through nine completed real
`openai_codex_cli/gpt-5.6-terra` responses, 15 candidates, 50 unique parameter
Trials and 178 formal Qlib calls. Two candidates passed the unchanged
standalone gate and are locked research-only:

- `srmcl1_56201db3ca8a2b4ccd88be58abfddc127d4c077e16407c400a3f4312edd9f95b`:
  `cs_zscore(momentum_60_10 - rolling_mean(momentum_60_10, window=40))`.
- `srmcl1_4e0abd499038faf0ecc9f178b89712d7055790e91d3e391f41a0e338352c80b4`:
  `momentum_60_10 - 0.75 * distance_to_high_60`.

Both have four completed Qlib Fold results and satisfy independent eligibility.
The two-family ensemble was therefore allowed. In contaminated retrospective
reports, both candidates and their ensemble underperform CSI300 in 2025 and
2026H1; none is fresh validation or promotion evidence. Exact replay cold
restores 368 lineage artifacts with all external call counts zero and Store
integrity healthy, Missing 0, Unreferenced 0.
