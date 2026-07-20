# QM2-P0-015G Implementation Report

## 1. Task Summary

`partial`. Formal Qlib evidence proves that none of the four locked strategy
paths carried either audited security across termination. The historical
Fixed-100 benchmark did have theoretical equal-weight exposure and the
governed Tushare graph has no settlement event, so affected benchmark and
Fixed-100-relative metrics are explicitly noncanonical.

## 2. Goal and Scope

- Reconstruct formal 2025 orders and positions for `600837.SH` and
  `601989.SH` across three locked candidates and their equal-weight combination.
- Audit Fixed-100 membership exposure independently from strategy exposure.
- Establish a generic evidence-gated `SecurityTerminationPolicyV1`.
- Preserve source artifacts and publish a separate immutable audit with Store
  validation, cold recovery and exact replay.

## 3. Explicit Non-goals

No Agent call, Optimization, candidate or parameter change, universe
replacement, inferred liquidation, zero-return fill, stale valuation, cash or
conversion assumption, corrected return, Fresh Validation, Promotion,
LightGBM, database/API/UI, dependency/lockfile change or push.

## 4. Preflight State

- Repository: `quantmind-main` at the configured QuantMind root.
- Branch: `master`.
- Base commit: `20fccfe82c7b258a7f52cff54ff597e650565851`.
- Worktree: clean; unrelated dirty files: none.
- Source experiment: `tha_2b367621...76383b`.
- Lifecycle evidence: `thf_9f389863...7307b2`.
- Lifecycle policy: `fulp_60672b83...a632a`.
- Factor Lab was read-only. Its configured formal source directory contains no
  non-`__pycache__` files, retaining the already recorded `/tmp` durability
  limitation.

## 5. Termination Facts

| Symbol | Status | Last market/tradable evidence | Effective/delist date | Settlement evidence |
|---|---|---|---|---|
| `600837.SH` / `SH600837` | D | 2025-02-05 | 2025-03-04 | absent |
| `601989.SH` / `SH601989` | D | 2025-08-12 | 2025-09-05 | absent |

The event records retain nullable settlement date, currency, cash per share,
replacement symbol and conversion ratio. No absent field was guessed.

## 6. Strategy Position and Trade Audit

| Strategy | SH600837 | SH601989 | Last formal exit | Canonical decision |
|---|---|---|---|---|
| equal-weight combination | never held | 35 position days; three buys and three sells | 2025-07-11 | `EXITED_BEFORE_TERMINATION` |
| Candidate `fi_d877...` | never held | 15 position days; one buy and one sell | 2025-04-21 | `EXITED_BEFORE_TERMINATION` |
| Candidate `fi_8f557...` | never held | never held | none | `NO_PORTFOLIO_IMPACT` |
| Candidate `fi_e0fb...` | never held | never held | none | `NO_PORTFOLIO_IMPACT` |

For the combination, the final positive `SH601989` position was 6,516.587818
shares on 2025-07-10 at 4.7835% portfolio weight and recorded market value
50,164.849418; the formal sell completed the next day. For `fi_d877...`, the
final positive position was 6,398.104403 shares on 2025-04-18 at 4.9281% and
recorded market value 45,792.000983; the formal sell completed on 2025-04-21.
Neither position exists after the 2025-08-12 last tradable evidence.

TopkDropout exposes generated orders and resulting positions, not a durable
formal daily target-weight series. The audit records target weight as
`not_emitted_by_topk_dropout`; it does not reverse-engineer a target from final
returns or holdings.

## 7. Fixed-100 Benchmark Audit

The benchmark is independently calculated as daily equal weight over the
observable locked members. It had unit-notional exposure of 1/100 to
`SH600837` on 2025-02-05 and 1/98 to `SH601989` on 2025-08-12. On subsequent
missing-market dates the existing computation removes the member and
re-normalizes the denominator. There is no governed sale, cash settlement,
conversion, merger exchange or write-off event supporting that transition.

Consequently:

- affected shares and true settlement value are unknown;
- stale valuation days are not reported because the implementation removes
  the member rather than formally carrying a stale price;
- maximum metric impact is unknown, not a fabricated bound;
- 2025 and full-period Fixed-100 benchmark returns are noncanonical;
- every affected Fixed-100-relative strategy excess metric is noncanonical.

## 8. Security Termination Contract

`SecurityTerminationPolicyV1` supports `delisting`, `cash_settlement`,
`stock_conversion`, `merger_exchange`, `write_off` and
`unknown_termination`. A no-exposure or fully exited strategy requires no
settlement action. A crossing position requires immutable settlement evidence;
otherwise it is `SECURITY_TERMINATION_SETTLEMENT_UNRESOLVED` and affected
backtests are noncanonical. Implicit last-price sale, stale valuation, zero
return, cash and conversion are forbidden.

