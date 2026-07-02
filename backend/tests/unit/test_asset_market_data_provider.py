from __future__ import annotations

import httpx
import pytest

from app.services.asset_market_data import BinanceAssetMarketDataProvider


@pytest.mark.asyncio
async def test_binance_provider_returns_v2_snapshot_fields() -> None:
    seen_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        params = dict(request.url.params)
        if request.url.path == "/api/v3/ticker/bookTicker":
            assert params["symbol"] == "BTCUSDT"
            return httpx.Response(200, json={"bidPrice": "107999", "askPrice": "108001"})
        if request.url.path == "/api/v3/klines" and params["interval"] == "1h":
            return httpx.Response(200, json=_klines(168, 100_000, step=10))
        if request.url.path == "/api/v3/klines" and params["interval"] == "1d":
            return httpx.Response(200, json=_klines(91, 100_000, step=100))
        if request.url.path == "/api/v3/ticker/24hr":
            return httpx.Response(200, json={"priceChangePercent": "1.5", "volume": "1000"})
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = BinanceAssetMarketDataProvider(
        base_url="https://data-api.binance.vision",
        http_client=http_client,
    )

    try:
        data = await provider.asset_market_data("BTC")
    finally:
        await provider.aclose()
        await http_client.aclose()

    assert data is not None
    assert data.asset == "BTC"
    assert data.current_price == data.spot_mid
    assert data.spot_bid is not None
    assert data.spot_ask is not None
    assert data.realized_vol_7d is not None
    assert data.realized_vol_30d is not None
    assert data.realized_vol_90d is not None
    assert data.momentum_24h == 0.015
    assert seen_paths.count("/api/v3/klines") == 2


def _klines(count: int, start: int, step: int) -> list[list[str]]:
    rows = []
    for index in range(count):
        close = start + index * step
        rows.append([0, "0", "0", "0", str(close), "0"])
    return rows
