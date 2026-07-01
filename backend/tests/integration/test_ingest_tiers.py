from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import (
    ModelSignal,
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.workers.ingest import event_ids_for_sync


@pytest.mark.asyncio
async def test_event_ids_for_sync_prioritizes_positions_and_buy_signals(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'tiers.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9900"))
        session.add_all([venue, account])
        await session.flush()

        position_event = await _event(session, venue.id, "position-event", days=5)
        signal_event = await _event(session, venue.id, "signal-event", days=4)
        recent_event = await _event(session, venue.id, "recent-event", days=1)
        position_market = await _market(session, venue.id, position_event)
        signal_market = await _market(session, venue.id, signal_event)
        await _market(session, venue.id, recent_event)
        session.add(
            PaperPosition(
                account_id=account.id,
                market_id=position_market.id,
                outcome_index=0,
                quantity=Decimal("10"),
                avg_price=Decimal("0.50"),
                mark_price=Decimal("0.50"),
                status="open",
            )
        )
        session.add(
            ModelSignal(
                market_id=signal_market.id,
                ts=datetime.now(UTC),
                strategy_code="crypto_threshold_v1",
                action="BUY",
                side="YES",
                executable_price=Decimal("0.50"),
                edge=Decimal("0.10"),
                confidence=Decimal("0.80"),
                reason_codes=[],
                risk_flags=[],
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await session.commit()

        event_ids = await event_ids_for_sync(session, limit=2)

        assert event_ids == ["position-event", "signal-event"]
    await sessionmaker.bind.dispose()


async def _event(session, venue_id: str, external_id: str, days: int) -> PredictionEvent:
    event = PredictionEvent(
        venue_id=venue_id,
        external_event_id=external_id,
        protocol="POLYMARKET",
        question=external_id,
        categories=["crypto"],
        status="OPEN",
        closes_at=datetime.now(UTC) + timedelta(days=days),
    )
    session.add(event)
    await session.flush()
    return event


async def _market(session, venue_id: str, event: PredictionEvent) -> PredictionMarket:
    market = PredictionMarket(
        event_id=event.id,
        venue_id=venue_id,
        external_market_id=f"{event.external_event_id}-market",
        protocol="POLYMARKET",
        question=event.question,
        status="OPEN",
        closes_at=event.closes_at,
    )
    session.add(market)
    await session.flush()
    return market
