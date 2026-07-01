from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class StrategySignal:
    market_id: str
    strategy_code: str
    action: str
    side: str | None
    model_probability: Decimal | None
    executable_price: Decimal | None
    edge: Decimal | None
    confidence: Decimal
    suggested_notional: Decimal | None
    market_quality_score: Decimal
    reason_codes: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    snapshot_id: int | None = None

