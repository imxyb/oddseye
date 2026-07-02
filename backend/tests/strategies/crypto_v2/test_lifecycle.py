from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.strategies.crypto_v2.lifecycle import PositionState, decide_lifecycle_action


def test_buy_when_no_position_and_edge_sufficient() -> None:
    decision = decide_lifecycle_action(
        current_position=None,
        target_side="YES",
        edge_exec=0.10,
        edge_stress=0.05,
        required_edge=0.07,
        p_trade=0.62,
        p_entry=None,
        executable_buy_price=Decimal("0.52"),
        exit_bid=Decimal("0.49"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "BUY"
    assert decision.side == "YES"


def test_hold_when_position_still_positive_ev() -> None:
    decision = decide_lifecycle_action(
        current_position=_position("YES"),
        target_side="YES",
        edge_exec=0.04,
        edge_stress=0.02,
        required_edge=0.07,
        p_trade=0.62,
        p_entry=0.60,
        executable_buy_price=Decimal("0.56"),
        exit_bid=Decimal("0.58"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "HOLD"
    assert decision.side == "YES"


def test_exit_when_edge_reverses() -> None:
    decision = decide_lifecycle_action(
        current_position=_position("YES"),
        target_side="YES",
        edge_exec=-0.02,
        edge_stress=-0.02,
        required_edge=0.07,
        p_trade=0.45,
        p_entry=0.62,
        executable_buy_price=Decimal("0.55"),
        exit_bid=Decimal("0.50"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "EXIT"
    assert decision.side == "YES"
    assert "EDGE_STRESS_REVERSED" in decision.reason_codes


def test_existing_position_exits_even_when_no_entry_edge() -> None:
    decision = decide_lifecycle_action(
        current_position=_position("YES"),
        target_side="YES",
        edge_exec=-0.10,
        edge_stress=-0.10,
        required_edge=0.07,
        p_trade=0.45,
        p_entry=0.62,
        executable_buy_price=None,
        exit_bid=Decimal("0.50"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "EXIT"
    assert decision.side == "YES"


def test_exit_when_probability_deteriorates() -> None:
    decision = decide_lifecycle_action(
        current_position=_position("YES"),
        target_side="YES",
        edge_exec=0.02,
        edge_stress=0.01,
        required_edge=0.07,
        p_trade=0.47,
        p_entry=0.62,
        executable_buy_price=Decimal("0.55"),
        exit_bid=Decimal("0.50"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "EXIT"
    assert "PROBABILITY_DETERIORATED" in decision.reason_codes


def test_reduce_when_take_profit_triggered() -> None:
    decision = decide_lifecycle_action(
        current_position=_position("YES", mark_price=Decimal("0.88")),
        target_side="YES",
        edge_exec=0.03,
        edge_stress=0.02,
        required_edge=0.07,
        p_trade=0.90,
        p_entry=0.62,
        executable_buy_price=Decimal("0.90"),
        exit_bid=Decimal("0.86"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
    )

    assert decision.action == "REDUCE"
    assert decision.side == "YES"
    assert decision.reduce_fraction == 0.50


def test_block_when_daily_loss_limit_triggered() -> None:
    decision = decide_lifecycle_action(
        current_position=None,
        target_side="YES",
        edge_exec=0.12,
        edge_stress=0.06,
        required_edge=0.07,
        p_trade=0.65,
        p_entry=None,
        executable_buy_price=Decimal("0.52"),
        exit_bid=Decimal("0.49"),
        now=datetime(2026, 7, 1, tzinfo=UTC),
        window_end=datetime(2026, 7, 10, tzinfo=UTC),
        daily_loss_limit_triggered=True,
    )

    assert decision.action == "BLOCKED"
    assert "DAILY_LOSS_LIMIT_TRIGGERED" in decision.risk_flags


def _position(side: str, mark_price: Decimal = Decimal("0.60")) -> PositionState:
    return PositionState(
        side=side,
        quantity=Decimal("100"),
        avg_price=Decimal("0.50"),
        mark_price=mark_price,
        opened_probability=0.62,
        last_buy_at=datetime(2026, 7, 1, tzinfo=UTC) - timedelta(hours=1),
    )
