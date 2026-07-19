# QM2-P0-014 Implementation Report

## 1. Task Summary

Completed the Tushare-only fixed-500 market-data authority cutover, fixed-100
experiment view, immutable Artifact Store publication, clean research genesis,
verified legacy purge, and Project Memory transition.

## 2. Goal

Make `tushare-pro-v1` the only formal market-data provider; store full history
only for a PIT-selected immutable 500, run experiments on its immutable top
100, remove the legacy annual-boundary Feature defect, and delete old data only
after the replacement passes all recovery, Qlib, quality and secret gates.

## 3. Scope

- Environment-only Tushare client with schema checks, bounded retry, global
  request-start rate limiting, bounded concurrency and resumable checkpoints.
- Immutable 500/100 locks, raw necessary-column datasets, normalization,
  continuous four-Feature contract, T+1 Label contract and fixed-100 Qlib view.
- Artifact Store kinds, formal validator, publication, recovery and exact replay.
- Empty Tushare Registry genesis and sanitized Research Memory.
- Immutable legacy purge plan, bounded deletion, shared-blob safety, final
  authority and inventory.
- ADR-0011, data contracts, Project Memory, CLI and focused tests.

## 4. Explicit Non-goals

- No Agent factor experiment rerun, LightGBM redesign or model training.
- No Factor DSL, Optimization, Validation or portfolio redesign.
- No live trading, API, database migration, UI, distributed Store or cloud.
- No post-2026-06-23 incremental collection.
- No inheritance of old IC, RankIC, backtest, Frozen, Development or promotion
  conclusions.

## 5. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `65389084b36abd1ee0b5b9f3577b44a2dd6ff3cb`.
- Worktree: clean; unrelated dirty files: none.
- Factor Lab was not copied, formatted or modified; its formal source received
  only a final read-only content-digest check.
- Artifact Store baseline: 97 artifacts / 372 blobs, healthy, zero missing and
  zero unreferenced.
- The credential was present only in a no-history process environment. It was
  never passed by CLI or printed.

## 6. Provider Capability and Selection

Real Tushare calls passed schema and permission probes for `stock_basic`,
`trade_cal`, `daily`, `adj_factor`, `daily_basic` and `index_daily`.

The first 20 open sessions were 2019-01-02 through 2019-01-29. Selection used
`circ_mv`, at least 15 valid observations, listing/delisting eligibility,
descending 20-session mean and ascending `ts_code` tie-break. The resulting
locks are:

- 500: `tu500_fb547c7935c91409b8e7f901bc891257bbb77c911a15a99773eccadf32624e8c`.
- 100: `tu100_078e6609ef84c58e4c9db53fe8ee194a4b8b7b31d4990a61fbddb9022c02c526`.

The 100 is exactly parent ranks 1..100. No later performance, completeness,
delisting, suspension or survival outcome replaced a stock.

## 7. Historical Data and Contracts

Only the locked 500 received full 2018-09-01..2026-06-23 queries:

- daily: 926,653 rows;
- adj factor: 931,312 rows;
- daily basic: 926,653 rows;
- SSE calendar: 2,854 rows, including the 2026-06-24 boundary session;
- CSI300 benchmark: 1,889 rows.

Normalized bars `tnb_311f8c6f7efe127f0891831502aa41e779c67f24d45a2b772ba80c613a9c73ec`
contain 926,653 unique symbol/date rows, 500 symbols, zero duplicate keys and
zero missing adjustment factors. Adjusted OHLC is raw OHLC multiplied by the
contemporaneous adjustment factor, without dynamic rebasing.

Feature Dataset `tfd_2cdcf05615a2669d144633952c81efc5e2e493294d8ac191698fd7260e86b97e`
contains `mom_ret_1d`, `liq_volume_ratio_5`, `style_beta_20` and
`style_idio_vol_20`. All were computed on one continuous cross-year series
before slicing, with no fill and population rolling formulas.

Label Dataset `tld_7f765006c745d2a8d4f3ce885d1322dd96441fd547800ebe997c5452b0ddc969`
contains raw T+1 close/open return, five-MAD/population-z-score model label,
sample weight, next-session tradability and conservative locked-limit state.
Raw-label NaN ratio is 0.05396%; zero-weight ratio and model-label NaN ratio
are 0.13338%.

## 8. Qlib Consumption and Data Quality

Qlib view `tqv_c489efe4d2084878433407d6dd3084b4f0c62ae2ca831b156998eba4d62941ff`
contains exactly the locked 100 equities plus CSI300 as a non-universe
benchmark and one empty 2026-06-24 calendar boundary sentinel.

Real `qlib.init` read calendar, prices and idio-vol fields. Existing
`QlibBacktestService` initialized directly against the view and loaded
`RedisRecordingStrategy`, `SimulatorExecutor` and `CnExchange`. No mock or
fallback was used. The 2026H1 `style_idio_vol_20` NaN ratio and the two locked
Factor combination signal NaN ratio are both 0%, below the unchanged 20% gate.

## 9. Store, Genesis and Memory

Thirteen core artifacts were Domain-validated and imported: both locks, five
raw/calendar/benchmark artifacts, normalized bars, Feature, Label, Qlib view,
Genesis Registry and sanitized Memory. Two independent cold materializations
verified all bytes and formal identities.

Genesis Registry `trg_0e23d0c7255a570a5f72f132d7db46d00842e55c794162ad6b04b15e7c61d309`
has entry/promotion/approved/active counts 0/0/0/0. Sanitized Memory
`tsm_d17b00a7a24ef1410baed9a6c49fb24cd52941aa3fd380e3a3894ae911ee9fc8`
marks historical metrics invalid and retains only structure fingerprints,
contract/safety failures, novelty and engineering experience.

