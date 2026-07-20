# QM2-P0-015H Implementation Report

## 1. Task Summary

`blocked`. A live, Tushare-only capability audit and immutable evidence chain
were completed, but the current account cannot access issuer announcements or
structured merger endpoints and the available responses do not contain the
settlement terms required for either 2025 termination. The formal result is
`TUSHARE_CORPORATE_ACTION_EVIDENCE_INSUFFICIENT`; no Fixed-100 revision or
canonical relative metric was published.

## 2. Goal and Scope

- Probe Tushare capabilities for the two governed terminations without
  presuming endpoint availability.
- Preserve raw responses, safe failures, schemas and hashes in an immutable
  Raw Snapshot.
- Normalize evidence without defaulting absent settlement fields.
- Freeze the investable, self-financing Fixed-100 Benchmark Contract v2.
- Implement generic evidence-gated cash, conversion, merger-exchange,
  residual-cash and write-off settlement mechanics.
- Publish only evidence supported by Tushare and exact-replay it from Store.

## 3. Explicit Non-goals

No web or alternate Provider, manual ratio, remembered event detail, price
inference, last-price sale, zero-return assumption, Agent call, Optimization,
candidate/parameter/direction change, strategy rerun, Qlib strategy call,
universe replacement, 2026H1 rerun, CSI300 change, Promotion, LightGBM,
database/API/UI, dependency/lockfile change, amend or push.

## 4. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `623acf8d328b219bc32396e6ae21a2312aff8e62`.
- Worktree: clean; unrelated dirty files: none.
- Provider authority: `tushare-pro-v1`, active.
- Source termination audit: `htf_4a0762a5...ba6c3f`.
- Source lifecycle follow-up: `thf_9f389863...7307b2`.
- Store baseline: 46 artifacts / 1,597 blobs, healthy.
- The official Factor Lab path remained read-only. At final verification it
  contained no non-cache source file, so an earlier supplied digest could not
  be independently recomputed.

## 5. Live Tushare Capability Evidence

The environment-only credential was used for 19 redacted requests. Thirteen
requests were available and six returned safely classified permission or
parameter errors.

| Endpoint | Result | Evidence boundary |
|---|---|---|
| `stock_basic` | available for both symbols | status D and delist date |
| `daily` | available for both symbols | last observed trading date |
| `namechange` | available for both symbols | name history only |
| `suspend_d` | available for both symbols | suspension history only |
| `share_float` | available for both symbols | share-capital history only |
| `dividend` | available for both symbols | ordinary dividend records, not termination settlement |
| `major_news` | 800 metadata rows | title/time/source/URL metadata, not issuer announcement text or structured settlement |
| `anns_d` | unavailable for both symbols | no raw issuer announcement |
| `merge`, `merger` | unavailable for both symbols | no structured merger or conversion fields |

Safe errors contain no token or upstream account detail. No inaccessible
endpoint was treated as proof that an event or settlement did not exist.

## 6. Raw Corporate Action Artifact

- Raw Snapshot:
  `tsca_raw_c8c04e0228791d6a6c6103b249b6c9172668b3126aa94aba6377c396c9291b13`.
- Files: `requests.json`, `events.parquet`, `announcements.parquet`,
  `quality.json`, `manifest.json`.
- Counts: 19 requests, 409 event/status rows and 800 news-metadata rows.
- Identity binds Provider, symbol set, request contracts, returned schemas and
  response hashes. It excludes token, account, physical path and request time.
- Credential scan across the repository and formal working artifacts found
  zero token-byte matches.

## 7. Normalized Events and Evidence Completeness

Event Set:
`scae_a90b37266807856f0644bb242364374ced4666275bbcfaf95831ba20907abd1f`.

| Symbol / Event ID | Type | Last tradable | Effective | Settlement fields | Completeness |
|---|---|---|---|---|---|
| `SH600837` / `scaev_910b7231...1f76c` | delisting | 2025-02-05 | 2025-03-04 | all null | `evidence_missing` |
| `SH601989` / `scaev_a612839f...e0044` | delisting | 2025-08-12 | 2025-09-05 | all null | `evidence_missing` |

For both events, announcement date, settlement date, cash per share,
replacement symbol, conversion ratio and residual cash per share remain null.
The available Tushare evidence establishes termination dates but cannot prove
whether original holders received cash, replacement shares or another governed
settlement. Neither event may be upgraded to cash settlement, stock conversion,
merger exchange or write-off.

## 8. Settlement Contract

The generic settlement engine supports:

- cash credit on the formal settlement date;
- stock conversion or merger exchange at the governed ratio;
- fractional-share residual cash when explicitly evidenced;
- evidence-backed write-off;
- hard failure for incomplete or unknown settlement.

It contains no security-specific ratios or outcomes. Missing data raises
`SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED`; it never supplies a last price,
zero, cash amount, replacement symbol or conversion ratio.

## 9. Fixed-100 Benchmark Contract

Contract:
`fubc_e1885a790fc9f3f2825dab5954a02e7154cbc013ead8bbd116384630b22513e4`.

- Semantics: investable, self-financing, equal-weight portfolio.
- Universe lock remains `tu100_078e6609...2c526`; membership remains 100.
- Weekly rebalance and original transaction-cost policy are unchanged.
- New target weight is allocated only to active members.
- A missing observation is not a zero return.
- Corporate actions require governed termination evidence.
- Settlement cash remains in the portfolio cash account.
- A conversion asset may settle an old holding but is not a new locked member.
- No replacement security is introduced to refill the universe.

## 10. Benchmark Revision and Canonicality Gate

The all-events-complete gate rejected the Event Set. Therefore:

