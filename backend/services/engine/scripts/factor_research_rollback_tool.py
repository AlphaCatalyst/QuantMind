from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class RollbackToolFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class RollbackToolConfig:
    base_url: str
    token: str | None
    tenant_id: str
    username: str | None
    password: str | None
    promotion_id: str | None
    latest_active: bool
    reason: str
    execute: bool
    force: bool
    timeout_seconds: float


@dataclass(frozen=True)
class RollbackToolResult:
    status: str
    base_url: str
    auth_source: str
    promotion_id: str
    execute: bool
    reason: str
    feature_key: str | None
    before_status: str | None
    before_materialization_status: str | None
    before_version_id: str | None
    after_status: str | None
    after_materialization_status: str | None
    rollback_version_id: str | None
    message: str
    steps: list[str]


def _unwrap_api_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _json_response(response: httpx.Response, *, step: str) -> Any:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RollbackToolFailure(f"{step} returned non-JSON response") from exc
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise RollbackToolFailure(f"{step} failed: HTTP {response.status_code}: {detail}")
    return payload


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    token: str | None = None,
    step: str,
    json_body: dict[str, Any] | None = None,
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await client.request(method, path, json=json_body, headers=headers)
    return _json_response(response, step=step)


async def _authenticate(
    client: httpx.AsyncClient,
    config: RollbackToolConfig,
) -> tuple[str, str]:
    if config.token:
        return config.token, "provided_token"
    if not config.username or not config.password:
        raise RollbackToolFailure(
            "rollback requires --token or --username/--password for the owner account"
        )
    payload = {
        "tenant_id": config.tenant_id,
        "username": config.username,
        "password": config.password,
    }
    auth_payload = await _request_json(
        client,
        "POST",
        "/api/v1/auth/login",
        step="login",
        json_body=payload,
    )
    token = str(auth_payload.get("access_token") or "").strip()
    if not token:
        raise RollbackToolFailure("login response did not include access_token")
    return token, "login"


def _promotion_rollback_version_id(promotion: dict[str, Any] | None) -> str | None:
    if not promotion:
        return None
    metadata = promotion.get("metadata")
    if not isinstance(metadata, dict):
        return None
    rollback = metadata.get("rollback")
    if not isinstance(rollback, dict):
        return None
    value = rollback.get("rollback_version_id")
    return str(value) if value is not None else None


def _is_active_or_materialized(promotion: dict[str, Any]) -> bool:
    status = str(promotion.get("status") or "").lower()
    materialization_status = str(
        promotion.get("materializationStatus") or ""
    ).lower()
    return status in {"materialized", "active"} or materialization_status in {
        "materialized",
        "active",
    }


def _select_promotion(
    promotions: list[dict[str, Any]],
    *,
    promotion_id: str | None,
    latest_active: bool,
) -> dict[str, Any]:
    if promotion_id:
        for promotion in promotions:
            if str(promotion.get("id")) == promotion_id:
                return promotion
        raise RollbackToolFailure(f"promotion not found in current user scope: {promotion_id}")

    if latest_active:
        for promotion in promotions:
            if _is_active_or_materialized(promotion):
                return promotion
        raise RollbackToolFailure("no active/materialized promotion found")

    raise RollbackToolFailure("provide --promotion-id or --latest-active")


