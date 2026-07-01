from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

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
from app.services.paper_trading import PaperOrderInput, create_paper_order
from app.services.signals import create_order_from_signal


@pytest.mark.asyncio
async def test_manual_orders_are_allowed_on_low_quality_market_but_signal_orders_are_blocked(
    tmp_path, monkeypatch
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'risk.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    sessionmaker = create_sessionmaker(database_url)
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("10000"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="low-quality-event",
            protocol="POLYMARKET",
            question="Will a vague crypto thing happen?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=1),
            market_count=1,
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="low-quality-market",
            protocol="POLYMARKET",
            question="Will a vague crypto thing happen?",
            status="OPEN",
            closes_at=event.closes_at,
        )
        session.add(market)
        await session.flush()
        session.add(
            MarketSnapshot(
                market_id=market.id,
                ts=datetime.now(UTC),
                outcome0_label="Yes",
                outcome0_best_bid=Decimal("0.40"),
                outcome0_best_ask=Decimal("0.50"),
                outcome0_spread=Decimal("0.10"),
                outcome1_label="No",
                outcome1_best_bid=Decimal("0.45"),
                outcome1_best_ask=Decimal("0.55"),
                outcome1_spread=Decimal("0.10"),
                liquidity_usd=Decimal("500"),
                volume_usd_24h=Decimal("100"),
                market_quality_score=Decimal("30"),
            )
        )
        signal = ModelSignal(
            market_id=market.id,
            ts=datetime.now(UTC),
            strategy_code="crypto_threshold_v1",
            action="BUY",
            side="YES",
            executable_price=Decimal("0.50"),
            edge=Decimal("0.10"),
            confidence=Decimal("0.80"),
            market_quality_score=Decimal("30"),
            reason_codes=[],
            risk_flags=["QUALITY_BELOW_GATE"],
        )
        session.add(signal)
        await session.commit()

        manual = await create_paper_order(
            session,
            PaperOrderInput(
                account_id=account.id,
                market_id=market.id,
                side="BUY",
                outcome_index=0,
                limit_price=Decimal("0.50"),
                quantity=Decimal("10"),
            ),
        )
        assert manual["order"]["status"] == "filled"

        blocked = await create_order_from_signal(
            session,
            signal_id=signal.id,
            account_id=account.id,
            notional=Decimal("5"),
            limit_price=Decimal("0.50"),
        )
        assert blocked["order"]["status"] == "rejected"
        assert blocked["order"]["reason"] == "market_quality_below_gate"
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_manual_sell_without_inventory_is_rejected_without_cash_change(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'sell-risk.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("10000"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=1),
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
                market_quality_score=Decimal("80"),
            )
        )
        await session.commit()

        response = await create_paper_order(
            session,
            PaperOrderInput(
                account_id=account.id,
                market_id=market.id,
                side="SELL",
                outcome_index=0,
                limit_price=Decimal("0.50"),
                quantity=Decimal("10"),
            ),
        )

        await session.refresh(account)
        assert response["order"]["status"] == "rejected"
        assert response["order"]["reason"] == "insufficient_inventory"
        assert account.cash == Decimal("10000.00000000")
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_new_buy_is_rejected_when_single_market_risk_would_exceed_limit(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'market-risk.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9700"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=1),
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
            closes_at=event.closes_at,
        )
        session.add(market)
        await session.flush()
        session.add_all(
            [
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC),
                    outcome0_best_bid=Decimal("0.50"),
                    outcome0_best_ask=Decimal("0.50"),
                    market_quality_score=Decimal("80"),
                ),
                PaperPosition(
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    quantity=Decimal("600"),
                    avg_price=Decimal("0.50"),
                    mark_price=Decimal("0.50"),
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=Decimal("0"),
                    status="open",
                ),
            ]
        )
        await session.commit()

        response = await create_paper_order(
            session,
            PaperOrderInput(
                account_id=account.id,
                market_id=market.id,
                side="BUY",
                outcome_index=0,
                limit_price=Decimal("0.50"),
                quantity=Decimal("500"),
            ),
        )

        assert response["order"]["status"] == "rejected"
        assert response["order"]["reason"] == "market_exposure_exceeds_5pct_equity"
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_new_buy_is_rejected_when_market_closes_within_thirty_minutes(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'closing-soon.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("10000"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(minutes=20),
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
                market_quality_score=Decimal("80"),
            )
        )
        await session.commit()

        response = await create_paper_order(
            session,
            PaperOrderInput(
                account_id=account.id,
                market_id=market.id,
                side="BUY",
                outcome_index=0,
                limit_price=Decimal("0.52"),
                quantity=Decimal("10"),
            ),
        )

        assert response["order"]["status"] == "rejected"
        assert response["order"]["reason"] == "market_closing_soon"
    await sessionmaker.bind.dispose()
