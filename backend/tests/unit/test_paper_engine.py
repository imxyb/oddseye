from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.paper.engine import (
    PaperAccountState,
    PaperOrderRequest,
    PaperTradingEngine,
    SnapshotQuote,
)


def test_buy_yes_limit_fills_at_ask_with_slippage_and_updates_cash_position() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account = PaperAccountState(id=uuid4(), cash=Decimal("10000"), starting_cash=Decimal("10000"))
    market_id = uuid4()
    snapshot = SnapshotQuote(
        id=1,
        market_id=market_id,
        ts=datetime.now(timezone.utc),
        outcome0_best_bid=Decimal("0.55"),
        outcome0_best_ask=Decimal("0.57"),
        outcome1_best_bid=Decimal("0.41"),
        outcome1_best_ask=Decimal("0.43"),
    )
    order = PaperOrderRequest(
        account_id=account.id,
        market_id=market_id,
        side="BUY",
        outcome_index=0,
        limit_price=Decimal("0.58"),
        quantity=Decimal("100"),
    )

    result = engine.try_fill(account, order, snapshot)

    assert result is not None
    assert result.fill.price == Decimal("0.571425")
    assert result.fill.notional == Decimal("57.142500")
    assert result.account.cash == Decimal("9942.857500")
    assert result.position.quantity == Decimal("100")
    assert result.position.avg_price == Decimal("0.571425")
    assert result.position.mark_price == Decimal("0.55")
    assert result.position.unrealized_pnl == Decimal("-2.142500")


def test_sell_yes_limit_uses_bid_with_negative_slippage_and_realizes_pnl() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account_id = uuid4()
    market_id = uuid4()
    account = PaperAccountState(id=account_id, cash=Decimal("9942.857500"), starting_cash=Decimal("10000"))
    engine.open_position(
        account_id=account_id,
        market_id=market_id,
        outcome_index=0,
        quantity=Decimal("100"),
        avg_price=Decimal("0.571425"),
    )
    snapshot = SnapshotQuote(
        id=2,
        market_id=market_id,
        ts=datetime.now(timezone.utc),
        outcome0_best_bid=Decimal("0.62"),
        outcome0_best_ask=Decimal("0.64"),
        outcome1_best_bid=Decimal("0.36"),
        outcome1_best_ask=Decimal("0.38"),
    )
    order = PaperOrderRequest(
        account_id=account_id,
        market_id=market_id,
        side="SELL",
        outcome_index=0,
        limit_price=Decimal("0.61"),
        quantity=Decimal("100"),
    )

    result = engine.try_fill(account, order, snapshot)

    assert result is not None
    assert result.fill.price == Decimal("0.618450")
    assert result.account.cash == Decimal("10004.702500")
    assert result.position.quantity == Decimal("0")
    assert result.position.status == "closed"
    assert result.position.realized_pnl == Decimal("4.702500")


def test_order_does_not_fill_when_limit_is_not_executable() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account = PaperAccountState(id=uuid4(), cash=Decimal("10000"), starting_cash=Decimal("10000"))
    market_id = uuid4()

    result = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account.id,
            market_id=market_id,
            side="BUY",
            outcome_index=0,
            limit_price=Decimal("0.56"),
            quantity=Decimal("100"),
        ),
        SnapshotQuote(
            id=3,
            market_id=market_id,
            ts=datetime.now(timezone.utc),
            outcome0_best_bid=Decimal("0.55"),
            outcome0_best_ask=Decimal("0.57"),
            outcome1_best_bid=Decimal("0.41"),
            outcome1_best_ask=Decimal("0.43"),
        ),
    )

    assert result is None
    assert account.cash == Decimal("10000")


def test_buy_order_does_not_fill_if_slippage_breaks_limit() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account = PaperAccountState(id=uuid4(), cash=Decimal("10000"), starting_cash=Decimal("10000"))
    market_id = uuid4()

    result = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account.id,
            market_id=market_id,
            side="BUY",
            outcome_index=0,
            limit_price=Decimal("0.501"),
            quantity=Decimal("100"),
        ),
        SnapshotQuote(
            id=30,
            market_id=market_id,
            ts=datetime.now(timezone.utc),
            outcome0_best_bid=Decimal("0.49"),
            outcome0_best_ask=Decimal("0.50"),
            outcome1_best_bid=Decimal("0.49"),
            outcome1_best_ask=Decimal("0.50"),
        ),
    )

    assert result is None
    assert account.cash == Decimal("10000")


