# Implementation Report — QM2-R1-003

## 1. Task Result

Completed. Research Artifact Completeness v1 and a Store-backed six-round
skip-recent momentum deep dive were implemented and executed.

## 2. Preflight State

Repository was clean on `master` at
`588d74888d3ffdd2a210804e957a81cd4c04a170`; unrelated dirty files: none.

## 3. Previous Artifact Gap

The R1-002 candidate definition was unrecoverable and was not reconstructed.
This task performed new research from scratch.

## 4. Research Artifact Completeness Contract

The new contract separates Raw Response, Proposal, Template, Trial, Fold Lock,
Eligibility, Candidate, Report, Assessment and Experiment.

## 5. Artifact Completeness Gate

Each stage validates, publishes, cold-restores and revalidates before use.
Missing fields hard-fail as `ARTIFACT_COMPLETENESS_FAILED`.

## 6. Agent Response Persistence

Nine completed real responses retain exact bytes, hash, length,
`openai_codex_cli/gpt-5.6-terra`, prompt hash and decision identity. No secret
is stored.

## 7. Proposal Persistence

Every Proposal retains its normalized payload, rationale, Decision and Raw
Response lineage.

## 8. Template and DSL Persistence

Admitted definitions retain canonical DSL/AST, Features, parameters,
orientation policy, structural fingerprint and hypothesis.

## 9. Trial Persistence

Fifty unique parameter Trials were counted; fold-specific detail artifacts
retain parameters, Factor Instance, complete Parquet values and metrics.

## 10. Fold Lock Persistence

All four selected parameter sets were locked and cold-restored before their
next-year evaluation.

## 11. Eligibility Evidence Persistence

All Fold metrics, formal Qlib metrics, neighborhood rows, cost, turnover,
concentration, correlation, regimes and gate failures are retained.

## 12. Skip-Recent Research Protocol

Only the immutable momentum Catalog/Dataset were read. Strategy remained
TopK20, n_drop5, five-session rebalance, open, lag one and CSI300.

## 13. Round 1

Classic skip-recent: three candidates; none eligible. Best failed worst RankIC.

## 14. Round 2

Multi-horizon consensus: two admitted candidates; none eligible.

## 15. Round 3

Path quality: two admitted candidates; none eligible.

## 16. Round 4

Relative/residual: two admitted candidates; none eligible.

## 17. Round 5

Risk-adjusted: three admitted candidates; one independently eligible.

## 18. Round 6

Failure-driven hybrid: three admitted candidates; one independently eligible.

## 19. Early-stop Result

All six fixed rounds ran; no extra round or structure evolution was opened.

## 20. Candidate Eligibility

Fifteen candidates were evaluated; two passed every unchanged standalone gate.

## 21. Parameter Stability

Direct one-parameter neighbors were formally evaluated. Both locks meet the
minimum 0.50 stability threshold.

## 22. Candidate Ordering

Ordering used four research/evaluation Folds only and excluded all 2025/2026
and Fixed-100-relative evidence.

## 23. Final Candidate Locks

Two `research_registered` locks were created; no production or Promotion
state was written.

## 24. Candidate Definitions

- `srmcl1_56201db3...9f95b`: z-scored deviation of `momentum_60_10`
  from its 40-session rolling mean.
- `srmcl1_4e0abd49...c80b4`: `momentum_60_10 - 0.75 ×
  distance_to_high_60`.

## 25. 2025 Report

Candidate returns/excess are 7.78%/-13.41% and 8.61%/-12.58%. Ensemble return
is 9.77%, excess -11.42%. Reports are contaminated retrospective evidence.

## 26. 2026H1 Report

Candidate returns/excess are -7.22%/-11.50% and -10.36%/-14.63%. Ensemble
return is -7.47%, excess -11.75%.

## 27. Regime Report

Trend, volatility and breadth diagnostics are retained for every Fold and
report period and never enter Agent memory or selection.

## 28. Ensemble Decision

Two eligible, structurally distinct subfamilies allow the equal-weight
ensemble. Diversity was not used to reject either standalone lock.

## 29. Existing-factor Comparison

Both locks pass the <0.85 existing-factor correlation gate. The unrecoverable
R1-002 candidate remains summary-only historical evidence.

## 30. Registry

Two entries are `research_registered`; promotion candidates, approved and
active counts are zero.

## 31. Artifact Store

Experiment `srme1_072b0d1a...d1ab3c` is canonical. Store integrity is healthy,
Missing 0 and Unreferenced 0.

## 32. Trial Cold Recovery

Trial detail and embedded Factor Values restore and hash-validate from Store.

## 33. Candidate Cold Recovery

Both locks and all eligibility evidence restore from empty destinations.

## 34. Experiment Cold Recovery

The full 368-artifact lineage restores without relying on disposable runtime
directories.

## 35. Exact Replay

Replay reports Agent 0, Optimization 0, Qlib 0, network 0, new artifacts 0,
new blobs 0 and Promotion 0.

## 36. Files Added

Skip-recent domain package, CLI, tests, two contracts, and this Run.

## 37. Files Modified

Artifact kind/validation/cache routing, Project Memory, roadmap and context
validation expectations. No data, model, strategy or Qlib business behavior.

## 38. Tests Executed

Skip-recent unit tests: 12 passed. Relevant domain/Store/runtime regression:
43 passed. Context suite: 21 passed. Context Bootstrap: 42 checks passed.

## 39. Expected vs Actual

Expected up to 12/18/144 calls/templates/Trials; actual completed evidence is
9 Agent calls, 15 candidates, 50 unique Trials and 178 formal Qlib calls. Two
locks and an ensemble were produced.

## 40. Implementation Run

`QM2-R1-003-20260721T164832Z-588d748`, Manifest v2, one independent commit.

## 41. Project Memory Updates

Current State, Handoff, Component Catalog, Known Issues and Roadmap record the
complete evidence and negative later-period continuation.

## 42. Known Limitations

The work is retrospective adaptive research, not Fresh Validation. Qlib
feature loading is serialized because the cached setuptools 83 no longer
ships the legacy `pkg_resources` module required by subprocess MLflow imports.
Two interrupted Agent subprocesses produced no response artifact; nine
completed responses are authoritative and the bounded call ceiling was not
exceeded.

## 43. Final Research Conclusion

Skip-recent eligibility is reproducible in two replayable structures, but
neither structure nor their ensemble continues versus CSI300 in 2025 or
2026H1. No promotion conclusion is supported.

## 44. Git State After

The Run is prepared uncommitted; final commit/planner evidence is completed
after Manifest finalization. No push is performed.
