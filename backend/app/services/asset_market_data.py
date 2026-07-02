from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

import httpx


@dataclass(frozen=True)
class AssetMarketData:
    asset: str
    current_price: Decimal
    annualized_volatility: Decimal
    source: str
    ts: datetime | None = None
    spot_bid: Decimal | None = None
    spot_ask: Decimal | None = None
    spot_mid: Decimal | None = None
    realized_vol_1d: float | None = None
    realized_vol_3d: float | None = None
    realized_vol_7d: float | None = None
    realized_vol_30d: float | None = None
    realized_vol_90d: float | None = None
    momentum_24h: float | None = None


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
        book_response = await self.http_client.get(
            f"{self.base_url}/api/v3/ticker/bookTicker",
            params={"symbol": symbol},
        )
        book_response.raise_for_status()
        book = book_response.json()
        spot_bid = Decimal(str(book["bidPrice"]))
        spot_ask = Decimal(str(book["askPrice"]))
        current_price = ((spot_bid + spot_ask) / Decimal("2")).quantize(Decimal("0.000001"))

        hourly_response = await self.http_client.get(
            f"{self.base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": "1h", "limit": 168},
        )
        hourly_response.raise_for_status()
        hourly_closes = [Decimal(str(row[4])) for row in hourly_response.json()]

        daily_response = await self.http_client.get(
            f"{self.base_url}/api/v3/klines",
            params={"symbol": symbol, "interval": "1d", "limit": 91},
        )
        daily_response.raise_for_status()
        daily_closes = [Decimal(str(row[4])) for row in daily_response.json()]

        ticker_response = await self.http_client.get(
            f"{self.base_url}/api/v3/ticker/24hr",
            params={"symbol": symbol},
        )
        ticker_response.raise_for_status()
        ticker = ticker_response.json()
        realized_vol_7d = _realized_volatility(hourly_closes, periods_per_year=8760)
        realized_vol_30d = _realized_volatility(daily_closes[-31:], periods_per_year=365)
        realized_vol_90d = _realized_volatility(daily_closes, periods_per_year=365)
        return AssetMarketData(
            asset=asset.upper(),
            current_price=current_price,
            annualized_volatility=Decimal(str(realized_vol_30d)).quantize(Decimal("0.000001")),
            source=f"binance:{symbol}",
            spot_bid=spot_bid,
            spot_ask=spot_ask,
            spot_mid=current_price,
            realized_vol_7d=realized_vol_7d,
            realized_vol_30d=realized_vol_30d,
            realized_vol_90d=realized_vol_90d,
            momentum_24h=float(ticker.get("priceChangePercent", 0)) / 100,
        )

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()


def annualized_volatility(closes: list[Decimal]) -> Decimal:
    return Decimal(str(_realized_volatility(closes, periods_per_year=365))).quantize(Decimal("0.000001"))


def _realized_volatility(closes: list[Decimal], periods_per_year: int) -> float:
    returns = [
        math.log(float(closes[index] / closes[index - 1]))
        for index in range(1, len(closes))
        if closes[index - 1] > 0 and closes[index] > 0
    ]
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns) * math.sqrt(periods_per_year)


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
