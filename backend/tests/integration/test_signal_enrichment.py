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
    PaperFill,
    PaperOrder,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.services.signals import compute_crypto_signals, list_signals


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


@dataclass
class FakeHighEdgeAssetMarketDataProvider:
    calls: list[str]
    current_price: Decimal = Decimal("3500")
    annualized_volatility: Decimal = Decimal("0.35")

    async def asset_market_data(self, asset: str):
        self.calls.append(asset)
        return {
            "asset": asset,
            "current_price": self.current_price,
            "annualized_volatility": self.annualized_volatility,
            "realized_vol_7d": self.annualized_volatility,
            "realized_vol_30d": self.annualized_volatility,
            "realized_vol_90d": self.annualized_volatility,
            "momentum_24h": Decimal("0"),
            "source": "test",
        }


@pytest.mark.asyncio
async def test_compute_crypto_signals_v2_auto_fills_buy_order(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-auto-buy.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue, market = await _crypto_market_with_snapshot(
                session,
                question="Will ETH be above $3,000 on July 10, 2026?",
                yes_bid=Decimal("0.48"),
                yes_ask=Decimal("0.50"),
            )
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))
            order = await session.scalar(select(PaperOrder))
            fill = await session.scalar(select(PaperFill))
            position = await session.scalar(select(PaperPosition))
            listed = await list_signals(session, category="crypto", limit=5)

        assert venue.code == "POLYMARKET"
        assert count == 1
        assert provider.calls == ["ETH"]
        assert signal is not None
        assert signal.strategy_code == "crypto_threshold_v2"
        assert signal.action == "BUY"
        assert signal.side == "YES"
        assert signal.raw_json["strategy_code"] == "crypto_threshold_v2"
        assert signal.raw_json["decision"]["action"] == "BUY"
        assert order is not None
        assert order.status == "filled"
        assert order.signal_id == signal.id
        assert fill is not None
        assert fill.snapshot_id == signal.raw_json["snapshot_id"]
        assert position is not None
        assert position.status == "open"
        assert listed["items"][0]["strategy_code"] == "crypto_threshold_v2"
        assert listed["items"][0]["asset"] == "ETH"
        assert listed["items"][0]["market_type"] == "close_above"
        assert listed["items"][0]["probability_range"] is not None
        assert listed["items"][0]["required_edge"] is not None
        assert listed["items"][0]["edge_stress"] is not None
        assert listed["items"][0]["raw_signal_json"]["strategy_code"] == "crypto_threshold_v2"
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_v2_skips_kalshi_crypto_market(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-skip-kalshi.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            venue = Venue(code="KALSHI", name="Kalshi")
            session.add(venue)
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="kalshi-crypto-event",
                protocol="KALSHI",
                question="Will BTC be above $110,000 on July 31, 2026?",
                categories=["crypto", "bitcoin"],
                status="OPEN",
            )
            session.add(event)
            await session.flush()
            market = PredictionMarket(
                event_id=event.id,
                venue_id=venue.id,
                external_market_id="kalshi-crypto-market",
                protocol="KALSHI",
                question=event.question,
                status="OPEN",
                closes_at=datetime(2026, 7, 31, tzinfo=UTC),
            )
            session.add(market)
            await session.flush()
            session.add(
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    outcome0_best_bid=Decimal("0.48"),
                    outcome0_best_ask=Decimal("0.50"),
                    outcome0_spread=Decimal("0.02"),
                    outcome1_best_bid=Decimal("0.48"),
                    outcome1_best_ask=Decimal("0.50"),
                    outcome1_spread=Decimal("0.02"),
                    liquidity_usd=Decimal("25000"),
                    market_quality_score=Decimal("80"),
                )
            )
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal_count = len((await session.execute(select(ModelSignal))).scalars().all())

        assert count == 0
        assert signal_count == 0
        assert provider.calls == []
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_v2_blocked_signal_does_not_create_order(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-blocked.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            await _crypto_market_with_snapshot(
                session,
                question="Will ETH trend higher by July 31, 2026?",
            )
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(calls=[])
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))
            order_count = len((await session.execute(select(PaperOrder))).scalars().all())

        assert count == 1
        assert provider.calls == []
        assert signal is not None
        assert signal.strategy_code == "crypto_threshold_v2"
        assert signal.action == "BLOCKED"
        assert "NO_THRESHOLD" in signal.risk_flags
        assert signal.raw_json["decision"]["blocked_reason"] == "PARSER_FAILED"
        assert order_count == 0
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_v2_exits_position_when_entry_gate_blocks(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-exit-gate-block.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            _venue, market = await _crypto_market_with_snapshot(
                session,
                question="Will ETH be above $3,000 on July 10, 2026?",
                yes_bid=Decimal("0.50"),
                yes_ask=Decimal("0.95"),
                no_bid=Decimal("0.03"),
                no_ask=Decimal("0.05"),
            )
            account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9950"))
            session.add(account)
            await session.flush()
            session.add(
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    quantity=Decimal("100"),
                    avg_price=Decimal("0.50"),
                    mark_price=Decimal("0.50"),
                    realized_pnl=Decimal("0"),
                    unrealized_pnl=Decimal("0"),
                    status="open",
                )
            )
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(
                calls=[],
                current_price=Decimal("2500"),
                annualized_volatility=Decimal("0.35"),
            )
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))
            order = await session.scalar(select(PaperOrder))

        assert count == 1
        assert signal is not None
        assert signal.action == "EXIT"
        assert signal.side == "YES"
        assert order is not None
        assert order.side == "SELL"
        assert order.status == "filled"
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_auto_exit_order_bypasses_buy_only_quality_gate(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-exit-low-quality.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            _venue, market = await _crypto_market_with_snapshot(
                session,
                question="Will ETH be above $3,000 on July 10, 2026?",
                yes_bid=Decimal("0.50"),
                yes_ask=Decimal("0.95"),
                no_bid=Decimal("0.03"),
                no_ask=Decimal("0.05"),
            )
            account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9950"))
            session.add(account)
            await session.flush()
            session.add(
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    quantity=Decimal("100"),
                    avg_price=Decimal("0.50"),
                    mark_price=Decimal("0.50"),
                    realized_pnl=Decimal("0"),
                    unrealized_pnl=Decimal("0"),
                    status="open",
                )
            )
            latest_snapshot = await session.scalar(select(MarketSnapshot).where(MarketSnapshot.market_id == market.id))
            assert latest_snapshot is not None
            latest_snapshot.market_quality_score = Decimal("30")
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(
                calls=[],
                current_price=Decimal("2500"),
                annualized_volatility=Decimal("0.35"),
            )
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = await session.scalar(select(ModelSignal))
            order = await session.scalar(select(PaperOrder))

        assert count == 1
        assert signal is not None
        assert signal.action == "EXIT"
        assert order is not None
        assert order.status == "filled"
        assert order.reason is None
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_existing_position_exits_when_probability_deteriorates_from_entry_trace(
    tmp_path,
) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'v2-prob-deterioration.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            _venue, market = await _crypto_market_with_snapshot(
                session,
                question="Will ETH be above $3,000 on July 10, 2026?",
                yes_bid=Decimal("0.10"),
                yes_ask=Decimal("0.80"),
                no_bid=Decimal("0.03"),
                no_ask=Decimal("0.95"),
            )
            account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9950"))
            session.add(account)
            await session.flush()
            entry_signal = ModelSignal(
                market_id=market.id,
                ts=datetime.now(UTC) - timedelta(hours=2),
                strategy_code="crypto_threshold_v2",
                action="BUY",
                side="YES",
                executable_price=Decimal("0.50"),
                edge=Decimal("0.20"),
                confidence=Decimal("0.80"),
                reason_codes=[],
                risk_flags=[],
                raw_json={"probability": {"p_calibrated": 0.95}},
            )
            session.add(entry_signal)
            await session.flush()
            session.add(
                PaperOrder(
                    account_id=account.id,
                    market_id=market.id,
                    signal_id=entry_signal.id,
                    side="BUY",
                    outcome_index=0,
                    limit_price=Decimal("0.50"),
                    quantity=Decimal("100"),
                    status="filled",
                    filled_at=datetime.now(UTC) - timedelta(hours=2),
                )
            )
            session.add(
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    quantity=Decimal("100"),
                    avg_price=Decimal("0.50"),
                    mark_price=Decimal("0.10"),
                    realized_pnl=Decimal("0"),
                    unrealized_pnl=Decimal("-40"),
                    status="open",
                )
            )
            await session.commit()

            provider = FakeHighEdgeAssetMarketDataProvider(
                calls=[],
                current_price=Decimal("3100"),
                annualized_volatility=Decimal("0.35"),
            )
            count = await compute_crypto_signals(session, asset_market_data_provider=provider)
            await session.commit()

            signal = (
                await session.execute(select(ModelSignal).order_by(ModelSignal.ts.desc()))
            ).scalars().first()

        assert count == 1
        assert signal is not None
        assert signal.action == "EXIT"
        assert "PROBABILITY_DETERIORATED" in signal.reason_codes
    finally:
        await sessionmaker.bind.dispose()


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
                question="Will ETH be above $3,000 on July 10, 2026?",
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
                closes_at=datetime(2026, 7, 10, tzinfo=UTC),
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
                    ts=datetime.now(UTC),
                    outcome0_best_bid=Decimal("0.48"),
                    outcome0_best_ask=Decimal("0.50"),
                    outcome0_spread=Decimal("0.02"),
                    outcome1_best_bid=Decimal("0.47"),
                    outcome1_best_ask=Decimal("0.53"),
                    outcome1_spread=Decimal("0.06"),
                    outcome0_liquidity=Decimal("25000"),
                    outcome1_liquidity=Decimal("25000"),
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
        assert signal.strategy_code == "crypto_threshold_v2"
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
        assert signal.strategy_code == "crypto_threshold_v2"
        assert signal.action == "BLOCKED"
        assert signal.side is None
        assert "NO_THRESHOLD" in signal.risk_flags
        assert signal.expires_at is not None
        assert signal.expires_at - signal.ts >= timedelta(minutes=10)
    finally:
        await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_compute_crypto_signals_observes_touch_markets_without_edge(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'signal-touch.db'}")
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
                question="Will BTC touch $120,000 before July 10, 2026?",
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
                closes_at=datetime(2026, 7, 10, tzinfo=UTC),
                raw_json={"id": "market", "market": {"id": "market"}},
            )
            session.add(market)
            await session.flush()
            session.add(
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    outcome0_best_bid=Decimal("0.43"),
                    outcome0_best_ask=Decimal("0.45"),
                    outcome0_spread=Decimal("0.02"),
                    outcome1_best_bid=Decimal("0.94"),
                    outcome1_best_ask=Decimal("0.96"),
                    outcome1_spread=Decimal("0.02"),
                    outcome0_liquidity=Decimal("25000"),
                    outcome1_liquidity=Decimal("25000"),
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
        assert provider.calls == ["BTC"]
        assert signal is not None
        assert signal.action == "OBSERVE"
        assert signal.side is None
        assert signal.strategy_code == "crypto_threshold_v2"
        assert "NO_EXECUTABLE_EDGE" in signal.reason_codes
        assert "BARRIER_TOUCH_MODEL_NOT_IMPLEMENTED" not in signal.risk_flags
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
        assert "HOLD_POSITIVE_EV" in signal.reason_codes
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
            order = await session.scalar(select(PaperOrder))
            fill = await session.scalar(select(PaperFill))
            position = await session.scalar(select(PaperPosition))

        assert count == 1
        assert signal is not None
        assert signal.action == "EXIT"
        assert signal.side == "NO"
        assert signal.executable_price == Decimal("0.47")
        assert "EXIT_OPPOSING_MODEL_EDGE" in signal.reason_codes
        assert order is not None
        assert order.side == "SELL"
        assert order.status == "filled"
        assert fill is not None
        assert fill.side == "SELL"
        assert position is not None
        assert position.status == "closed"
    finally:
        await sessionmaker.bind.dispose()


async def _crypto_market_with_snapshot(
    session,
    question: str = "Will ETH be above $3,000 on July 10, 2026?",
    yes_bid: Decimal = Decimal("0.48"),
    yes_ask: Decimal = Decimal("0.50"),
    no_bid: Decimal = Decimal("0.47"),
    no_ask: Decimal = Decimal("0.53"),
):
    venue = Venue(code="POLYMARKET", name="Polymarket")
    session.add(venue)
    await session.flush()
    event = PredictionEvent(
        venue_id=venue.id,
        external_event_id="event",
        protocol="POLYMARKET",
        question=question,
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
        closes_at=datetime(2026, 7, 10, tzinfo=UTC),
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
            ts=datetime.now(UTC),
            outcome0_best_bid=yes_bid,
            outcome0_best_ask=yes_ask,
            outcome0_spread=abs(yes_ask - yes_bid),
            outcome1_best_bid=no_bid,
            outcome1_best_ask=no_ask,
            outcome1_spread=abs(no_ask - no_bid),
            outcome0_liquidity=Decimal("25000"),
            outcome1_liquidity=Decimal("25000"),
            liquidity_usd=Decimal("25000"),
            volume_usd_24h=Decimal("5000"),
            market_quality_score=Decimal("80"),
        )
    )
    return venue, market
