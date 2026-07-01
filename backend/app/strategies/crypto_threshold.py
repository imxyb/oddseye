from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.strategies.base import StrategySignal

ASSET_PATTERN = re.compile(r"\b(BTC|BITCOIN|ETH|ETHEREUM|SOL|SOLANA)\b", re.IGNORECASE)
THRESHOLD_PATTERN = re.compile(r"\$?\s*([0-9]{2,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)")


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
    if "BELOW" in upper or "UNDER" in upper:
        condition = "close_below"
    elif "HIT" in upper or "REACH" in upper:
        condition = "hit_above"
    else:
        condition = "close_above"
    threshold = Decimal(threshold_match.group(1).replace(",", ""))
    confidence = Decimal("0.86") if "$" in question or "," in threshold_match.group(1) else Decimal("0.78")
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
        yes_edge = p_model - context.yes_ask if context.yes_ask is not None else None
        no_edge = (Decimal("1") - p_model) - context.no_ask if context.no_ask is not None else None
        if risk_flags:
            return self._observe(context, confidence, reason_codes, risk_flags, p_model=p_model)
        if yes_edge is not None and yes_edge >= self.min_edge:
            reason_codes.extend(["MODEL_EDGE_POSITIVE", "BUY_YES_EDGE"])
            return StrategySignal(
                market_id=context.market_id,
                strategy_code=self.strategy_code,
                action="BUY",
                side="YES",
                model_probability=p_model,
                executable_price=context.yes_ask,
                edge=yes_edge.quantize(Decimal("0.000001")),
                confidence=confidence,
                suggested_notional=Decimal("100"),
                market_quality_score=context.market_quality_score,
                reason_codes=reason_codes,
                risk_flags=[],
                expires_at=context.now + timedelta(minutes=5),
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
                executable_price=context.no_ask,
                edge=no_edge.quantize(Decimal("0.000001")),
                confidence=confidence,
                suggested_notional=Decimal("100"),
                market_quality_score=context.market_quality_score,
                reason_codes=reason_codes,
                risk_flags=[],
                expires_at=context.now + timedelta(minutes=5),
                snapshot_id=context.snapshot_id,
            )
        reason_codes.append("EDGE_BELOW_THRESHOLD")
        return self._observe(context, confidence, reason_codes, risk_flags, p_model=p_model)

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
            expires_at=context.now + timedelta(minutes=5),
            snapshot_id=context.snapshot_id,
        )

