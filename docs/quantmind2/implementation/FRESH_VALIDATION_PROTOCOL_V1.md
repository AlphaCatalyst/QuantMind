# Fresh Validation Protocol v1

Fresh Validation is a strict forward, one-time control protocol. The candidate
cohort is locked before eligible market observations exist. Historical data
that was readable at lock time is forbidden even when an Agent did not see it.

The authoritative Candidate Lock binds exactly three admitted Factor Instance
IDs, their canonical Template payload and ID, parameter values, Study, Trial,
Development result, family, fixed pre-2025 orientation, and admission rank.
The first eligible observation is the first observed market trade date strictly
after the greater of the lock market date and global exposure cutoff.

The protocol selects the earliest 60 label-complete dates with at least 100
common finite observations across all candidates. It may not skip dates, extend
the window, backfill, reselect candidates or Trials, change parameters, or flip
orientation. Label maturity follows the production H=1 contract: the next
trading row's adjusted open and close must exist; natural-day age is irrelevant.

Metrics are daily Pearson IC, average-rank Pearson RankIC, non-annualized ICIR,
positive rates, observation and coverage statistics. The frozen pass gates are
60 valid dates, median daily observations >=100, factor finite coverage >=0.60,
oriented mean RankIC >=0.01, RankICIR >=0.10, and positive rate >=0.52. A pass
only means eligibility for a later Frozen protocol; it is not promotion.

One protocol can publish one immutable result. Replay returns the existing
result and never reads a 61st date. The result records every locked candidate,
including failures, and a passing-only deterministic future candidate order.
Registry main status remains `research_registered`; only bounded pending or
result evidence may be added. Agent memory receives outcome categories only.

Current authority is under `docs/quantmind2/research/fresh_validation/`. The
lock market date is 2026-07-17. The inspected source ends 2026-06-24, so the
current state is `awaiting_first_fresh_date`, eligible count is zero, and no
real Fresh Validation result exists.
