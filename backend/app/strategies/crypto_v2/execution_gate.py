from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.strategies.crypto_v2.calibration import clamp
from app.strategies.crypto_v2.spec import (
    CryptoAssetSnapshot,
    CryptoMarketSpec,
    ExecutionDecision,
    PredictionOrderBookSnapshot,
    ProbabilityEstimate,
    Side,
)


@dataclass(frozen=True)
class ExecutionGateConfig:
    max_spread_ct: float = 0.04
    orderbook_seconds: int = 15
    market_snapshot_seconds: int = 300
    spot_seconds: int = 30
    depth_multiplier: float = 1.5
    min_parser_confidence: float = 0.85
    touch_min_parser_confidence: float = 0.90
    min_quality_score: float = 70
    touch_min_quality_score: float = 75
    min_hours_to_close: float = 2
    max_days_to_close: float = 21
    min_trade_price: float = 0.03
    max_trade_price: float = 0.97
    min_exec_edge: float = 0.06
    min_stress_edge: float = 0.025
    touch_min_exec_edge: float = 0.08
    touch_min_stress_edge: float = 0.04
    uncertainty_penalty_multiplier: float = 1.0


def evaluate_execution_gate(
    *,
    spec: CryptoMarketSpec,
    asset_snapshot: CryptoAssetSnapshot,
    orderbook: PredictionOrderBookSnapshot,
    estimate: ProbabilityEstimate,
    side: Side,
    market_quality_score: Decimal,
    now: datetime,
    intended_notional: Decimal = Decimal("0"),
    config: ExecutionGateConfig = ExecutionGateConfig(),
) -> ExecutionDecision:
    risk_flags: list[str] = []
    reason_codes: list[str] = []
    executable_price = orderbook.best_ask
    p_trade = estimate.p_calibrated if side == "YES" else 1.0 - estimate.p_calibrated
    p_stress = _stress_probability(estimate, side)
    price_float = float(executable_price) if executable_price is not None else None
    market_mid = float(orderbook.mid) if orderbook.mid is not None else None
    edge_mid = p_trade - market_mid if market_mid is not None else None
    edge_exec = p_trade - price_float if price_float is not None else -1.0
    edge_stress = p_stress - price_float if price_float is not None else -1.0
    required = required_edge(
        float(orderbook.spread or 0),
        spec.market_type,
        (spec.window_end - now).total_seconds() / 3600,
        estimate.uncertainty_penalty * config.uncertainty_penalty_multiplier,
    )
    configured_min_edge = config.touch_min_exec_edge if spec.market_type.startswith("hit_") else config.min_exec_edge
    required = max(required, configured_min_edge)

    if spec.protocol.upper() != "POLYMARKET":
        risk_flags.append("VENUE_NOT_POLYMARKET")
    parser_min = (
        config.touch_min_parser_confidence
        if spec.market_type.startswith("hit_")
        else config.min_parser_confidence
    )
    if spec.parser_confidence < parser_min:
        risk_flags.append("PARSER_CONFIDENCE_LOW")
    if spec.has_blocking_ambiguity:
        risk_flags.append("BLOCKING_AMBIGUITY")
    if executable_price is None:
        risk_flags.append("NO_EXECUTABLE_ASK")
    elif not config.min_trade_price <= float(executable_price) <= config.max_trade_price:
        risk_flags.append("EXTREME_PRICE")
    if orderbook.best_bid is None:
        risk_flags.append("NO_BEST_BID")
    if orderbook.spread is None or float(orderbook.spread) > config.max_spread_ct:
        risk_flags.append("SPREAD_TOO_WIDE")
    if _age_seconds(asset_snapshot.ts, now) > config.spot_seconds:
        risk_flags.append("SPOT_DATA_STALE")
    if _age_seconds(orderbook.ts, now) > _orderbook_freshness_seconds(orderbook, config):
        risk_flags.append("ORDERBOOK_STALE")
    min_quality = config.touch_min_quality_score if spec.market_type.startswith("hit_") else config.min_quality_score
    if float(market_quality_score) < min_quality:
        risk_flags.append("MARKET_QUALITY_BELOW_GATE")
    horizon_hours = (spec.window_end - now).total_seconds() / 3600
    if horizon_hours < config.min_hours_to_close:
        risk_flags.append("CLOSES_TOO_SOON")
    if horizon_hours > config.max_days_to_close * 24:
        risk_flags.append("CLOSES_TOO_LATE")
    if intended_notional > 0 and _depth(orderbook) < intended_notional * Decimal(str(config.depth_multiplier)):
        risk_flags.append("INSUFFICIENT_DEPTH")
    if edge_exec < required:
        risk_flags.append("EDGE_BELOW_REQUIRED")
    stress_min = config.touch_min_stress_edge if spec.market_type.startswith("hit_") else config.min_stress_edge
    if edge_stress < stress_min:
        risk_flags.append("STRESS_EDGE_BELOW_REQUIRED")

    allowed = not risk_flags
    reason_codes.append("EXECUTION_GATE_PASSED" if allowed else "EXECUTION_GATE_BLOCKED")
    return ExecutionDecision(
        allowed=allowed,
        side=side,
        executable_price=executable_price,
        market_mid=market_mid,
        edge_mid=edge_mid,
        edge_exec=edge_exec,
        edge_stress=edge_stress,
        required_edge=required,
        p_trade=p_trade,
        p_stress=p_stress,
        reason_codes=reason_codes,
        risk_flags=risk_flags,
    )


def required_edge(
    spread: float,
    market_type: str,
    horizon_hours: float,
    uncertainty_penalty: float,
) -> float:
    base = 0.04
    if market_type in {"hit_above", "hit_below"}:
        base += 0.02
    if horizon_hours < 6:
        base += 0.015
    if spread > 0.03:
        base += 0.5 * spread
    return clamp(base + uncertainty_penalty, 0.05, 0.14)


def _stress_probability(estimate: ProbabilityEstimate, side: Side) -> float:
    candidates = [estimate.p_low, estimate.p_calibrated, estimate.p_high]
    if side == "YES":
        return min(candidates)
    return min(1.0 - candidate for candidate in candidates)


def _depth(orderbook: PredictionOrderBookSnapshot) -> Decimal:
    return orderbook.best_ask_size or orderbook.depth_to_100_usd or Decimal("0")


def _orderbook_freshness_seconds(
    orderbook: PredictionOrderBookSnapshot,
    config: ExecutionGateConfig,
) -> int:
    if orderbook.source == "market_snapshot":
        return max(config.orderbook_seconds, config.market_snapshot_seconds)
    return config.orderbook_seconds


def _age_seconds(ts: datetime, now: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=now.tzinfo)
    return max((now - ts).total_seconds(), 0.0)
