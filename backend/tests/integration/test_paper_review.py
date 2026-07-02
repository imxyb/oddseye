from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import (
    ModelSignal,
    PaperAccount,
    PaperFill,
    PaperOrder,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker
from app.services.paper_trading import review_report


@pytest.mark.asyncio
async def test_review_rollups_include_win_rate_pnl_edge_and_drawdown(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'paper-review.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("10008"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="OPEN",
            closes_at=datetime.now(UTC) + timedelta(days=10),
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
        signal = ModelSignal(
            market_id=market.id,
            ts=datetime.now(UTC),
            strategy_code="crypto_threshold_v1",
            action="BUY",
            side="YES",
            edge=Decimal("0.10"),
            confidence=Decimal("0.90"),
            reason_codes=["MODEL_EDGE_POSITIVE"],
            risk_flags=[],
        )
        session.add(signal)
        await session.flush()

        base_ts = datetime.now(UTC) - timedelta(hours=1)
        fills = [
            ("BUY", Decimal("0.50"), Decimal("100"), Decimal("1")),
            ("SELL", Decimal("0.65"), Decimal("100"), Decimal("1")),
            ("BUY", Decimal("0.50"), Decimal("100"), Decimal("0")),
            ("SELL", Decimal("0.45"), Decimal("100"), Decimal("0")),
        ]
        for offset, (side, price, quantity, fee) in enumerate(fills):
            order = PaperOrder(
                account_id=account.id,
                market_id=market.id,
                signal_id=signal.id,
                side=side,
                outcome_index=0,
                limit_price=price,
                quantity=quantity,
                status="filled",
                created_at=base_ts + timedelta(minutes=offset),
                filled_at=base_ts + timedelta(minutes=offset),
            )
            session.add(order)
            await session.flush()
            session.add(
                PaperFill(
                    order_id=order.id,
                    account_id=account.id,
                    market_id=market.id,
                    outcome_index=0,
                    side=side,
                    price=price,
                    quantity=quantity,
                    notional=price * quantity,
                    fee=fee,
                    created_at=base_ts + timedelta(minutes=offset),
                )
            )
        await session.commit()

        report = await review_report(session)

        strategy = _only_rollup(report["strategy_stats"], "crypto_threshold_v1")
        category = _only_rollup(report["category_stats"], "crypto")
        for rollup in (strategy, category):
            assert rollup["total_trades"] == 4
            assert rollup["average_edge"] == pytest.approx(0.10)
            assert rollup["realized_pnl"] == pytest.approx(8.0)
            assert rollup["win_rate"] == pytest.approx(0.5)
            assert rollup["max_drawdown"] == pytest.approx(5.0)
    await sessionmaker.bind.dispose()


def _only_rollup(items: list[dict], key: str) -> dict:
    matches = [item for item in items if item["key"] == key]
    assert len(matches) == 1
    return matches[0]
