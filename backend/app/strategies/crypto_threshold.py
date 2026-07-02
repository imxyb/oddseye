from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.strategies.base import StrategySignal

ASSET_PATTERN = re.compile(r"\b(BTC|BITCOIN|ETH|ETHEREUM|SOL|SOLANA)\b", re.IGNORECASE)
THRESHOLD_PATTERN = re.compile(
    r"(?:\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)|"
    r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?)\s*(?:USD|USDT|DOLLARS?)?)",
    re.IGNORECASE,
)
# Keep signal visibility longer than the 5 minute worker cadence so commit time
# and an occasional slow run do not create an empty active-signal window.
SIGNAL_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class ParsedCryptoThreshold:
    asset: str
    condition_type: str
    threshold: Decimal
    confidence: Decimal


@dataclass(frozen=True)
class CryptoMarketContext:
    market_id: str
    question: str
    now: datetime
    deadline: datetime
    current_price: Decimal
    annualized_volatility: Decimal
    yes_ask: Decimal | None
    no_ask: Decimal | None
    market_quality_score: Decimal
    parser_confidence: Decimal
    snapshot_id: int | None = None


def normalize_asset(asset: str) -> str:
    upper = asset.upper()
    return {"BITCOIN": "BTC", "ETHEREUM": "ETH", "SOLANA": "SOL"}.get(upper, upper)


def parse_crypto_threshold(question: str) -> ParsedCryptoThreshold | None:
    asset_match = ASSET_PATTERN.search(question)
    threshold_match = THRESHOLD_PATTERN.search(question)
    if not asset_match or not threshold_match:
        return None
    upper = question.upper()
    if any(token in upper for token in ("BELOW", "UNDER", "DIP", "DROP", "FALL")):
        condition = "close_below"
    elif "HIT" in upper or "REACH" in upper or "TOUCH" in upper:
        condition = "hit_above"
    else:
        condition = "close_above"
    threshold_text = next(group for group in threshold_match.groups() if group)
    threshold = Decimal(threshold_text.replace(",", ""))
    confidence = Decimal("0.86")
    return ParsedCryptoThreshold(
        asset=normalize_asset(asset_match.group(1)),
        condition_type=condition,
        threshold=threshold,
        confidence=confidence,
    )


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def close_above_probability(
    current_price: Decimal,
    threshold: Decimal,
    deadline: datetime,
    now: datetime,
    annualized_volatility: Decimal,
    drift: Decimal = Decimal("0"),
) -> Decimal:
    seconds = max((deadline - now).total_seconds(), 1)
    years = Decimal(str(seconds)) / Decimal(str(365.25 * 24 * 60 * 60))
    sigma = max(float(annualized_volatility), 1e-9)
    t = float(years)
    numerator = math.log(float(threshold / current_price)) - (
        float(drift) - 0.5 * sigma * sigma
    ) * t
    z = numerator / (sigma * math.sqrt(t))
    return Decimal(str(1 - normal_cdf(z))).quantize(Decimal("0.000001"))


