from __future__ import annotations

from datetime import datetime

from app.strategies.base import StrategySignal


def macro_v1_observe_only_signal(
    market_id: str,
    quality_score,
    *,
    snapshot_id: int | None = None,
    expires_at: datetime | None = None,
):
    return StrategySignal(
        market_id=market_id,
        strategy_code="macro_calendar_v1",
        action="OBSERVE",
        side=None,
        model_probability=None,
        executable_price=None,
        edge=None,
        confidence=quality_score,
        suggested_notional=None,
        market_quality_score=quality_score,
        reason_codes=["MACRO_V1_MANUAL_ONLY"],
        risk_flags=[],
        expires_at=expires_at,
        snapshot_id=snapshot_id,
    )
