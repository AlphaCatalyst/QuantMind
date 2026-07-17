# Fresh Validation Accrual v1

The annual Legacy Parquet is mutable input, not immutable Fresh Validation
authority. Every inspection hashes its exact bytes and creates a new immutable
Watermark on source drift. The Watermark records observed maximum date, first
strictly fresh date, last label-complete observation, eligible count and state.

After fresh rows arrive, an accrual snapshot retains only post-start source
terminals required for the locked Templates and production label, regenerated
locked factor values, complete labels, eligible dates, and quality evidence.
Its content-addressed directory is staging-published atomically and validated by
closed inventory and file hashes. Existing identical content replays exactly;
corruption or conflicting content fails.

Maturity requires the earliest 60 common label-complete dates with 100 finite
observations. An incomplete last observation is never counted. Before maturity,
evaluation raises `FRESH_VALIDATION_NOT_MATURE` and publishes no result. The
current source hash is
`c2060c913dfdc7cc6a0723d19de53cc957c928a6ed490c163b1dceefde9269c1`,
ends 2026-06-24, and yields zero post-lock eligible dates.
