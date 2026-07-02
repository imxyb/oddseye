from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.strategies.crypto_v2.calibration import clamp

MONEY_Q = Decimal("0.000001")


@dataclass(frozen=True)
class SizingConfig:
    min_notional: Decimal = Decimal("5")
    default_paper_notional_cap: Decimal = Decimal("100")
    kelly_fraction: float = 0.20
    max_position_pct: float = 0.01


def suggested_notional(
    *,
    equity: Decimal,
    p: float,
    price: float,
    edge_stress: float,
    market_quality_score: float,
    parser_confidence: float,
    liquidity_multiplier: float,
    existing_exposure_multiplier: float,
    market_type: str,
    config: SizingConfig = SizingConfig(),
) -> Decimal:
    if equity <= 0 or price <= 0 or price >= 1 or edge_stress <= 0:
        return Decimal("0")
    b = (1 - price) / price
    q = 1 - p
    kelly_full = max(0.0, (b * p - q) / b)
    raw_fraction = kelly_full * config.kelly_fraction
    quality_mult = clamp((market_quality_score - 60) / 40, 0.0, 1.0)
    confidence_mult = clamp((parser_confidence - 0.80) / 0.20, 0.0, 1.0)
    if market_type in {"hit_above", "hit_below"}:
        type_mult = 0.60
    elif market_type == "range_close":
        type_mult = 0.75
    else:
        type_mult = 1.00
    fraction = raw_fraction
    fraction *= quality_mult
    fraction *= confidence_mult
    fraction *= clamp(liquidity_multiplier, 0.0, 1.0)
    fraction *= clamp(existing_exposure_multiplier, 0.0, 1.0)
    fraction *= type_mult
    fraction = clamp(fraction, 0.0, config.max_position_pct)
    notional = equity * Decimal(str(fraction))
    notional = min(notional, config.default_paper_notional_cap)
    if notional < config.min_notional:
        return Decimal("0")
    return notional.quantize(MONEY_Q)
