from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.time import utcnow
from app.services.asset_market_data import AssetMarketData, AssetMarketDataProvider
from app.strategies.crypto_v2.spec import CryptoAssetSnapshot


class CryptoMarketDataService:
    def __init__(self, provider: AssetMarketDataProvider):
        self.provider = provider

    async def get_asset_snapshot(self, asset: str) -> CryptoAssetSnapshot | None:
        data = await self.provider.asset_market_data(asset)
        if data is None:
            return None
        if isinstance(data, AssetMarketData):
            return CryptoAssetSnapshot(
                asset=data.asset,
                ts=getattr(data, "ts", None) or utcnow(),
                source=data.source,
                spot=data.current_price,
                spot_bid=getattr(data, "spot_bid", None),
                spot_ask=getattr(data, "spot_ask", None),
                spot_mid=data.current_price,
                realized_vol_1d=getattr(data, "realized_vol_1d", None),
                realized_vol_3d=getattr(data, "realized_vol_3d", None),
                realized_vol_7d=getattr(data, "realized_vol_7d", None),
                realized_vol_30d=float(data.annualized_volatility),
                realized_vol_90d=getattr(data, "realized_vol_90d", None),
                ewma_vol=getattr(data, "ewma_vol", None),
                momentum_1h=getattr(data, "momentum_1h", None),
                momentum_4h=getattr(data, "momentum_4h", None),
                momentum_24h=getattr(data, "momentum_24h", None),
                momentum_7d=getattr(data, "momentum_7d", None),
                funding_rate=getattr(data, "funding_rate", None),
                funding_zscore=getattr(data, "funding_zscore", None),
                raw_json={},
            )
        return _snapshot_from_dict(asset, data)


def _snapshot_from_dict(asset: str, data: dict[str, Any]) -> CryptoAssetSnapshot:
    current_price = Decimal(str(data["current_price"]))
    ts = data.get("ts")
    if ts is None:
        ts = utcnow()
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    vol = _float_or_none(data.get("annualized_volatility"))
    return CryptoAssetSnapshot(
        asset=str(data.get("asset") or asset).upper(),
        ts=ts,
        source=str(data.get("source") or "asset_market_data"),
        spot=current_price,
        spot_bid=_decimal_or_none(data.get("spot_bid")),
        spot_ask=_decimal_or_none(data.get("spot_ask")),
        spot_mid=_decimal_or_none(data.get("spot_mid")) or current_price,
        realized_vol_1d=_float_or_none(data.get("realized_vol_1d")),
        realized_vol_3d=_float_or_none(data.get("realized_vol_3d")),
        realized_vol_7d=_float_or_none(data.get("realized_vol_7d")) or vol,
        realized_vol_30d=_float_or_none(data.get("realized_vol_30d")) or vol,
        realized_vol_90d=_float_or_none(data.get("realized_vol_90d")) or vol,
        ewma_vol=_float_or_none(data.get("ewma_vol")),
        momentum_1h=_float_or_none(data.get("momentum_1h")),
        momentum_4h=_float_or_none(data.get("momentum_4h")),
        momentum_24h=_float_or_none(data.get("momentum_24h")),
        momentum_7d=_float_or_none(data.get("momentum_7d")),
        funding_rate=_float_or_none(data.get("funding_rate")),
        funding_zscore=_float_or_none(data.get("funding_zscore")),
        raw_json=dict(data),
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)
