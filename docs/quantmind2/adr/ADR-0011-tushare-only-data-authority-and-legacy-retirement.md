# ADR-0011: Tushare-only Data Authority and Legacy Retirement

- ADR ID: ADR-0011
- Status: accepted
- Date: 2026-07-20
- Supersedes: ADR-0003
- Superseded By: none
- Related Components: `quantmind2.data_foundation`, `quantmind.feature_snapshots`, `quantmind.qlib_backtest`, `quantmind2.research_artifact_store`
- Related Implementation Runs: `QM2-P0-014`

## Context

ADR-0003 selected TongDaXin as the intended A-share entry while explicitly
leaving its concrete provider unverified. The available legacy annual feature
Parquet exhibited annual rolling-window cold starts and separated PostgreSQL,
Parquet, and Qlib facts. The user has now approved Tushare Pro as the only
market-data authority and approved retirement and physical purge of the legacy
data graph after a verified replacement exists.

## Decision

The authoritative chain is:

```text
Tushare Pro (`tushare-pro-v1`)
→ immutable necessary-column raw artifacts for a PIT-selected fixed 500
→ deterministic normalization (`adjusted_price = raw_price * adj_factor`)
→ continuous cross-year Feature and T+1 Label datasets
→ immutable fixed-100 experiment view
→ Qlib consumer view
```

The fixed 500 is selected only from the first 20 open sessions of 2019 using
mean `circ_mv`, at least 15 observations, listing/delisting eligibility, and a
stable code tie-break. The fixed 100 is the first 100 parent ranks. Full
2018-09-01..2026-06-23 history is fetched only for the locked 500. Dataset and
Artifact Store identities remain authoritative; Qlib remains a consumer.

Provider credentials are accepted only from the process environment variable
`TUSHARE_TOKEN` and may not be logged, persisted, hashed, or passed by CLI.
The legacy provider `quantmind-production-feature-snapshots-v1` is
`retired_and_purged`; formal runtime fallback to it is forbidden. Research
metrics derived from it are invalidated, not transferred to the new empty
Registry genesis, while non-metric structural memory may be retained in a
sanitized artifact.

## Consequences

- ADR-0003 remains immutable historical evidence but no longer governs the
  active provider choice.
- The fixed 500/100 identities, raw data, normalized bars, Feature/Label
  contracts, Qlib view, Registry genesis, Memory sanitization, purge plan and
  authority records are content-addressed artifacts.
- Old source Parquet/Qlib/cache data and all 97 legacy research descriptors
  were deleted only after capability, quality, Qlib, Store recovery, exact
  replay and credential gates passed.
- Existing LightGBM and Qlib implementations remain unchanged. LightGBM input
  integration with the new Feature Dataset remains a separate task.
- Incremental Tushare updates after 2026-06-23 are not provided by this ADR.

## Alternatives Considered

Keeping TongDaXin primary, retaining dual authorities, using Qlib binary as
authority, selecting today's survivors, and copying old validation metrics into
the new Registry were rejected because they violate the approved single-source,
PIT, immutable-lineage, and clean-revalidation boundaries.

## Non-goals

This ADR does not redesign Tushare, LightGBM, Qlib, Factor DSL, Agent research,
portfolio logic, live trading, database APIs, or post-cutover incremental
collection.