- benchmark revision artifacts published: 0;
- historical benchmark follow-up artifacts published: 0;
- 2025 revised Fixed-100 return: not produced;
- full-period revised Fixed-100 return: not produced;
- four revised Fixed-100-relative strategy metrics: not produced;
- 2025 and full-period Fixed-100 benchmark/relative metrics remain
  noncanonical.

2019--2024, strategy absolute NAV/returns, CSI300-relative metrics and 2026H1
remain unchanged and canonical under their existing evidence. No partial event
was used to mark the aggregate benchmark canonical.

## 11. Strategy Position Parity

The task did not rerun or rewrite any strategy. The immutable source termination
audit remains unchanged, including `position_timeline.parquet` SHA-256
`ce190168f7c19b470a238d8947b761cd7fc807025bc8fc4536fc74dcb4c2ce26`.
Its existing evidence still proves that all four strategy paths were flat
before the relevant terminations. Strategy NAV, trades, 2025 returns and
2026H1 results were not recalculated and no Qlib call occurred.

## 12. Artifact Store, Cold Recovery and Replay

- Imported three new immutable artifacts: Raw Snapshot, normalized Event Set
  and Benchmark Contract.
- Inventory: `sai_ff1a263a7a441df6ba6514a0cb178bc87a7172118a818e7f0b2918a3c0cfaee2`.
- Final Store: 49 artifacts / 1,607 unique blobs.
- Integrity: healthy; Missing 0; Unreferenced 0.
- Cold materialization of the three-artifact graph passed.
- Exact replay returned the same three IDs with Tushare network calls 0, Qlib
  calls 0, Agent calls 0, new artifacts 0 and new blobs 0.

The formal first pass made 19 Tushare calls, zero Qlib/Agent calls and zero
Optimization or Promotion writes. Replay needs no token and makes no network
request.

## 13. What Changed and Why

- Added the Tushare-only corporate-action capability, raw capture,
  normalization, evidence validation, settlement and benchmark-contract
  package plus CLI.
- Extended Artifact Store kinds and validation for the five frozen artifact
  families; only the three evidence-supported families were published.
- Added contract tests for credential handling, unavailable capabilities,
  immutable raw/event evidence, settlement mechanics, universe/cash semantics,
  revision gating, cold recovery and replay.
- Updated Project Memory to record the blocked outcome and continuing
  noncanonicality without inventing settlement evidence.

## 14. Files Changed

Production changes are limited to
`backend/services/engine/corporate_actions/` and the Artifact Store kind/
validator extension. One CLI, three focused tests, Context/Component/Issue/
Roadmap records, context validation and this Implementation Run are included.
No strategy, Qlib runner, Dataset, market-data authority, Factor, Candidate,
Optimization, Registry decision, model, configuration, dependency, lockfile or
database file changed.

## 15. API, Database, Configuration and Security

- External API changes: none.
- Database changes/migrations: none.
- Configuration changes: none.
- Dependencies/lockfiles: unchanged.
- Credential source: `TUSHARE_TOKEN` environment variable only.
- CLI has no token argument. Token is not persisted, logged, hashed or included
  in identity. Secret scan passed with zero matches.

## 16. Tests Executed

- Focused corporate-action and existing termination tests: 18 passed.
- Full relevant Tushare, lifecycle, termination, Artifact Store and Context
  suite: 79 passed in 16.16 seconds.
- Context Bootstrap: 42 checks passed.
- Formal exact replay: passed; 0 network/Qlib/Agent calls and 0 writes.
- `py_compile`: passed for the package and CLI.
- JSON parsing: 94 QuantMind 2.0 JSON documents parsed.
- Credential-byte scan: 0 matches.
- Factor Lab boundary: 0 non-cache source files; no write was made.
- `git diff --check`: passed.

The existing project virtual environment was reused. No dependency was
installed or updated.

## 17. Known Limitations

- The current Tushare account cannot provide issuer announcement bodies or
  structured merger/settlement fields for these events. Available news
  metadata is not sufficient evidence.
- Both normalized events remain `evidence_missing`; the actual settlement
  method, amount, ratio, replacement asset, residual cash and settlement date
  are unknown.
- No revised Fixed-100 return or Fixed-100-relative metric exists. Publishing
  one would violate the evidence contract.
- Tushare authority remains locked through 2026-06-23; incremental collection
  and late-data revision policy remain outside this task.
- The official Factor Lab `/tmp` source has the previously recorded durability
  risk and currently exposes no non-cache source file for digest verification.

## 18. Compatibility, Rollback and Remaining Work

Existing data, strategies and metrics are unchanged. The new package is an
evidence-gated side path and the Artifact Store extension is additive.
Rollback is one commit revert plus ceasing to reference the three new immutable
artifacts; Store evidence must not be silently overwritten. A future explicitly
authorized evidence source or Tushare entitlement change is required before
settlement can be completed. This task authorizes no successor.

## 19. Git / Workspace State

- One independent commit is required:
  `feat(qm2): add tushare corporate action settlement`.
- No amend and no push.
- Post-commit Planner must be validated and indexable with zero evidence gaps
  and warnings.

## 20. Artifact Index

- Raw Snapshot: `tsca_raw_c8c04e...91b13`.
- Event Set: `scae_a90b3726...abd1f`.
- Events: `scaev_910b7231...1f76c`, `scaev_a612839f...e0044`.
- Benchmark Contract: `fubc_e1885a79...513e4`.
- Store Inventory: `sai_ff1a263a...faee2`.
- Benchmark revision: none.
- Historical benchmark follow-up: none.
- Source termination audit: `htf_4a0762a5...ba6c3f` (unchanged).
