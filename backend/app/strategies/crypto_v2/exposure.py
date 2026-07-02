from __future__ import annotations

from typing import Literal

from app.strategies.crypto_v2.spec import MarketType, Side

ExposureDirection = Literal["bullish", "bearish", "range_bound"]


def condition_direction(market_type: MarketType) -> ExposureDirection:
    if market_type in {"close_above", "hit_above"}:
        return "bullish"
    if market_type in {"close_below", "hit_below"}:
        return "bearish"
    return "range_bound"


def buy_exposure_direction(market_type: MarketType, side: Side) -> ExposureDirection:
    direction = condition_direction(market_type)
    if side == "YES" or direction == "range_bound":
        return direction
    return "bearish" if direction == "bullish" else "bullish"


def opposite_direction(direction: ExposureDirection) -> ExposureDirection | None:
    if direction == "bullish":
        return "bearish"
    if direction == "bearish":
        return "bullish"
    return None
