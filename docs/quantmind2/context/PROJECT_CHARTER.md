# Project Charter

## Goal

QuantMind 2.0 is an AI Quant Research Platform. It converts a research goal
into reproducible factor definitions, validation evidence, model or single
factor signals, official Qlib backtests, and risk analysis.

## Primary workflow

`Research Goal → Research Agent → Factor DSL/IR → Factor Optimization → Factor
Validation → Factor Registry → Single Factor or LightGBM → Unified Signal →
Qlib Backtest → Risk Analysis`.

## System boundaries

- QuantMind is the target host and owns the existing LightGBM, inference,
  Qlib, strategy, backtest, and risk services.
- The only official Factor Lab source is
  `/tmp/quantmind_factor_lab_real_bounded_v7_orchestrator_v1/backend/services/engine/factor_lab/`.
  It is a read-only capability donor until explicitly migrated by contract.
- Tushare Pro is the only active A-share market-data entry under ADR-0011,
  which supersedes the unverified TongDaXin choice in ADR-0003.
- Dataset Snapshot is the authoritative research-data version. Parquet stores
  large factor/training materializations. PostgreSQL stores tasks, state,
  metadata, indexes, and query projections. Qlib binary is a consumer view.
- Existing LightGBM combines multiple factors. Existing Qlib produces official
  portfolio and risk conclusions.
- The immutable Tushare fixed-500 Dataset/Artifact graph is authoritative. The
  fixed-100 Qlib binary is a derived consumer view, never a data source.

## Non-goals

- Do not replace LightGBM or Qlib.
- Do not make Python `factor_impl.py` the v1 standard factor path.
- Do not perform DSL structure evolution in v1.
- Do not merge repositories wholesale or treat temporary artifacts as
  production evidence.
- Do not allow an Agent to approve validation, feature, or production state.

## Long-term collaboration

Humans, web ChatGPT, and new Codex sessions must recover context from this
repository without replaying historical chats. Every implementation task must
produce an immutable report and manifest tied to Git evidence.

## Principles

- Safety: untrusted Python is Docker-only; official conclusions require real
  Qlib; Frozen Test access is isolated.
- Reproducibility: data, factors, transforms, models, signals, environments,
  code, and seeds have immutable identities.
- Lineage: derived artifacts reference their exact sources.
- Honesty: implemented, partial, planned, not implemented, deprecated, and
  blocked states are never conflated.
