# QM2-R2-009 Implementation Report

## 1. Task Result

Completed uncommitted before the final commit. The two-member Cohort is
frozen, the first formal Fresh date is observed, both fixed models have one
prediction, and evidence remains legally accumulating.

## 2. Preflight State

Repository was the QuantMind main repository on `master` at
`dca8e42494af418c7afe74bb92c4d1aaf1bc9f1d`. The worktree was clean and
there were no unrelated dirty files. No reset, stash, amend, dependency
installation, lockfile update, Factor Lab write, or push occurred.

## 3. Candidate Recovery

The Store supplied exactly:

- Bundle B Candidate `mhrmc1_6b1a97e5b5a19052387ac06c64c3d1cea998a502542479b47c535b1eb24527c3`;
- Bundle C Candidate `mhrmc1_83272b1d8093eccb6b3823d62fa618685c139497269bde5742006311ce856c23`.

Both remain `retrospective_model_candidate` and
`worth_fresh_observation=true`.

## 4. Fresh Lock Recovery

Locks `mhmfl1_59790b02d1ebcd6b8ed2a7d5e264d10a9060a3f91a0f52fd6c3ebdd6f3e5db17`
and `mhmfl1_1b78c7a94afc15505c852af9796b5b6b05e6ca68151eb11924a146e95bc0cdfc`
bind the exact Candidate, Bundle, Label, model, walk-forward, seed, strategy,
primary-statistic, no-backfill, and monthly-retraining contracts. Missing or
different monthly policy hard-fails as `FRESH_RETRAINING_POLICY_INCOMPLETE`.

## 5. Executable Label Guard

The executable identity is
`trl1_38786d6192c987a887de52477ee2dfcca7f8a209ab5744ff70757339cb62cf3a`:
`technical_return_1d`, adjusted open T+1 to adjusted close T+1, HAC lag 10,
without forward fill. Drift raises `EXECUTABLE_LABEL_IDENTITY_MISMATCH`.

## 6. Fresh Cohort

Cohort `mfcc1_faab1ee6f07fe1ce46bb13ab8403e104433c5781058d3e8c6720e6ffd7bde6dc`
was published before the first Fresh market read and contains exactly the two
Candidates and Locks. Membership, Label, model, seeds, Bundle rules, strategy,
minimum evidence, HAC/BH, and no-backfill are immutable.

## 7. Fresh Start Date

The formal SSE calendar derives `2026-07-24`, the first official open date
strictly after project exposure date `2026-07-23`. The date is not hardcoded
as an implementation shortcut.

## 8. Credential Safety

Credentials are accepted only from the environment, never by CLI. Artifact
identities record only `environment_only_not_persisted`; no secret, prefix,
suffix, or hash is logged or persisted. The absent-credential path freezes the
Cohort, performs zero network calls, and returns `fresh_data_blocked`.

## 9. Incremental Market Data

Only `trade_cal`, `daily`, `adj_factor`, `daily_basic`, and `index_daily` were
called. The formal Snapshot used one call per endpoint. Collection was limited
to the increment after the latest official stored date and preserved endpoint
accounting, checkpoint, de-duplication, schema, symbol, adjustment, calendar,
and lifecycle evidence.

## 10. First-seen Snapshot

Snapshot `fms1_e0aaaf867bea7ac11fa754d11ef9122be94dd48f2b1d048355585deeea9f83e3`
covers only 2026-07-24. It has 479 `daily`, 479 `adj_factor`, 479
`daily_basic`, one CSI300 row, no duplicates, no missing adjustment keys, and
no missing required daily fields. It is first-seen, revision 1, immutable, and
does not overwrite its parent.

## 11. Bundle B Materialization

Bundle B reuses frozen `expanded_technical_space`: all 20 Catalog v3 Terminal
Features and six frozen Primitives in their registered order. No Fresh feature
selection or Feature mutation is permitted.

## 12. Bundle C Materialization

Bundle C reuses `combined_decorrelated_technical`. Its membership Artifact
`fmbm1_395aa09d...8438410` is selected only from the purged training slice by
the frozen label-free coverage, finite-ratio, dispersion, persistence, and
correlation rule. Fresh Labels, performance, importance, and outer prediction
reads are zero.

## 13. Initial Fresh Models

Six immutable `initial_fresh_model_event` Artifacts exist: two Candidates by
three seeds (`20260701`, `20260702`, `20260703`). Training ends before the
Fresh prediction date after the unchanged purge. LightGBM configuration,
200 rounds, no early stopping, one thread, determinism, and equal seed
weighting remain frozen.

## 14. Monthly Retraining

The runtime implements expanding monthly retraining on the first observed
official session of a new calendar month. The cutoff is the immediately prior
official prediction date and remains strictly earlier than the effective
prediction. Three seed-model Artifacts form one monthly event; minimum-evidence
counting de-duplicates the seed rows by effective date. The current count is
zero because only July 24 exists; initial training does not count.

## 15. Fresh Predictions

Each Candidate has one 2026-07-24 prediction Artifact over 98 fixed-universe
members with 100% finite coverage. Each persists seed predictions, equal-weight
raw prediction, cross-sectional score, signal, training cutoff, model IDs,
Bundle membership, Snapshot lineage, lag one, T+1 execution rule, and checksum.

## 16. Mature Fresh Labels

Mature label count is zero. A July 24 L1 observation requires complete
first-seen adjusted open, adjusted close, and tradeability for the next
official session; the Snapshot ends July 24, so no early or filled Label was
published.

## 17. Fresh Strategy Results

