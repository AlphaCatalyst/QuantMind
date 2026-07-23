# Autonomous Factor Research Campaign v2

Status: implemented by `QM2-R2-002`.

## Purpose and evidence semantics

Campaign v2 is a retrospective locked-holdout research workflow. It reduces
within-Campaign adaptation but does not create Fresh, Frozen Test, predictive,
Promotion, or production evidence. The v1 candidates remain immutable
`research_registered/retrospective_v1_candidate` objects; their 2025 and
2026H1 degradation establishes that autonomous execution succeeded while
generalization did not.

## Frozen time partitions

| Partition | Dates | Agent | Planner | Failure memory | Parameters | Shortlist | Registry |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development | 2019-01-02..2020-12-31 | aggregate | yes | yes | yes | yes | no |
| adaptive_discovery | 2021-01-04..2022-12-30 | aggregate | yes | yes | no | yes | no |
| locked_holdout | 2023-01-03..2024-12-31 | no | no | no | no | no | yes |
| contaminated_report | 2025; 2026-01-05..2026-06-23 | no | no | no | no | no | no |
| fresh_forward | after the latest used market date | no | no | no | no | no | no |

Discovery receives a physically cropped feature matrix ending 2022-12-30.
The full matrix is instantiated for holdout evaluation only after rounds stop,
Agent and Planner close, Failure Memory freezes, and the immutable Shortlist
Lock is published. Violations fail with
`LOCKED_HOLDOUT_EVIDENCE_CONTAMINATION`.

## Spec and budgets

`AutonomousFactorCampaignSpecV2` freezes `technical_factor_campaign_002`
before an Agent call. Ceilings are 12 rounds, 12 Agent calls, 36 proposals,
24 admissions, 48 local-rescue trials, 100 Discovery Qlib calls, 12 Holdout
Qlib calls, 12 report Qlib calls, six shortlist entries, three final locks,
and six near-miss reports. Strategy and Combined Optimization, market-data
network access, and Promotion are forbidden.

## Search, shortlist, and holdout

Agent proposes structure and explicit default parameters. Admission retains
the v1 DSL/PIT/feature/complexity/semantic/redundancy checks. Development uses
the fixed TopK20, n_drop5, 10-session equal-weight protocol and at most a
one-hop local rescue. Discovery evaluates only 2021 and 2022.

Each Discovery-eligible object receives `CandidateSearchExposureV1`. Risk is
low at no more than 10 effective searches, medium at 11–25, and high above
25. Exposure is disclosure and a Discovery tie-break; it never weakens
eligibility.

`AutonomousCampaignShortlistLockV1` freezes no more than six objects,
parameters, orientation, correlations, exposure, and Discovery ordering while
the holdout read count is zero. `CampaignFailureMemoryFreezeV1` prohibits
later append. `LockedHoldoutAccessControllerV1` opens the 2023–2024 evidence
once. Holdout is Pass/Fail only. If more than three objects pass, capacity
uses the already-frozen Discovery order, never Holdout performance.

The Holdout Gate requires complete two-year data, at least 90% coverage, no
infinity or PIT violation, positive RankIC in both years, median RankIC at
least 0.003, worst RankIC at least -0.003, at least one positive CSI300 excess
year, positive median excess, worst excess above -5 percentage points,
median turnover no more than 30, median best-ten-day contribution no more
than 35%, unchanged parameters/orientation, correlation below 0.85, and no
specified Discovery-to-Holdout sign failure.

Only survivors become v2 `research_registered` candidates. Failures receive
an immutable failure report and cannot enter Registry. Contaminated reports
run only for survivors and never feed selection. Each survivor receives a
no-backfill Fresh Lock starting on the first formal trading date after the
latest used market date, with a minimum of 60 Fresh trading days, five
completed holding windows, and three independent rebalance cycles.

## Formal Campaign 002 result

Canonical Spec:
`afc2_f3ba310a3b67cc9a4291744ae96c1d550bd7dd18ad9dcbe1be62cc52a9f17cb2`.

The Campaign stopped after four rounds because Development improvement was
exhausted. Four Agent calls produced 12 proposals and eight admissions.
Seventeen Discovery Qlib calls yielded one shortlist object. Shortlist
`acsl1_3746253e487016ec80ffe15088f6ea04ea5daff3a09f7d5a35b03681cab5f0a4`
was published with zero prior holdout reads.

The single Holdout object passed every gate except positive RankIC in both
years: 2023 RankIC was 0.009854 and 2024 RankIC was -0.002376. It therefore
did not enter Registry. The legal terminal state is
`completed_no_holdout_survivor`; Candidate and Fresh Lock counts are zero.
Report:
`afcr2_bbeee1e907b2406e46dc82d72614e0e047c8e449457cc6fa9bd9fc82603cb4b0`.

Cold validation reports zero evidence gaps and healthy Store integrity.
Exact replay performs zero Agent, optimization, Qlib, Tushare, network,
Registry, Fresh Lock, Promotion, Artifact, and Blob operations.