async def run_rollback_tool(
    config: RollbackToolConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> RollbackToolResult:
    owns_client = client is None
    steps: list[str] = []
    if client is None:
        client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout_seconds),
        )

    try:
        health = await client.get("/health")
        if health.status_code >= 400:
            raise RollbackToolFailure(f"health failed: HTTP {health.status_code}")
        steps.append("health")

        token, auth_source = await _authenticate(client, config)
        steps.append(auth_source)

        promotions_payload = await _request_json(
            client,
            "GET",
            "/api/v1/research/factors/promotions?limit=200&offset=0",
            token=token,
            step="list_promotions",
        )
        promotions_data = _unwrap_api_data(promotions_payload)
        promotions = promotions_data.get("items") if isinstance(promotions_data, dict) else []
        if not isinstance(promotions, list):
            raise RollbackToolFailure("list_promotions response did not include items")
        promotion = _select_promotion(
            promotions,
            promotion_id=config.promotion_id,
            latest_active=config.latest_active,
        )
        steps.append("select_promotion")

        promotion_id = str(promotion.get("id"))
        before_status = promotion.get("status")
        before_materialization_status = promotion.get("materializationStatus")
        before_version_id = promotion.get("versionId")
        feature_key = promotion.get("featureKey")

        if str(before_status or "").lower() == "rolled_back" and not config.force:
            return RollbackToolResult(
                status="skipped",
                base_url=config.base_url,
                auth_source=auth_source,
                promotion_id=promotion_id,
                execute=config.execute,
                reason=config.reason,
                feature_key=str(feature_key) if feature_key is not None else None,
                before_status=str(before_status) if before_status is not None else None,
                before_materialization_status=str(before_materialization_status)
                if before_materialization_status is not None
                else None,
                before_version_id=str(before_version_id)
                if before_version_id is not None
                else None,
                after_status=str(before_status) if before_status is not None else None,
                after_materialization_status=str(before_materialization_status)
                if before_materialization_status is not None
                else None,
                rollback_version_id=_promotion_rollback_version_id(promotion),
                message="promotion already rolled back; use --force to replay rollback",
                steps=steps,
            )

        if not config.execute:
            return RollbackToolResult(
                status="dry_run",
                base_url=config.base_url,
                auth_source=auth_source,
                promotion_id=promotion_id,
                execute=False,
                reason=config.reason,
                feature_key=str(feature_key) if feature_key is not None else None,
                before_status=str(before_status) if before_status is not None else None,
                before_materialization_status=str(before_materialization_status)
                if before_materialization_status is not None
                else None,
                before_version_id=str(before_version_id)
                if before_version_id is not None
                else None,
                after_status=None,
                after_materialization_status=None,
                rollback_version_id=None,
                message="dry-run only; rerun with --execute to rollback this promotion",
                steps=steps,
            )

        rollback_payload = await _request_json(
            client,
            "POST",
            f"/api/v1/research/factors/promotions/{promotion_id}/rollback",
            token=token,
            step="rollback_promotion",
            json_body={"reason": config.reason},
        )
        rollback_data = _unwrap_api_data(rollback_payload)
        rolled_back = (
            rollback_data.get("promotion")
            if isinstance(rollback_data, dict)
            else None
        )
        if not isinstance(rolled_back, dict):
            raise RollbackToolFailure("rollback response did not include promotion")
        steps.append("rollback_promotion")

        after_status = str(rolled_back.get("status") or "")
        after_materialization_status = str(
            rolled_back.get("materializationStatus") or ""
        )
        if after_status != "rolled_back" or after_materialization_status != "rolled_back":
            raise RollbackToolFailure(
                "rollback did not return rolled_back status: "
                f"status={after_status}, materializationStatus="
                f"{after_materialization_status}"
            )

        return RollbackToolResult(
            status="rolled_back",
            base_url=config.base_url,
            auth_source=auth_source,
            promotion_id=promotion_id,
            execute=True,
            reason=config.reason,
            feature_key=str(feature_key) if feature_key is not None else None,
            before_status=str(before_status) if before_status is not None else None,
            before_materialization_status=str(before_materialization_status)
            if before_materialization_status is not None
            else None,
            before_version_id=str(before_version_id)
            if before_version_id is not None
            else None,
            after_status=after_status,
            after_materialization_status=after_materialization_status,
            rollback_version_id=_promotion_rollback_version_id(rolled_back),
            message="promotion rollback completed and verified",
            steps=steps,
        )
    finally:
        if owns_client:
            await client.aclose()


def _parse_args(argv: list[str] | None = None) -> RollbackToolConfig:
    parser = argparse.ArgumentParser(
        description="Dry-run or execute a QuantMind factor promotion rollback.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--promotion-id")
    parser.add_argument(
        "--latest-active",
        action="store_true",
        help="Rollback the latest active/materialized promotion in the owner scope.",
    )
    parser.add_argument("--reason", default="ops_factor_research_rollback")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually call the rollback API. Omit for dry-run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replay rollback even when the promotion already reports rolled_back.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args(argv)
    return RollbackToolConfig(
        base_url=args.base_url,
        token=args.token,
        tenant_id=args.tenant_id,
        username=args.username,
        password=args.password,
        promotion_id=args.promotion_id,
        latest_active=bool(args.latest_active),
        reason=args.reason,
        execute=bool(args.execute),
        force=bool(args.force),
        timeout_seconds=args.timeout_seconds,
    )


async def _amain(argv: list[str] | None = None) -> int:
    config = _parse_args(argv)
    try:
        result = await run_rollback_tool(config)
    except RollbackToolFailure as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
