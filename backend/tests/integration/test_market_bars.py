from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import MarketSnapshot, PredictionEvent, PredictionMarket, Venue
from app.db.session import Base, create_sessionmaker
from app.services.market_data import market_bars


@pytest.mark.asyncio
async def test_market_bars_respects_range_filter(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'bars.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
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
        session.add_all(
            [
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(days=2),
                    outcome0_best_bid=Decimal("0.40"),
                    outcome0_best_ask=Decimal("0.42"),
                ),
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(hours=1),
                    outcome0_best_bid=Decimal("0.50"),
                    outcome0_best_ask=Decimal("0.52"),
                ),
            ]
        )
        await session.commit()

        response = await market_bars(session, market.id, range_name="24h", resolution="min15")

        assert response["source"] == "local_snapshots"
        assert len(response["bars"]) == 1
        assert response["bars"][0]["yes_bid"] == 0.5
    await sessionmaker.bind.dispose()
