from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import (
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.services.resolution import settle_due_markets


@pytest.mark.asyncio
async def test_settle_due_markets_closes_winning_position_and_pays_cash(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'settle.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9996"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="RESOLVED",
            closes_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="RESOLVED",
            closes_at=event.closes_at,
            raw_json={"resolved_outcome_index": 0, "resolved_label": "Yes"},
        )
        session.add(market)
        await session.flush()
        position = PaperPosition(
            account_id=account.id,
            market_id=market.id,
            outcome_index=0,
            quantity=Decimal("10"),
            avg_price=Decimal("0.40"),
            mark_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
        )
        session.add(position)
        await session.commit()

        processed = await settle_due_markets(session)

        await session.refresh(account)
        await session.refresh(position)
        assert processed == 1
        assert account.cash == Decimal("10006.00000000")
        assert position.status == "closed"
        assert position.quantity == Decimal("0E-8")
        assert position.realized_pnl == Decimal("6.00000000")
        assert position.unrealized_pnl == Decimal("0E-8")
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_settle_due_markets_marks_unknown_resolution_pending(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'pending.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9996"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="CLOSED",
            closes_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="CLOSED",
            closes_at=event.closes_at,
        )
        session.add(market)
        await session.flush()
        position = PaperPosition(
            account_id=account.id,
            market_id=market.id,
            outcome_index=0,
            quantity=Decimal("10"),
            avg_price=Decimal("0.40"),
            mark_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
        )
        session.add(position)
        await session.commit()

        processed = await settle_due_markets(session)

        await session.refresh(position)
        assert processed == 1
        assert position.status == "pending_resolution"
        assert position.quantity == Decimal("10.00000000")
    await sessionmaker.bind.dispose()
