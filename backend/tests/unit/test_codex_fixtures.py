from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.codex.client import CodexClient

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "codex"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_documented_codex_fixtures_match_client_query_shapes() -> None:
    fixtures = {
        "events_crypto.json": await _client_response(
            "events_crypto.json",
            lambda client: client.discover_events(["crypto"], limit=1),
        ),
        "markets_btc.json": await _client_response(
            "markets_btc.json",
            lambda client: client.event_markets(["event-btc"], limit=1),
        ),
        "market_bars_btc.json": await _client_response(
            "market_bars_btc.json",
            lambda client: client.market_bars("market-btc-80000", 1, 2, "hour1"),
        ),
    }

    events = fixtures["events_crypto.json"]["filterPredictionEvents"]
    assert events["results"][0]["event"]["question"]
    assert events["results"][0]["markets"][0]["id"]

    markets = fixtures["markets_btc.json"]["filterPredictionMarkets"]
    assert markets["results"][0]["market"]["question"]
    assert markets["results"][0]["outcome0"]["bestAskCT"]
    assert markets["results"][0]["outcome1"]["bestBidCT"]

    bars = fixtures["market_bars_btc.json"]["predictionMarketBars"]
    assert bars["marketId"] == "market-btc-80000"
    assert bars["bars"][0]["outcome0"]["priceCollateralToken"]["c"]


async def _client_response(name: str, call):
    fixture = _load_fixture(name)

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture)

    client = CodexClient(
        endpoint="https://graph.codex.io/graphql",
        api_key="secret",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )
    try:
        return await call(client)
    finally:
        await client.aclose()
