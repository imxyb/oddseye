from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.codex import queries
from app.core.time import utcnow

CODEX_MAX_FILTER_LIMIT = 200


@dataclass(frozen=True)
class UsageRecord:
    provider: str
    kind: str
    request_count: int
    status: str
    duration_ms: int
    job_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class UsageRecorder(Protocol):
    async def record(self, record: UsageRecord) -> None:
        ...


class NoopUsageRecorder:
    async def record(self, record: UsageRecord) -> None:
        return None


class CodexClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        usage_recorder: UsageRecorder | None = None,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.usage_recorder = usage_recorder or NoopUsageRecorder()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http_client = http_client is None

    async def call(
        self,
        kind: str,
        query: str,
        variables: dict[str, Any] | None,
        job_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = utcnow()
        status = "success"
        usage_metadata = {
            "query_size": len(query),
            "variable_keys": sorted((variables or {}).keys()),
            **(metadata or {}),
        }
        try:
            data = await self._post_with_retries(query, variables or {})
            return data
        except Exception:
            status = "failed"
            raise
        finally:
            duration_ms = int((utcnow() - started).total_seconds() * 1000)
            await self.usage_recorder.record(
                UsageRecord(
                    provider="codex",
                    kind=kind,
                    request_count=1,
                    status=status,
                    duration_ms=duration_ms,
                    job_run_id=job_run_id,
                    metadata=usage_metadata,
                )
            )

    async def prediction_categories(self, job_run_id: str | None = None) -> dict[str, Any]:
        return await self.call(
            "categories",
            queries.PREDICTION_CATEGORIES,
            {},
            job_run_id=job_run_id,
            metadata={"query_name": "PredictionCategories"},
        )

    async def discover_events(
        self,
        categories: list[str],
        limit: int = 100,
        offset: int = 0,
        job_run_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            "discovery",
            queries.DISCOVER_EVENTS,
            {"categories": categories, "limit": _codex_limit(limit), "offset": offset},
            job_run_id=job_run_id,
            metadata={"query_name": "DiscoverEvents", "category_count": len(categories)},
        )

    async def event_markets(
        self,
        event_ids: list[str],
        limit: int = 300,
        job_run_id: str | None = None,
        kind: str = "market_snapshot",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            kind,
            queries.EVENT_MARKETS,
            {"eventIds": event_ids, "limit": _codex_limit(limit)},
            job_run_id=job_run_id,
            metadata={
                "query_name": "EventMarkets",
                "market_count": len(event_ids),
                **(metadata or {}),
            },
        )

    async def market_bars(
        self,
        market_id: str,
        from_ts: int,
        to_ts: int,
        resolution: str,
        job_run_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            "bars",
            queries.MARKET_BARS,
            {"marketId": market_id, "from": from_ts, "to": to_ts, "resolution": resolution},
            job_run_id=job_run_id,
            metadata={"query_name": "PredictionMarketBars", "market_id": market_id},
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()

    async def _post_with_retries(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.http_client.post(
                    self.endpoint,
                    headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                    json={"query": query, "variables": variables},
                )
                if response.status_code >= 500:
                    raise RuntimeError(f"Codex server error {response.status_code}")
                if response.status_code >= 400:
                    raise RuntimeError(f"Codex request rejected {response.status_code}: {response.text}")
                payload = response.json()
                if payload.get("errors"):
                    raise RuntimeError(f"Codex GraphQL errors: {payload['errors']}")
                return payload.get("data", {})
            except (httpx.HTTPError, RuntimeError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
        raise RuntimeError("Codex request failed") from last_exc


def _codex_limit(limit: int) -> int:
    return min(limit, CODEX_MAX_FILTER_LIMIT)