Policy ID:
`stp_e821399918903023292680e5291fa2a859d8e471f78beeefa1d26e3608740ffc`.

## 9. Parity and Canonicality

Four formal 2025 Qlib reruns preserved source positions and all key metrics at
`1e-12` tolerance. No strategy crosses a termination.

- 2019--2024: unchanged and canonical.
- 2025 strategy absolute and CSI300-relative results: canonical.
- 2025 Fixed-100 benchmark and Fixed-100-relative results: noncanonical.
- 2026H1: unchanged and canonical because both securities are inactive before
  the period.
- Full-period strategy absolute and CSI300-relative results: canonical.
- Full-period Fixed-100 benchmark and Fixed-100-relative results:
  noncanonical.

Noncanonical metrics may not drive Agent feedback, factor ranking, parameter
selection or Promotion.

## 10. Artifact Store and Replay

- Audit Artifact: `htf_4a0762a5b87c0f2837fe70cbf51f2b4ecdc56da8482c25807ec566ba43ba6c3f`.
- Descriptor: `sad_f0e4486f...db3b104`.
- Files: policy, symbol events, strategy exposure, benchmark exposure,
  position timeline Parquet, impact summary, canonicality and Manifest.
- Formal run: four Qlib calls; zero Agent, Optimization, Promotion, Tushare
  network or legacy-data calls.
- Inventory: `sai_3ce20ede...b7a25`, 46 artifacts / 1,597 blobs.
- Integrity: healthy, Missing 0, Unreferenced 0.
- Cold materialization: passed.
- Exact replay: same Artifact ID, 0 Qlib calls, 0 new artifacts, 0 new blobs.

## 11. What Changed and Why

- Added the generic termination event/policy and audit engine.
- Extended the existing formal Qlib runner with opt-in, symbol-bounded order
  evidence capture; ordinary calls retain their prior output and cache key.
- Added a formally validated termination-follow-up Artifact kind and CLI.
- Added policy, classification, settlement and Artifact contract tests.
- Updated Project Memory and context checks to record the partial conclusion.

## 12. Files Changed

Production changes are limited to the security-termination package, opt-in
formal Qlib evidence capture and the existing Artifact Store validation edge.
Tests, one CLI, Project Memory and this Implementation Run are also changed.
No source Dataset, Qlib binary, Factor, signal, candidate, parameter, model,
dependency, lockfile, configuration or database file changed.

## 13. API, Database, Configuration and Security

- External API changes: none.
- Database changes/migrations: none.
- Configuration/environment changes: none.
- Dependencies/lockfiles: unchanged.
- Security: no credential was read or persisted; no Tushare network request was
  made. Only hash-verified governed Store artifacts were materialized.

## 14. Tests Executed

- New policy/lifecycle focused tests: 20 passed.
- Full relevant termination, lifecycle, Tushare, Store, runtime, historical and
  Context suite: 78 passed.
- Context Bootstrap: 42 checks passed.
- Formal Qlib audit: four strategy runs and parity checks passed.
- Cold recovery and exact replay: passed with zero replay calls/writes.
- `py_compile`, JSON parsing and `git diff --check`: passed.
- Initial `python` and bundled-runtime pytest attempts did not run because those
  interpreters did not expose pytest; the existing project virtualenv was used
  without installing or changing dependencies.

## 15. Known Limitations

- The governed authority has no corporate-action settlement evidence for the
  two benchmark terminations. The task cannot be `completed` and no corrected
  benchmark return can be published.
- TopkDropout does not expose formal daily target weights; the unavailable
  field is explicit in the timeline rather than inferred.
- Tushare authority ends at 2026-06-23; incremental update and late revision
  policy remain absent.
- Formal Qlib attempts a production model lookup before consuming the explicit
  signal path; the isolated run logs the unavailable database and completes
  from the supplied formal signals. No database result was used.

## 16. Compatibility, Rollback and Remaining Work

Existing Qlib behavior changes only when the optional audit-symbol argument is
provided. Rollback is one commit revert plus ceasing to reference the new
Artifact; immutable Store evidence and prior source artifacts must not be
deleted or overwritten. A future separately authorized Corporate Action
Provider is required to resolve Fixed-100 settlement. This task authorizes no
successor.

## 17. Git / Workspace State

- One independent commit: `fix(qm2): audit security termination handling`.
- No amend and no push.
- Post-commit Planner must be validated and indexable with zero evidence gaps
  and warnings.

## 18. Artifact Index

- Policy: `stp_e8213999...740ffc`.
- Termination audit: `htf_4a0762a5...ba6c3f`.
- Store Inventory: `sai_3ce20ede...b7a25`.
- Source experiment: `tha_2b367621...76383b` (unchanged).
- Lifecycle follow-up: `thf_9f389863...7307b2` (unchanged).
