from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
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