## 10. Purge and Final Authority

Purge Plan `ldp_b9074f7f91dfb9c7d700ed83f6702e403c4aa335569975817a167287b5770fed`
bound three exact roots, all 97 legacy descriptors and 372 blobs not referenced
by retained descriptors. Early historical migrations omitted lineage on 22
fixed-universe/historical artifacts; the plan therefore also classified the
closed pre-cutover research-kind set and preserved every ID in the plan.

Only after capability, quality, Qlib, Store recovery and credential gates
passed, Result `ldr_cc9b249dcf1a973fa0a49ef7ab319ab2b380add6f7cfdf8786e462b29621fea0`
deleted 59,168 files, 97 descriptors and 372 exclusive blobs. It reclaimed
11,366,423,425 bytes. Old annual Feature Parquet, old Qlib data and old
QuantMind research caches are absent. A further 759,390,881 bytes of completed
Tushare checkpoint/staging/recovery duplicates were removed after Store
publication.

Final Authority `dar_38b6b09e06ed9091cc86789d4e44a50f143e51301bb2464b5f01a4ef47bd9052`
sets Tushare active, legacy provider `retired_and_purged`, legacy runtime reads
false and fallback forbidden. Inventory
`sai_2e7ce67296dd8f19af8239c3b7e4da1084cbd7c76c92afdcd2afc30129202040`
has 17 retained artifacts, 1,527 unique blobs, 127,650,825 logical bytes and
126,664,983 unique bytes. Integrity is healthy; missing, unreferenced and
legacy research Artifact counts are all zero. Eleven final authority artifacts
were cold-restored and exact-replayed after purge.

## 11. Files and Important Symbols

- `backend/services/engine/tushare_cutover/`: `TushareClient`,
  `TushareCutoverPipeline`, canonical identity and artifact validation.
- `backend/services/engine/artifact_store/`: new closed Artifact kinds and
  Tushare validator routing.
- `tools/quantmind2/tushare_data_cutover.py`: the eleven required commands;
  deliberately no `--token`.
- `backend/services/tests/test_tushare_cutover.py`: credential redaction, CLI,
  identity/hash, cross-year Feature and bounded-purge tests.
- `docs/quantmind2/data/`: Git governance record and data contracts.
- ADR-0011 and Project Memory document the authority transition.

## 12. API, Database, Configuration and Dependencies

No network API, database table/migration, runtime configuration, dependency
declaration or lockfile changed. No dependency was added to the repository or
system environment. Initial checks assembled short-lived offline `uv` tool
environments exclusively from an already populated cache; final data and test
runs used an existing cached Python environment. No package file or lockfile
was written.

## 13. Architecture, Security and Data Lineage Impact

ADR-0011 is a new accepted decision that explicitly supersedes, but does not
rewrite, accepted ADR-0003. Existing LightGBM and Qlib implementations are
retained. Dataset/Artifact identities remain authority; Qlib remains a view.

The credential client holds the token only in process memory, errors are
redacted, API response bodies are not logged, and CLI exposes no token option.
An exact-value scan covered repository files, all new working artifacts and
all Store files: 15,519 files, zero matches. A final repository/Store scan is
recorded in the Manifest tests.

Every derived artifact binds exact lock/raw/normalized/Feature/Label/calendar/
benchmark parents. Old data metrics are explicitly invalidated and cannot enter
the new Registry or Memory effectiveness labels.

## 14. Tests Executed and Results

- Tushare focused tests: 5 passed.
- Real endpoint probes and PIT selection: passed.
- 1,500 bounded full-history symbol requests with checkpoint/resume: passed.
- Cutover gate: passed; both 2026H1 missingness ratios 0%.
- Qlib direct provider and existing service initialization: passed.
- Store import, two pre-purge restores, final cold restore and exact replay:
  passed.
- Purge postconditions: healthy, Missing 0, Unreferenced 0, legacy count 0.
- Context, Artifact Store, market-data, historical/Qlib, JSON, compile, diff,
  secret and Planner results are finalized in the Manifest.

## 15. Known Limitations

- Incremental updates, revisions and publication after 2026-06-23 are not
  implemented.
- Artifact Store is single-host local filesystem; this task adds a bounded
  one-time purge, not general distributed garbage collection.
- Existing LightGBM is not yet bound to the Tushare Feature Dataset.
- Conservative price-limit labeling uses observed locked OHLC and a 9.5%
  threshold because `stk_limit` is outside the approved minimal endpoint set.
- Full formal backtest conclusions must be recomputed in QM2-P0-015; this task
  proves data and service consumption only.

## 16. Compatibility, Rollback and Remaining Work

Old code remains for historical readability, but formal legacy data reads are
forbidden and the local source/artifact data are physically absent. The data
purge is not reversible from this repository or Store. Recovery requires an
independent old backup or a fresh Tushare rebuild plus a new authority ADR;
silently restoring old data as authority is forbidden.

The next and only recommended task is
`QM2-P0-015 — Re-run Fixed-100 Agent Factor Experiment on Tushare Authority`.

## 17. Git / Workspace State and Artifact Index

- `result_commit` remains `null` in the immutable pre-commit Manifest; the
  containing commit is established by the post-commit Planner evidence.
- No amend and no push.
- Suggested commit: `feat(qm2): cut over market data to tushare`.
- Formal artifact IDs are listed in
  `docs/quantmind2/data/TUSHARE_AUTHORITY_V1.json`.
