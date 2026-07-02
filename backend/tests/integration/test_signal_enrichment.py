from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import (
    MarketSnapshot,
    ModelSignal,
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.services.signals import compute_crypto_signals


@dataclass
class FakeAssetMarketDataProvider:
    calls: list[str]

    async def asset_market_data(self, asset: str):
        self.calls.append(asset)
        return {
            "current_price": Decimal("3500"),
            "annualized_volatility": Decimal("0.35"),
            "source": "test",
        }


@pytest.mark.asyncio
async def test_compute_crypto_signals_uses_asset_enrichment_for_codex_markets(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signal-enrichment.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue = Venue(code="POLYMARKET", name="Polymarket")
            session.add(venue)
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="event",
                protocol="POLYMARKET",
                question="Will ETH be above $3,000 on July 31, 2026?",
                categories=["crypto", "ethereum"],
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
                closes_at=datetime(2026, 7, 31, tzinfo=UTC),
                raw_json={
                    "id": "market",
                    "market": {"id": "market"},
                    "outcome0": {"label": "Yes"},
                    "outcome1": {"label": "No"},
                },
            )
            session.add(market)
            await session.flush()
            session.add(
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime(2026, 7, 1, tzinfo=UTC),
                    outcome0_best_ask=Decimal("0.50"),
                    outcome1_best_ask=Decimal("0.53"),
                    liquidity_usd=Decimal("25000"),
                    volume_usd_24h=Decimal("5000"),
                    market_quality_score=Decimal("80"),
                )
            )
            await session.commit()

            provider = FakeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))

        assert count == 1
        assert provider.calls == ["ETH"]
        assert signal is not None
        assert signal.action == "BUY"
        assert signal.side == "YES"
        assert signal.raw_json["asset_market_data"]["source"] == "test"
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_ignores_unparsed_crypto_markets(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signal-ignore.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue = Venue(code="POLYMARKET", name="Polymarket")
            session.add(venue)
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="event",
                protocol="POLYMARKET",
                question="Will Bitcoin trend on social media in July 2026?",
                categories=["crypto", "bitcoin"],
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
                closes_at=datetime(2026, 7, 31, tzinfo=UTC),
                raw_json={"id": "market", "market": {"id": "market"}},
            )
            session.add(market)
            await session.flush()
            session.add(
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime(2026, 7, 1, tzinfo=UTC),
                    outcome0_best_ask=Decimal("0.50"),
                    outcome1_best_ask=Decimal("0.53"),
                    liquidity_usd=Decimal("25000"),
                    volume_usd_24h=Decimal("5000"),
                    market_quality_score=Decimal("80"),
                )
            )
            await session.commit()

            provider = FakeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))

        assert count == 1
        assert provider.calls == []
        assert signal is not None
        assert signal.action == "IGNORE"
        assert signal.side is None
        assert "PARSER_FAILED" in signal.risk_flags
        assert signal.expires_at is not None
        assert signal.expires_at - signal.ts >= timedelta(minutes=10)
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_signals_creates_observe_only_macro_signals(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'macro-signal.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue = Venue(code="KALSHI", name="Kalshi")
            session.add(venue)
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="fomc-event",
                protocol="KALSHI",
                question="Will the Fed cut rates at the next FOMC meeting?",
                categories=["economy", "rates"],
                status="OPEN",
            )
            session.add(event)
            await session.flush()
            market = PredictionMarket(
                event_id=event.id,
                venue_id=venue.id,
                external_market_id="fomc-market",
                protocol="KALSHI",
                question=event.question,
                status="OPEN",
                closes_at=datetime(2026, 7, 31, tzinfo=UTC),
                raw_json={"id": "fomc-market", "market": {"id": "fomc-market"}},
            )
            session.add(market)
            await session.flush()
            session.add(
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime(2026, 7, 1, tzinfo=UTC),
                    outcome0_best_bid=Decimal("0.41"),
                    outcome0_best_ask=Decimal("0.43"),
                    outcome1_best_bid=Decimal("0.57"),
                    outcome1_best_ask=Decimal("0.59"),
                    liquidity_usd=Decimal("15000"),
                    volume_usd_24h=Decimal("2500"),
                    market_quality_score=Decimal("72"),
                )
            )
            await session.commit()

            from app.services import signals

            count = await signals.compute_signals(session, asset_market_data_provider=FakeAssetMarketDataProvider(calls=[]))
            await session.commit()

            signal = await session.scalar(select(ModelSignal))
            listed = await signals.list_signals(session, category="economics", limit=5)

        assert count == 1
        assert signal is not None
        assert signal.strategy_code == "macro_calendar_v1"
        assert signal.action == "OBSERVE"
        assert signal.side is None
        assert signal.model_probability is None
        assert signal.executable_price is None
        assert signal.edge is None
        assert signal.confidence == Decimal("72")
        assert signal.market_quality_score == Decimal("72")
        assert signal.raw_json["snapshot_id"] == 1
        assert listed["total"] == 1
        assert listed["items"][0]["strategy_code"] == "macro_calendar_v1"
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_holds_existing_same_side_position(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signal-hold.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue, market = await _crypto_market_with_snapshot(session)
            account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9500"))
            session.add(account)
            await session.flush()
            session.add(
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    quantity=Decimal("100"),
                    avg_price=Decimal("0.50"),
                    mark_price=Decimal("0.60"),
                    realized_pnl=Decimal("0"),
                    unrealized_pnl=Decimal("10"),
                    status="open",
                )
            )
            await session.commit()

            provider = FakeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))

        assert venue.code == "POLYMARKET"
        assert count == 1
        assert signal is not None
        assert signal.action == "HOLD"
        assert signal.side == "YES"
        assert "HOLD_EXISTING_POSITION" in signal.reason_codes
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_exits_existing_opposite_position(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signal-exit.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            _venue, market = await _crypto_market_with_snapshot(session)
            account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9500"))
            session.add(account)
            await session.flush()
            session.add(
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=1,
                    quantity=Decimal("100"),
                    avg_price=Decimal("0.53"),
                    mark_price=Decimal("0.47"),
                    realized_pnl=Decimal("0"),
                    unrealized_pnl=Decimal("-6"),
                    status="open",
                )
            )
            await session.commit()

            provider = FakeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))

        assert count == 1
        assert signal is not None
        assert signal.action == "EXIT"
        assert signal.side == "NO"
        assert signal.executable_price == Decimal("0.47")
        assert "EXIT_OPPOSING_MODEL_EDGE" in signal.reason_codes
    finally:
        await sessionmaker.bind.dispose()


async def _crypto_market_with_snapshot(session):
    venue = Venue(code="POLYMARKET", name="Polymarket")
    session.add(venue)
    await session.flush()
    event = PredictionEvent(
        venue_id=venue.id,
        external_event_id="event",
        protocol="POLYMARKET",
        question="Will ETH be above $3,000 on July 31, 2026?",
        categories=["crypto", "ethereum"],
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
        closes_at=datetime(2026, 7, 31, tzinfo=UTC),
        raw_json={
            "id": "market",
            "market": {"id": "market"},
            "outcome0": {"label": "Yes"},
            "outcome1": {"label": "No"},
        },
    )
    session.add(market)
    await session.flush()
    session.add(
        MarketSnapshot(
            market_id=market.id,
            ts=datetime(2026, 7, 1, tzinfo=UTC),
            outcome0_best_bid=Decimal("0.58"),
            outcome0_best_ask=Decimal("0.50"),
            outcome1_best_bid=Decimal("0.47"),
            outcome1_best_ask=Decimal("0.53"),
            liquidity_usd=Decimal("25000"),
            volume_usd_24h=Decimal("5000"),
            market_quality_score=Decimal("80"),
        )
    )
    return venue, market
