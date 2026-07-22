# Default-first Momentum Structure Search v2

## Authority and purpose

`QM2-R1-007` is retrospective structure research over Tushare Fixed-100,
Momentum Feature Catalog `mfc1_51dc0901...633b47c`, Dataset
`mfd1_9bb71725...08db2c`, CSI300 and governance Decision
`ogd1_7de0ba81...911f7f5`. It is not Fresh Validation, Frozen Test,
Promotion or production evidence.

## Frozen chronology

The Agent proposes a canonical DSL structure and explicit Template defaults.
The default is evaluated first on 2019-01-02 through 2020-12-31 under fixed
TopK20, n_drop5, five-session rebalance, equal weight, lag one, open execution
and CSI300. A passing default freezes immediately. A failing but near-gate
default may use only the R1-006 one-hop, one-parameter-at-a-time neighborhood,
bounded by `min(1 + 2*n, 7)`. Full, random, Bayesian, Strategy and Combined
searches are forbidden.

A successful default or rescue creates an immutable Development Parameter
Lock. Exactly those parameters are then evaluated separately in 2021, 2022,
2023 and 2024. Candidate ordering and Eligibility use only development and
these four annual results. The 2025 and 2026H1 periods are report-only and run
only for final Candidate Locks.

## Gates

The development default/local gate requires positive mean RankIC, RankIC
positive rate at least 50%, finite coverage at least 90%, turnover no more
than 45, zero infinities and PIT violations, plus positive CSI300 excess,
positive top-bottom spread or positive quantile monotonicity. Local rescue is
available only without data-quality/PIT failure and with RankIC at least
-0.002, positive rate at least 45%, or positive spread.

Annual Eligibility requires all four years, three positive RankIC years,
median RankIC at least 0.003, worst RankIC at least -0.008, three positive
CSI300-excess years, positive median excess, worst excess above -10 percentage
points, median turnover no more than 40, median best-ten-day contribution no
more than 35%, and maximum old-factor correlation below 0.85.

## Artifact and lifecycle contract

The formal chain preserves Agent response, Proposal, Template/AST, default
evaluation, optional local-rescue study, optional development lock and annual
evaluations, Eligibility, optional research-only Candidate Lock, optional
reports, Assessment and Experiment. Candidate status may only be
`research_registered`. Exact replay performs zero Agent, Factor/Strategy
Optimization, Qlib, network, new-object and Promotion calls.

## QM2-R1-007 result

Six real `openai_codex_cli` / `gpt-5.6-terra` calls produced eight evaluated
Proposals. Eight explicit defaults and thirteen one-hop local Trials used 21
formal Qlib calls. Every default had adequate coverage, positive oriented
RankIC and near-gate status, but exceeded turnover 45 and had neither positive
CSI300 excess nor positive group evidence. No local Trial rescued a structure.

Consequently no Development Parameter Lock, annual locked evaluation,
Candidate Lock, 2025 report or 2026H1 report exists. This is a valid terminal
research outcome: gates were not lowered, search was not expanded, and no
Promotion write occurred. Experiment `dfme1_e15ea299...98b6b0` and Assessment
`dfma1_b259450...271af4` cold-recover with Store integrity healthy, Missing 0
and Unreferenced 0.
