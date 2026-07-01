from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import MarketSnapshot, ModelSignal, PredictionEvent, PredictionMarket, Venue
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


@pytest.mark.asyncio
async def test_radar_uses_latest_unexpired_signal(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'radar-signal.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="crypto-event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=30),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="crypto-market",
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
        session.add_all(
            [
                ModelSignal(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    strategy_code="crypto_threshold_v1",
                    action="BUY",
                    side="YES",
                    edge=Decimal("0.20"),
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
                    edge=Decimal("0.10"),
                    confidence=Decimal("0.8"),
                    market_quality_score=Decimal("80"),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                ),
            ]
        )
        await session.commit()

        response = await radar_markets(session, category="crypto")

        assert response["items"][0]["latest_signal"]["side"] == "NO"
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_radar_supports_documented_sort_dimensions(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'radar-sorts.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()

        high_quality = await _market_with_snapshot(
            session,
            venue,
            external_event_id="quality-event",
            external_market_id="quality-market",
            question="Will BTC be above $80,000?",
            closes_at=datetime.now(UTC) + timedelta(days=10),
            liquidity_usd=Decimal("2000"),
            volume_usd_24h=Decimal("1000"),
            market_quality_score=Decimal("90"),
            edge=Decimal("0.02"),
        )
        high_volume = await _market_with_snapshot(
            session,
            venue,
            external_event_id="volume-event",
            external_market_id="volume-market",
            question="Will ETH be above $3,000?",
            closes_at=datetime.now(UTC) + timedelta(days=20),
            liquidity_usd=Decimal("3000"),
            volume_usd_24h=Decimal("9000"),
            market_quality_score=Decimal("70"),
            edge=Decimal("0.05"),
        )
        high_liquidity = await _market_with_snapshot(
            session,
            venue,
            external_event_id="liquidity-event",
            external_market_id="liquidity-market",
            question="Will SOL be above $200?",
            closes_at=datetime.now(UTC) + timedelta(days=30),
            liquidity_usd=Decimal("12000"),
            volume_usd_24h=Decimal("2000"),
            market_quality_score=Decimal("60"),
            edge=Decimal("0.25"),
        )
        closing_soon = await _market_with_snapshot(
            session,
            venue,
            external_event_id="closing-event",
            external_market_id="closing-market",
            question="Will BTC be above $90,000?",
            closes_at=datetime.now(UTC) + timedelta(days=2),
            liquidity_usd=Decimal("1000"),
            volume_usd_24h=Decimal("500"),
            market_quality_score=Decimal("50"),
            edge=Decimal("0.01"),
        )
        await session.commit()

        quality = await radar_markets(session, category="crypto", sort="quality")
        volume = await radar_markets(session, category="crypto", sort="volume")
        liquidity = await radar_markets(session, category="crypto", sort="liquidity")
        closing = await radar_markets(session, category="crypto", sort="closingSoon")
        edge = await radar_markets(session, category="crypto", sort="edge")

        assert quality["items"][0]["market_id"] == high_quality.id
        assert volume["items"][0]["market_id"] == high_volume.id
        assert liquidity["items"][0]["market_id"] == high_liquidity.id
        assert closing["items"][0]["market_id"] == closing_soon.id
        assert edge["items"][0]["market_id"] == high_liquidity.id
    await sessionmaker.bind.dispose()


async def _market_with_snapshot(
    session,
    venue: Venue,
    *,
    external_event_id: str,
    external_market_id: str,
    question: str,
    closes_at: datetime,
    liquidity_usd: Decimal,
    volume_usd_24h: Decimal,
    market_quality_score: Decimal,
    edge: Decimal,
) -> PredictionMarket:
    event = PredictionEvent(
        venue_id=venue.id,
        external_event_id=external_event_id,
        protocol="POLYMARKET",
        question=question,
        categories=["crypto"],
        status="OPEN",
        closes_at=closes_at,
    )
    session.add(event)
    await session.flush()
    market = PredictionMarket(
        event_id=event.id,
        venue_id=venue.id,
        external_market_id=external_market_id,
        protocol="POLYMARKET",
        question=question,
        status="OPEN",
        closes_at=closes_at,
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
            liquidity_usd=liquidity_usd,
            volume_usd_24h=volume_usd_24h,
            market_quality_score=market_quality_score,
        )
    )
    session.add(
        ModelSignal(
            market_id=market.id,
            ts=datetime.now(UTC),
            strategy_code="crypto_threshold_v1",
            action="BUY",
            side="YES",
            edge=edge,
            confidence=Decimal("0.8"),
            market_quality_score=market_quality_score,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    return market
