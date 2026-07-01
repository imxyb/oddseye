from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from app.codex.client import CodexClient, UsageRecord


@dataclass
class MemoryUsageRecorder:
    records: list[UsageRecord] = field(default_factory=list)

    async def record(self, record: UsageRecord) -> None:
        self.records.append(record)


@pytest.mark.asyncio
async def test_codex_client_records_success_usage() -> None:
    recorder = MemoryUsageRecorder()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "secret"
        return httpx.Response(200, json={"data": {"ok": True}})

    client = CodexClient(
        endpoint="https://graph.codex.io/graphql",
        api_key="secret",
        usage_recorder=recorder,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    response: dict[str, Any] = await client.call("discovery", "query Test { ok }", {}, job_run_id="job-1")

    assert response == {"ok": True}
    assert len(recorder.records) == 1
    assert recorder.records[0].kind == "discovery"
    assert recorder.records[0].status == "success"
    assert recorder.records[0].request_count == 1
    assert recorder.records[0].job_run_id == "job-1"


@pytest.mark.asyncio
async def test_codex_client_records_failed_usage() -> None:
    recorder = MemoryUsageRecorder()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"errors": [{"message": "boom"}]})

    client = CodexClient(
        endpoint="https://graph.codex.io/graphql",
        api_key="secret",
        usage_recorder=recorder,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )

    with pytest.raises(RuntimeError):
        await client.call("bars", "query Test { ok }", {})

    assert len(recorder.records) == 1
    assert recorder.records[0].kind == "bars"
    assert recorder.records[0].status == "failed"