def test_sell_order_does_not_fill_if_slippage_breaks_limit() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account_id = uuid4()
    market_id = uuid4()
    account = PaperAccountState(id=account_id, cash=Decimal("9950"), starting_cash=Decimal("10000"))
    engine.open_position(
        account_id=account_id,
        market_id=market_id,
        outcome_index=0,
        quantity=Decimal("100"),
        avg_price=Decimal("0.50"),
    )

    result = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account_id,
            market_id=market_id,
            side="SELL",
            outcome_index=0,
            limit_price=Decimal("0.499"),
            quantity=Decimal("100"),
        ),
        SnapshotQuote(
            id=31,
            market_id=market_id,
            ts=datetime.now(timezone.utc),
            outcome0_best_bid=Decimal("0.50"),
            outcome0_best_ask=Decimal("0.51"),
            outcome1_best_bid=Decimal("0.49"),
            outcome1_best_ask=Decimal("0.50"),
        ),
    )

    assert result is None
    assert account.cash == Decimal("9950")


def test_sell_without_inventory_does_not_fill_or_credit_cash() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account = PaperAccountState(id=uuid4(), cash=Decimal("10000"), starting_cash=Decimal("10000"))
    market_id = uuid4()

    result = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account.id,
            market_id=market_id,
            side="SELL",
            outcome_index=0,
            limit_price=Decimal("0.40"),
            quantity=Decimal("100"),
        ),
        SnapshotQuote(
            id=4,
            market_id=market_id,
            ts=datetime.now(timezone.utc),
            outcome0_best_bid=Decimal("0.50"),
            outcome0_best_ask=Decimal("0.52"),
            outcome1_best_bid=Decimal("0.47"),
            outcome1_best_ask=Decimal("0.49"),
        ),
    )

    assert result is None
    assert account.cash == Decimal("10000")


def test_oversized_sell_does_not_fill_or_credit_cash() -> None:
    engine = PaperTradingEngine(slippage_bps=25, fee_bps=0)
    account_id = uuid4()
    market_id = uuid4()
    account = PaperAccountState(id=account_id, cash=Decimal("9950"), starting_cash=Decimal("10000"))
    engine.open_position(
        account_id=account_id,
        market_id=market_id,
        outcome_index=0,
        quantity=Decimal("10"),
        avg_price=Decimal("0.50"),
    )

    result = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account_id,
            market_id=market_id,
            side="SELL",
            outcome_index=0,
            limit_price=Decimal("0.40"),
            quantity=Decimal("11"),
        ),
        SnapshotQuote(
            id=5,
            market_id=market_id,
            ts=datetime.now(timezone.utc),
            outcome0_best_bid=Decimal("0.55"),
            outcome0_best_ask=Decimal("0.57"),
            outcome1_best_bid=Decimal("0.41"),
            outcome1_best_ask=Decimal("0.43"),
        ),
    )

    assert result is None
    assert account.cash == Decimal("9950")


def test_repeated_partial_sells_accumulate_realized_pnl() -> None:
    engine = PaperTradingEngine(slippage_bps=0, fee_bps=0)
    account_id = uuid4()
    market_id = uuid4()
    account = PaperAccountState(id=account_id, cash=Decimal("9950"), starting_cash=Decimal("10000"))
    engine.open_position(
        account_id=account_id,
        market_id=market_id,
        outcome_index=0,
        quantity=Decimal("100"),
        avg_price=Decimal("0.50"),
    )
    snapshot = SnapshotQuote(
        id=6,
        market_id=market_id,
        ts=datetime.now(timezone.utc),
        outcome0_best_bid=Decimal("0.60"),
        outcome0_best_ask=Decimal("0.62"),
        outcome1_best_bid=Decimal("0.38"),
        outcome1_best_ask=Decimal("0.40"),
    )

    first = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account_id,
            market_id=market_id,
            side="SELL",
            outcome_index=0,
            limit_price=Decimal("0.59"),
            quantity=Decimal("25"),
        ),
        snapshot,
    )
    second = engine.try_fill(
        account,
        PaperOrderRequest(
            account_id=account_id,
            market_id=market_id,
            side="SELL",
            outcome_index=0,
            limit_price=Decimal("0.59"),
            quantity=Decimal("25"),
        ),
        snapshot,
    )

    assert first is not None
    assert second is not None
    assert second.position.quantity == Decimal("50")
    assert second.position.realized_pnl == Decimal("5.000000")
