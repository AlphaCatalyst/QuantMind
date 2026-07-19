from __future__ import annotations

import json
import os
import random
import time
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


class TushareError(RuntimeError):
    """A redacted Tushare transport or contract error."""


@dataclass(frozen=True)
class TushareResponse:
    api_name: str
    fields: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


class TushareClient:
    """Minimal Tushare Pro client; credentials never enter observable state."""

    endpoint = "https://api.tushare.pro"

    def __init__(
        self,
        *,
        token: str | None = None,
        minimum_interval_seconds: float = 0.13,
        maximum_attempts: int = 5,
        timeout_seconds: float = 45.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        resolved = token if token is not None else os.environ.get("TUSHARE_TOKEN")
        if not resolved:
            raise TushareError("TUSHARE_TOKEN is not present")
        self.__token = resolved
        self.minimum_interval_seconds = max(0.0, minimum_interval_seconds)
        self.maximum_attempts = maximum_attempts
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen
        self._last_request = 0.0
        self._rate_lock = threading.Lock()

    @property
    def credential_present(self) -> bool:
        return True

    def query(self, api_name: str, *, fields: tuple[str, ...], **params: Any) -> TushareResponse:
        if not api_name or not fields:
            raise ValueError("api_name and fields are required")
        body = json.dumps(
            {"api_name": api_name, "token": self.__token, "params": params, "fields": ",".join(fields)},
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(1, self.maximum_attempts + 1):
            with self._rate_lock:
                delay = self.minimum_interval_seconds - (time.monotonic() - self._last_request)
                if delay > 0:
                    time.sleep(delay)
                self._last_request = time.monotonic()
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    payload = json.loads(response.read().decode("utf-8"))
                if status != 200:
                    raise urllib.error.HTTPError(self.endpoint, status, "Tushare HTTP failure", {}, None)
                return self._parse(api_name, fields, payload)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code == 429 or exc.code >= 500
                if not retryable or attempt == self.maximum_attempts:
                    raise TushareError(f"{api_name} transport failed after {attempt} attempt(s)") from exc
                time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))) + random.random() * 0.1)
        raise AssertionError("unreachable")

    @staticmethod
    def _parse(api_name: str, requested_fields: tuple[str, ...], payload: Any) -> TushareResponse:
        if not isinstance(payload, dict) or payload.get("code") != 0:
            # Never reproduce upstream messages: they can carry request details.
            raise TushareError(f"{api_name} permission or parameter error")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("fields"), list) or not isinstance(data.get("items"), list):
            raise TushareError(f"{api_name} response schema is invalid")
        actual = tuple(str(item) for item in data["fields"])
        if not set(requested_fields).issubset(actual):
            raise TushareError(f"{api_name} response omitted required fields")
        rows: list[dict[str, Any]] = []
        for item in data["items"]:
            if not isinstance(item, list) or len(item) != len(actual):
                raise TushareError(f"{api_name} response row schema is invalid")
            rows.append(dict(zip(actual, item)))
        return TushareResponse(api_name, actual, tuple(rows))
