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


@pytest.mark.asyncio
async def test_list_signals_deduplicates_hold_signals_by_market_and_side(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'hold-dedupe.db'}")
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
            question="Crypto events",
            categories=["crypto"],
            status="OPEN",
        )
        session.add(event)
        await session.flush()
        market_a = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market-a",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            status="OPEN",
        )
        market_b = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market-b",
            protocol="POLYMARKET",
            question="Will ETH be above $3,000?",
            status="OPEN",
        )
        session.add_all([market_a, market_b])
        await session.flush()
        now = datetime.now(UTC)
        session.add_all(
            [
                ModelSignal(
                    market_id=market_a.id,
                    ts=now - timedelta(minutes=10),
                    strategy_code="crypto_threshold_v2",
                    action="HOLD",
                    side="YES",
                    edge=Decimal("0.01"),
                    confidence=Decimal("0.7"),
                    market_quality_score=Decimal("80"),
                ),
                ModelSignal(
                    market_id=market_a.id,
                    ts=now - timedelta(minutes=5),
                    strategy_code="crypto_threshold_v2",
                    action="HOLD",
                    side="YES",
                    edge=Decimal("0.02"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                ),
                ModelSignal(
                    market_id=market_a.id,
                    ts=now,
                    strategy_code="crypto_threshold_v2",
                    action="HOLD",
                    side="YES",
                    edge=Decimal("0.03"),
                    confidence=Decimal("0.9"),
                    market_quality_score=Decimal("80"),
                ),
                ModelSignal(
                    market_id=market_b.id,
                    ts=now - timedelta(minutes=1),
                    strategy_code="crypto_threshold_v2",
                    action="HOLD",
                    side="NO",
                    edge=Decimal("0.04"),
                    confidence=Decimal("0.85"),
                    market_quality_score=Decimal("80"),
                ),
            ]
        )
        await session.commit()

        response = await list_signals(session, action="HOLD", limit=10)

        assert response["total"] == 2
        assert [item["question"] for item in response["items"]] == [
            "Will BTC be above $80,000?",
            "Will ETH be above $3,000?",
        ]
        assert response["items"][0]["edge"] == 0.03
    await sessionmaker.bind.dispose()
