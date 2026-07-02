from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal


MarketType = Literal["close_above", "close_below", "hit_above", "hit_below", "range_close"]
Side = Literal["YES", "NO"]


BLOCKING_AMBIGUITY_FLAGS = {
    "NO_DEADLINE",
    "NO_THRESHOLD",
    "MULTI_ASSET_CONDITION",
    "NON_SPOT_METRIC",
    "UNCLEAR_RESOLUTION_SOURCE",
    "UNCLEAR_TIMEZONE",
    "ATH_REQUIRES_HISTORY",
    "MARKET_CAP_METRIC",
    "ETF_FLOW_METRIC",
    "FUNDING_RATE_METRIC",
    "NEG_RISK_MULTI_OUTCOME_UNSUPPORTED",
    "RANGE_TOUCH_UNSUPPORTED",
    "LLM_SEMANTIC_PARSE_UNAVAILABLE",
    "LLM_SEMANTIC_LOW_CONFIDENCE",
    "LLM_PARSE_CONFLICT",
}


@dataclass(frozen=True)
class CryptoMarketSpec:
    market_id: str
    event_id: str | None
    protocol: str
    question: str
    asset: Literal["BTC", "ETH", "SOL"]
    quote_currency: Literal["USD", "USDT"]
    metric: Literal["spot_price"]
    market_type: MarketType
    threshold: Decimal | None
    lower_threshold: Decimal | None
    upper_threshold: Decimal | None
    window_start: datetime | None
    window_end: datetime
    settlement_time: datetime | None
    settlement_timezone: str | None
    resolution_source: str | None
    parser_confidence: float
    ambiguity_flags: list[str]
    raw_parse: dict[str, Any]

    @property
    def has_blocking_ambiguity(self) -> bool:
        return bool(BLOCKING_AMBIGUITY_FLAGS.intersection(self.ambiguity_flags))


@dataclass(frozen=True)
class ParseResult:
    spec: CryptoMarketSpec | None
    ambiguity_flags: list[str] = field(default_factory=list)
    raw_parse: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.spec is None


@dataclass(frozen=True)
class CryptoAssetSnapshot:
    asset: str
    ts: datetime
    source: str
    spot: Decimal
    spot_bid: Decimal | None
    spot_ask: Decimal | None
    spot_mid: Decimal
    realized_vol_1d: float | None
    realized_vol_3d: float | None
    realized_vol_7d: float | None
    realized_vol_30d: float | None
    realized_vol_90d: float | None
    ewma_vol: float | None
    momentum_1h: float | None
    momentum_4h: float | None
    momentum_24h: float | None
    momentum_7d: float | None
    funding_rate: float | None
    funding_zscore: float | None
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class PredictionOrderBookSnapshot:
    market_id: str
    token_id: str | None
    outcome: Side
    ts: datetime
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    mid: Decimal | None
    best_bid_size: Decimal | None
    best_ask_size: Decimal | None
    depth_to_10_usd: Decimal | None
    depth_to_50_usd: Decimal | None
    depth_to_100_usd: Decimal | None
    tick_size: Decimal | None
    min_order_size: Decimal | None
    book_hash: str | None
    source: str
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class ProbabilityEstimate:
    p_raw: float
    p_calibrated: float
    p_low: float
    p_high: float
    model_family: str
    confidence: float
    uncertainty_penalty: float
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    side: Side
    executable_price: Decimal | None
    market_mid: float | None
    edge_mid: float | None
    edge_exec: float
    edge_stress: float
    required_edge: float
    p_trade: float
    p_stress: float
    reason_codes: list[str]
    risk_flags: list[str]


@dataclass(frozen=True)
class LifecycleDecision:
    action: str
    side: str | None
    reason_codes: list[str]
    risk_flags: list[str]
    reduce_fraction: float | None = None
