from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import (
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.services.paper_trading import performance


@pytest.mark.asyncio
async def test_performance_equity_includes_open_position_mark_value(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'performance.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9942.8575"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=10),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="OPEN",
        )
        session.add(market)
        await session.flush()
        session.add(
            PaperPosition(
                account_id=account.id,
                market_id=market.id,
                outcome_index=0,
                quantity=Decimal("100"),
                avg_price=Decimal("0.571425"),
                mark_price=Decimal("0.62"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("4.8575"),
                status="open",
            )
        )
        await session.commit()

        result = await performance(session)

        assert result["cash"] == 9942.8575
        assert result["position_value"] == 62.0
        assert result["equity"] == 10004.8575
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_performance_reports_drawdown_when_equity_is_below_starting_cash(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'drawdown.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        session.add(PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9250")))
        await session.commit()

        result = await performance(session)

        assert result["equity"] == 9250
        assert result["max_drawdown"] == 0.075
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_performance_reports_historical_max_drawdown_from_trade_curve(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'historical-drawdown.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("11000"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=10),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="OPEN",
        )
        session.add(market)
        await session.flush()

        base_ts = datetime.now(UTC) - timedelta(hours=4)
        fills = [
            ("BUY", Decimal("0.50"), Decimal("10000")),
            ("SELL", Decimal("1.00"), Decimal("10000")),
            ("BUY", Decimal("1.00"), Decimal("10000")),
            ("SELL", Decimal("0.60"), Decimal("10000")),
        ]
        for offset, (side, price, quantity) in enumerate(fills):
            order = PaperOrder(
                account_id=account.id,
                market_id=market.id,
                side=side,
                outcome_index=0,
                limit_price=price,
                quantity=quantity,
                status="filled",
                created_at=base_ts + timedelta(minutes=offset),
                filled_at=base_ts + timedelta(minutes=offset),
            )
            session.add(order)
            await session.flush()
            session.add(
                PaperFill(
                    order_id=order.id,
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    side=side,
                    price=price,
                    quantity=quantity,
                    notional=price * quantity,
                    fee=Decimal("0"),
                    created_at=base_ts + timedelta(minutes=offset),
                )
            )
        await session.commit()

        result = await performance(session)

        assert result["equity"] == 11000
        assert result["max_drawdown"] == pytest.approx(0.2666666667)
    await sessionmaker.bind.dispose()
