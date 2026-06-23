from __future__ import annotations

from typing import Any

import requests

from backend.services.engine.research.quantgpt_mapping import (
    parse_evaluation_payload,
    parse_factor_values_payload,
)
from backend.services.engine.research.schemas import (
    FactorValuesParseResult,
    QuantGPTEvaluation,
    QuantGPTEvaluationRequest,
)


class QuantGPTClient:
    """Narrow HTTP adapter for the QuantGPT sidecar."""

    def __init__(self, base_url: str, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/api/v1/health",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def submit_evaluation(self, request: QuantGPTEvaluationRequest) -> str:
        response = requests.post(
            f"{self.base_url}/api/v1/auto_backtest",
            json={
                "prompt": request.expression,
                "universe": request.universe,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "n_groups": request.n_groups,
                "holding_period": request.holding_period,
                "neutralize_industry": request.neutralize_industry,
                "neutralize_cap": request.neutralize_cap,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        task_id = payload.get("task_id")
        if not task_id:
            raise ValueError("QuantGPT auto_backtest response missing task_id")
        return str(task_id)

    def get_evaluation(self, task_id: str) -> QuantGPTEvaluation:
        response = requests.get(
            f"{self.base_url}/api/v1/tasks/{task_id}",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_evaluation_payload(response.json())

    def compute_factor_values(
        self,
        request: QuantGPTEvaluationRequest,
    ) -> FactorValuesParseResult:
        response = requests.post(
            f"{self.base_url}/api/v1/factor_values",
            json={
                "expression": request.expression,
                "universe": request.universe,
                "start_date": request.start_date,
                "end_date": request.end_date,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_factor_values_payload(response.json())