Both fixed strategy Artifacts are `accumulating`. The protocol is exactly
TopK20, drop5, ten-session rebalance, equal weight, lag one, open execution,
and CSI300 benchmark. There are zero completed holding windows and zero
rebalance periods; no performance conclusion is reported.

## 18. Fresh Observation Counts

Each Candidate has one Fresh trading day, one prediction day, zero mature
Label days, zero completed holding windows, zero rebalance periods, zero
monthly retraining events, and zero PIT violations.

## 19. Minimum-evidence Gate

Both Candidates fail only by immaturity against the unchanged gate of 60
trading days, five holding windows, three rebalances, two monthly retraining
events, 90% coverage, and zero PIT violations. Their status is
`fresh_evidence_accumulating`.

## 20. Multiple-testing Status

Artifact `fmcmt1_450ff0e8...a326a` records two frozen hypotheses but zero
tested hypotheses and `awaiting_all_members_minimum_evidence`. HAC and BH were
not called because neither member is mature.

## 21. Candidate B Fresh Status

`fresh_evidence_accumulating`; no support, rejection, or inconclusive
classification is permitted.

## 22. Candidate C Fresh Status

`fresh_evidence_accumulating`; no support, rejection, or inconclusive
classification is permitted.

## 23. Cohort Status

Heartbeat status is `fresh_evidence_accumulating`. The two-member Cohort is
evaluated synchronously and cannot be split.

## 24. Registry

Registry writes are zero. Candidate status, approved, active, production, and
promotion-candidate state are unchanged.

## 25. Heartbeat

Heartbeat `fmhr1_224de05ef7b20675ec4227eaa0efa487de73918cf0a1a1f55297812927f9fe42`
binds the Cohort, Snapshot, two observations, two assessments, and cohort
multiple-testing checkpoint. The final resumed publication used zero Tushare,
network, training, prediction, label, Qlib, strategy, testing, status,
Registry, and Promotion calls/writes; only the missing Heartbeat Artifact was
published.

## 26. Scheduling Contract

`supervisor_fresh_heartbeat.sh` and the operations document define the
project-local entry and restricted environment. No `launchd`, cron, or other
system scheduler was installed, loaded, or changed.

## 27. Artifact Store

The Store contains one Cohort, one Snapshot, two Bundle memberships, six
training events, two predictions, zero mature labels, two strategy
observations, two Candidate observations, one cohort-test checkpoint, two
assessments, and one Heartbeat. Integrity is healthy: Missing 0,
Unreferenced 0.

## 28. Cold Recovery

Cold CLI replay recovered the Heartbeat by immutable Store identity without
network, model, or write activity.

## 29. Resume Test

The first formal execution published the Snapshot and then encountered local
LightGBM runtime loading and later contract-integration failures. Resume
recovered the unprocessed Snapshot before network access, reused all completed
seed/model/prediction/checkpoint Artifacts, and published the terminal
Heartbeat. No Snapshot or model was duplicated.

## 30. Exact Replay

Both same-date heartbeat replay and explicit cold replay returned
`exact_replay` for the same Heartbeat ID with all twelve external/computation/
write counters equal to zero.

## 31. Files Added

Added the `fresh_model_cohort` package, its focused test module, accepted
architecture contract and schema, operations contract, scheduler entry, and
this immutable Implementation Run.

## 32. Files Modified

Extended Artifact Store kind/validation registries, the Supervisor CLI,
Project Memory, Context validation guard, and Current State schema. Existing
Candidate, Lock, Label, model, Qlib, Registry, and Promotion artifacts were
not modified.

## 33. Tests Executed

- Focused Fresh and Context suite: 109 passed.
- Artifact Store/Runtime, fixed-model, multi-horizon, Supervisor, Fresh and
  Context regression: 168 passed.
- Context Bootstrap: 42 checks passed.
- All documentation JSON parsed.
- `py_compile` and `git diff --check` passed.
- Formal heartbeat, interrupted resume, Store integrity, cold replay, and exact
  replay passed.

One initially mistyped nonexistent test filename produced “no tests ran”; it
was corrected immediately and is not represented as a passing test.

## 34. Expected vs Actual

Expected two frozen Candidates, calendar-derived no-backfill start, fixed
model/strategy, immutable first-seen evidence, minimum gate, Store recovery,
and no Promotion. Actual matches. Only one Fresh date is available, so mature
Labels, monthly retraining, Qlib strategy execution, HAC/BH, and terminal
Candidate classifications correctly remain pending.

## 35. Implementation Run

Run ID is `QM2-R2-009-20260724T164634Z-dca8e42`. Manifest v2 accompanies this
report. Pre-commit status is `completed_uncommitted`; the task requires one
subsequent independent commit and post-commit Planner verification.

## 36. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues, Roadmap, and their
machine-readable forms now record the Cohort, 2026-07-24 Snapshot, accumulating
status, exact Heartbeat, no Registry/Promotion, and no authorized successor.

## 37. Known Limitations

Only one Fresh session exists and no Label is mature. System scheduling is not
installed. The strategy Artifact is an accumulating fixed-protocol checkpoint;
formal Qlib execution cannot occur before a completed holding window. The
single-host Artifact Store remains the existing operational boundary.

## 38. Final Research Conclusion

There is no Fresh performance conclusion. Both R2-008 L1 model Candidates are
now under a correct immutable no-backfill observation protocol, but neither is
supported, rejected, validated, approved, active, production-ready, or eligible
for Promotion.

## 39. Git State After

The task will create one commit with message
`feat(qm2): automate fresh model cohort observations`, without amend or push.
Post-commit requirements are clean worktree and Planner
`validated=true`, `indexable=true`, zero evidence gaps, and zero warnings.
