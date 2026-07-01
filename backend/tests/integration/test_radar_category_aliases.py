from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import MarketSnapshot, PredictionEvent, PredictionMarket, Venue
from app.db.session import Base, create_sessionmaker
from app.services.market_data import radar_markets


@pytest.mark.asyncio
async def test_economics_filter_includes_economy_category(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'macro.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="macro-event",
            protocol="POLYMARKET",
            question="Will the Fed cut rates in 2026?",
            categories=["economy", "fed"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="macro-market",
            protocol="POLYMARKET",
            question=event.question,
            status="OPEN",
            closes_at=event.closes_at,
        )
        session.add(market)
        await session.flush()
        session.add(
            MarketSnapshot(
                market_id=market.id,
                ts=datetime.now(UTC),
                outcome0_best_bid=Decimal("0.50"),
                outcome0_best_ask=Decimal("0.52"),
                outcome0_spread=Decimal("0.02"),
                liquidity_usd=Decimal("2000"),
                volume_usd_24h=Decimal("1000"),
                market_quality_score=Decimal("70"),
            )
        )
        await session.commit()

        response = await radar_markets(session, category="economics")

        assert response["total"] == 1
        assert response["items"][0]["category"] == "economy"
    await sessionmaker.bind.dispose()
