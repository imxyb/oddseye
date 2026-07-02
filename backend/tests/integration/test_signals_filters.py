from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import ModelSignal, PredictionEvent, PredictionMarket, Venue
from app.db.session import Base, create_sessionmaker
from app.services.signals import list_signals


@pytest.mark.asyncio
async def test_list_signals_filters_before_applying_limit(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signals.db'}")
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
        session.add(
            ModelSignal(
                market_id=market.id,
                ts=datetime(2026, 7, 2, tzinfo=UTC),
                strategy_code="crypto_threshold_v1",
                action="OBSERVE",
                confidence=Decimal("0.8"),
                market_quality_score=Decimal("80"),
            )
        )
        session.add(
            ModelSignal(
                market_id=market.id,
                ts=datetime(2026, 7, 1, tzinfo=UTC),
                strategy_code="crypto_threshold_v1",
                action="BUY",
                side="YES",
                executable_price=Decimal("0.50"),
                edge=Decimal("0.10"),
                confidence=Decimal("0.8"),
                market_quality_score=Decimal("80"),
            )
        )
        await session.commit()

        response = await list_signals(session, action="BUY", limit=1)

        assert response["total"] == 1
        assert response["items"][0]["action"] == "BUY"
        assert response["items"][0]["strategy_code"] == "crypto_threshold_v1"
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_list_signals_excludes_expired_signals(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'expired-list.db'}")
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
                ModelSignal(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    strategy_code="crypto_threshold_v1",
                    action="BUY",
                    side="YES",
                    edge=Decimal("0.10"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                    expires_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
                ModelSignal(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(minutes=2),
                    strategy_code="crypto_threshold_v1",
                    action="BUY",
                    side="NO",
                    executable_price=Decimal("0.40"),
                    edge=Decimal("0.09"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                ),
            ]
        )
        await session.commit()

        response = await list_signals(session, action="BUY", limit=5)

        assert response["total"] == 1
        assert response["items"][0]["side"] == "NO"
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_list_signals_hides_legacy_buy_signals_with_nonpositive_executable_price(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'legacy-zero-buy.db'}")
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
                ModelSignal(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    strategy_code="crypto_threshold_v1",
                    action="BUY",
                    side="YES",
                    executable_price=Decimal("0"),
                    edge=Decimal("0.50"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                ),
                ModelSignal(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(minutes=1),
                    strategy_code="crypto_threshold_v1",
                    action="BUY",
                    side="NO",
                    executable_price=Decimal("0.42"),
                    edge=Decimal("0.09"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                ),
            ]
        )
        await session.commit()

        response = await list_signals(session, action="BUY", limit=5)

        assert response["total"] == 1
        assert response["items"][0]["side"] == "NO"
        assert response["items"][0]["executable_price"] == 0.42
    await sessionmaker.bind.dispose()
