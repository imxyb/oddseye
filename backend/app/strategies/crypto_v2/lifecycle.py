from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.strategies.crypto_v2.spec import LifecycleDecision


@dataclass(frozen=True)
class PositionState:
    side: str
    quantity: Decimal
    avg_price: Decimal
    mark_price: Decimal | None
    opened_probability: float | None
    last_buy_at: datetime | None


def decide_lifecycle_action(
    *,
    current_position: PositionState | None,
    target_side: str,
    edge_exec: float,
    edge_stress: float,
    required_edge: float,
    p_trade: float,
    p_entry: float | None,
    executable_buy_price: Decimal | None,
    exit_bid: Decimal | None,
    now: datetime,
    window_end: datetime,
    daily_loss_limit_triggered: bool = False,
    hold_required_edge: float = 0.01,
    exit_when_stress_edge_below: float = -0.01,
    max_probability_deterioration: float = 0.12,
    take_profit_price: Decimal = Decimal("0.85"),
    take_profit_trim_pct: float = 0.50,
    hard_exit_minutes_before_close: int = 20,
) -> LifecycleDecision:
    if daily_loss_limit_triggered:
        return LifecycleDecision(
            action="BLOCKED",
            side=None,
            reason_codes=[],
            risk_flags=["DAILY_LOSS_LIMIT_TRIGGERED"],
        )
    if current_position is None:
        if edge_exec >= required_edge and edge_stress >= 0 and executable_buy_price is not None:
            return LifecycleDecision(
                action="BUY",
                side=target_side,
                reason_codes=["OPEN_EDGE_SUFFICIENT"],
                risk_flags=[],
            )
        return LifecycleDecision(
            action="OBSERVE",
            side=None,
            reason_codes=["NO_POSITION_EDGE_BELOW_BUY"],
            risk_flags=[],
        )
    if current_position.side != target_side:
        return LifecycleDecision(
            action="EXIT",
            side=current_position.side,
            reason_codes=["EXIT_OPPOSING_MODEL_EDGE"],
            risk_flags=[],
        )
    if edge_stress < exit_when_stress_edge_below:
        return LifecycleDecision(
            action="EXIT",
            side=current_position.side,
            reason_codes=["EDGE_STRESS_REVERSED"],
            risk_flags=[],
        )
    entry_probability = p_entry if p_entry is not None else current_position.opened_probability
    if entry_probability is not None and entry_probability - p_trade > max_probability_deterioration:
        return LifecycleDecision(
            action="EXIT",
            side=current_position.side,
            reason_codes=["PROBABILITY_DETERIORATED"],
            risk_flags=[],
        )
    minutes_to_close = (window_end - now).total_seconds() / 60
    if minutes_to_close < hard_exit_minutes_before_close and p_trade - float(exit_bid or 0) <= hold_required_edge:
        return LifecycleDecision(
            action="EXIT",
            side=current_position.side,
            reason_codes=["HARD_EXIT_BEFORE_CLOSE"],
            risk_flags=[],
        )
    if (
        current_position.mark_price is not None
        and current_position.mark_price >= take_profit_price
        and p_trade < 0.95
    ):
        return LifecycleDecision(
            action="REDUCE",
            side=current_position.side,
            reason_codes=["TAKE_PROFIT_TRIM"],
            risk_flags=[],
            reduce_fraction=take_profit_trim_pct,
        )
    if exit_bid is not None and p_trade - float(exit_bid) > hold_required_edge:
        return LifecycleDecision(
            action="HOLD",
            side=current_position.side,
            reason_codes=["HOLD_POSITIVE_EV"],
            risk_flags=[],
        )
    return LifecycleDecision(
        action="HOLD",
        side=current_position.side,
        reason_codes=["HOLD_NO_EXIT_TRIGGER"],
        risk_flags=[],
    )
