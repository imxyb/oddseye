from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx


@dataclass(frozen=True)
class AssetMarketData:
    asset: str
    current_price: Decimal
    annualized_volatility: Decimal
    source: str


class AssetMarketDataProvider(Protocol):
    async def asset_market_data(self, asset: str) -> AssetMarketData | dict | None:
        ...


class BinanceAssetMarketDataProvider:
    def __init__(
        self,
        base_url: str = "https://data-api.binance.vision",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_http_client = http_client is None

    async def asset_market_data(self, asset: str) -> AssetMarketData | None:
        symbol = _symbol_for_asset(asset)
        if symbol is None:
            return None
        price_response = await self.http_client.get(
            f"{self.base_url}/api/v3/avgPrice",
            params={"symbol": symbol},
        )
        price_response.raise_for_status()
        current_price = Decimal(str(price_response.json()["price"]))

        klines_response = await self.http_client.get(
            f"{self.base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": "1d", "limit": 31},
        )
        klines_response.raise_for_status()
        closes = [Decimal(str(row[4])) for row in klines_response.json()]
        return AssetMarketData(
            asset=asset.upper(),
            current_price=current_price,
            annualized_volatility=annualized_volatility(closes),
            source=f"binance:{symbol}",
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()


def annualized_volatility(closes: list[Decimal]) -> Decimal:
    returns = [
        math.log(float(closes[index] / closes[index - 1]))
        for index in range(1, len(closes))
        if closes[index - 1] > 0 and closes[index] > 0
    ]
    if len(returns) < 2:
        return Decimal("0")
    volatility = statistics.stdev(returns) * math.sqrt(365)
    return Decimal(str(volatility)).quantize(Decimal("0.000001"))


def _symbol_for_asset(asset: str) -> str | None:
    symbols = {
        "BTC": "BTCUSDT",
        "BITCOIN": "BTCUSDT",
        "ETH": "ETHUSDT",
        "ETHEREUM": "ETHUSDT",
        "SOL": "SOLUSDT",
        "SOLANA": "SOLUSDT",
    }
    return symbols.get(asset.upper())
