from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SymbolsFeaturesRequest(BaseModel):
    symbols: list[str]


class WatchlistAddRequest(BaseModel):
    run_id: str | None = None
    stock_name: str | None = None
    features_snapshot: dict[str, Any] | None = None


class PoolAddRequest(BaseModel):
    run_id: str | None = None
    stock_name: str | None = None
    model_id: str | None = None
    fusion_score: float | None = None
    thesis_summary: str | None = None
    features_snapshot: dict[str, Any] | None = None


class FactorCandidateCreateRequest(BaseModel):
    name: str | None = None
    expression: str
    description: str | None = None
    source: str = "manual"
    family: str | None = None
    tags: list[str] = []
    metadata: dict[str, Any] | None = None


class FactorCandidateEvaluateRequest(BaseModel):
    universe: str = "hs300"
    start_date: str
    end_date: str
    n_groups: int = 5
    holding_period: int = 5
    neutralize_industry: bool = True
    neutralize_cap: bool = True
    validation_profile: str = "default"
    metadata: dict[str, Any] | None = None


class FactorCandidatePromoteRequest(BaseModel):
    run_id: str | None = None
    feature_key: str | None = None
    feature_name: str | None = None
    force_shadow: bool = True
    metadata: dict[str, Any] | None = None


class FactorShadowSignalPublishRequest(BaseModel):
    run_id: str | None = None
    trade_date: str | None = None
    top_n: int = 20
    bottom_n: int = 0
    long_short: bool = False
    quantity: int = 100
    publish_stream: bool = False
    allow_shadow_stream: bool = False
    metadata: dict[str, Any] | None = None


class FactorCampaignCreateRequest(BaseModel):
    name: str | None = None
    strategy: str = "template_mutation"
    seed_expression: str | None = None
    seed_expressions: list[str] = []
    n_candidates: int = 5
    max_generations: int = 1
    run_async: bool = False
    universe: str = "hs300"
    start_date: str
    end_date: str
    n_groups: int = 5
    holding_period: int = 5
    neutralize_industry: bool = True
    neutralize_cap: bool = True
    validation_profile: str = "campaign"
    worker_policy: dict[str, Any] | None = None
    retry_policy: dict[str, Any] | None = None
    execution_lease: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class FactorValueBackfillCreateRequest(BaseModel):
    run_ids: list[str] = []
    candidate_ids: list[str] = []
    promotion_ids: list[str] = []
    start_date: str | None = None
    end_date: str | None = None
    universe: str | None = None
    holding_period: int | None = None
    dry_run: bool = False
    max_runs: int = 50
    metadata: dict[str, Any] | None = None


class FactorTrainingLaunchRequest(BaseModel):
    display_name: str | None = None
    train_start: str | None = None
    train_end: str | None = None
    valid_start: str | None = None
    valid_end: str | None = None
    test_start: str | None = None
    test_end: str | None = None
    target_horizon_days: int | None = None
    target_mode: str = "return"
    label_formula: str | None = None
    num_boost_round: int | None = None
    early_stopping_rounds: int | None = None
    context: dict[str, Any] | None = None
    lgb_params: dict[str, Any] | None = None
    baseline_training_run_id: str | None = None
    baseline_metrics: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class FactorTrainingApproveRequest(BaseModel):
    set_default_model: bool = False
    approve_default_model: bool = False
    reason: str | None = None
    metadata: dict[str, Any] | None = None


class FactorTrainingApprovalRequestCreateRequest(BaseModel):
    reason: str | None = None
    metadata: dict[str, Any] | None = None


class FactorTrainingApprovalRequestReviewRequest(BaseModel):
    approve: bool = True
    decision: str | None = None
    reason: str | None = None
    reviewer_note: str | None = None
    metadata: dict[str, Any] | None = None


class FactorApprovalPolicyUpdateRequest(BaseModel):
    enabled: bool | None = None
    allow_direct_approval: bool | None = None
    allow_self_approval: bool | None = None
    min_approvals: int | None = None
    reviewer_permission: str | None = None
    metadata: dict[str, Any] | None = None