class CryptoThresholdStrategy:
    strategy_code = "crypto_threshold_v1"

    def __init__(self, min_edge: Decimal = Decimal("0.07")):
        self.min_edge = min_edge

    def evaluate(self, context: CryptoMarketContext) -> StrategySignal:
        parsed = parse_crypto_threshold(context.question)
        confidence = min(context.parser_confidence, parsed.confidence if parsed else Decimal("0"))
        risk_flags: list[str] = []
        reason_codes: list[str] = []
        if parsed is None:
            risk_flags.append("PARSER_FAILED")
            return self._observe(context, confidence, reason_codes, risk_flags)
        if parsed.condition_type == "hit_above":
            reason_codes.append("CRYPTO_THRESHOLD_TOUCH_MARKET_DETECTED")
            risk_flags.append("BARRIER_TOUCH_MODEL_NOT_IMPLEMENTED")
        if confidence < Decimal("0.75"):
            risk_flags.append("PARSER_CONFIDENCE_LOW")
        if context.market_quality_score < Decimal("65"):
            risk_flags.append("QUALITY_BELOW_GATE")
        if context.deadline <= context.now + timedelta(minutes=30):
            risk_flags.append("CLOSES_TOO_SOON")

        p_above = close_above_probability(
            current_price=context.current_price,
            threshold=parsed.threshold,
            deadline=context.deadline,
            now=context.now,
            annualized_volatility=context.annualized_volatility,
        )
        p_model = Decimal("1") - p_above if parsed.condition_type == "close_below" else p_above
        quote_risk_flags = _quote_risk_flags(context.yes_ask, context.no_ask)
        yes_ask = _tradable_price(context.yes_ask)
        no_ask = _tradable_price(context.no_ask)
        yes_edge = p_model - yes_ask if yes_ask is not None else None
        no_edge = (Decimal("1") - p_model) - no_ask if no_ask is not None else None
        if risk_flags:
            return self._observe(context, confidence, reason_codes, risk_flags + quote_risk_flags, p_model=p_model)
        if yes_edge is not None and yes_edge >= self.min_edge:
            reason_codes.extend(["MODEL_EDGE_POSITIVE", "BUY_YES_EDGE"])
            return StrategySignal(
                market_id=context.market_id,
                strategy_code=self.strategy_code,
                action="BUY",
                side="YES",
                model_probability=p_model,
                executable_price=yes_ask,
                edge=yes_edge.quantize(Decimal("0.000001")),
                confidence=confidence,
                suggested_notional=Decimal("100"),
                market_quality_score=context.market_quality_score,
                reason_codes=reason_codes,
                risk_flags=[],
                expires_at=context.now + SIGNAL_TTL,
                snapshot_id=context.snapshot_id,
            )
        if no_edge is not None and no_edge >= self.min_edge:
            reason_codes.extend(["MODEL_EDGE_POSITIVE", "BUY_NO_EDGE"])
            return StrategySignal(
                market_id=context.market_id,
                strategy_code=self.strategy_code,
                action="BUY",
                side="NO",
                model_probability=p_model,
                executable_price=no_ask,
                edge=no_edge.quantize(Decimal("0.000001")),
                confidence=confidence,
                suggested_notional=Decimal("100"),
                market_quality_score=context.market_quality_score,
                reason_codes=reason_codes,
                risk_flags=[],
                expires_at=context.now + SIGNAL_TTL,
                snapshot_id=context.snapshot_id,
            )
        reason_codes.append("EDGE_BELOW_THRESHOLD")
        return self._observe(context, confidence, reason_codes, risk_flags + quote_risk_flags, p_model=p_model)

    def _observe(
        self,
        context: CryptoMarketContext,
        confidence: Decimal,
        reason_codes: list[str],
        risk_flags: list[str],
        p_model: Decimal | None = None,
    ) -> StrategySignal:
        return StrategySignal(
            market_id=context.market_id,
            strategy_code=self.strategy_code,
            action="OBSERVE",
            side=None,
            model_probability=p_model,
            executable_price=None,
            edge=None,
            confidence=confidence,
            suggested_notional=None,
            market_quality_score=context.market_quality_score,
            reason_codes=reason_codes,
            risk_flags=risk_flags,
            expires_at=context.now + SIGNAL_TTL,
            snapshot_id=context.snapshot_id,
        )


def _tradable_price(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if Decimal("0") < value < Decimal("1"):
        return value
    return None


def _quote_risk_flags(yes_ask: Decimal | None, no_ask: Decimal | None) -> list[str]:
    risk_flags = []
    if yes_ask is not None and _tradable_price(yes_ask) is None:
        risk_flags.append("YES_ASK_OUT_OF_RANGE")
    if no_ask is not None and _tradable_price(no_ask) is None:
        risk_flags.append("NO_ASK_OUT_OF_RANGE")
    return risk_flags
