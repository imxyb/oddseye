from __future__ import annotations

import httpx
import pytest

from app.services.polymarket_metadata import PolymarketMarketMetadataClient


@pytest.mark.asyncio
async def test_fetches_clob_token_ids_by_condition_id() -> None:
    condition_id = "0xabc1234567"
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/markets"
        assert request.url.params["condition_ids"] == condition_id
        return httpx.Response(
            200,
            json=[
                {
                    "id": "gamma-market-1",
                    "conditionId": condition_id,
                    "outcomes": '["Yes", "No"]',
                    "clobTokenIds": '["yes-token", "no-token"]',
                }
            ],
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = PolymarketMarketMetadataClient(
        base_url="https://gamma-api.test",
        http_client=http_client,
    )

    try:
        tokens = await client.get_market_tokens(
            external_market_id=f"{condition_id}:Polymarket:0xdef:137",
            raw_json={},
        )
    finally:
        await client.aclose()
        await http_client.aclose()

    assert tokens is not None
    assert tokens.condition_id == condition_id
    assert tokens.token_ids == ["yes-token", "no-token"]
    assert tokens.raw_json["id"] == "gamma-market-1"
    assert len(requests) == 1
