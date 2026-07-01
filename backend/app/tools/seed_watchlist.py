from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.time import utcnow
from app.db.models import MarketOutcome, MarketSnapshot, PredictionEvent, PredictionMarket, Venue
from app.db.session import get_session_factory
from app.services.bootstrap import ensure_default_paper_account, ensure_default_venues


async def seed() -> None:
    async with get_session_factory()() as session:
        await ensure_default_venues(session)
        await ensure_default_paper_account(session)
        venue = await session.scalar(select(Venue).where(Venue.code == "POLYMARKET"))
        existing = await session.scalar(
            select(PredictionMarket).where(PredictionMarket.external_market_id == "seed-btc-80000")
        )
        if existing is None and venue is not None:
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="seed-event-btc-july",
                protocol="POLYMARKET",
                slug="seed-btc-july",
                question="Will BTC be above $80,000 on July 31, 2026?",
                description=(
                    "Seed market for local development. It resolves from a clear BTC reference "
                    "price at the listed deadline and is safe for paper trading tests."
                ),
                categories=["crypto"],
                status="OPEN",
                venue_url="https://example.com/seed-btc-july",
                closes_at=utcnow() + timedelta(days=30),
                resolves_at=utcnow() + timedelta(days=31),
                market_count=1,
            )
            session.add(event)
            await session.flush()
            market = PredictionMarket(
                event_id=event.id,
                venue_id=venue.id,
                external_market_id="seed-btc-80000",
                protocol="POLYMARKET",
                label="BTC above 80000",
                question=event.question,
                status="OPEN",
                closes_at=event.closes_at,
                resolves_at=event.resolves_at,
                raw_json={"current_price": 85000, "annualized_volatility": 0.45},
            )
            session.add(market)
            await session.flush()
            session.add_all(
                [
                    MarketOutcome(market_id=market.id, outcome_index=0, label="Yes", side="YES"),
                    MarketOutcome(market_id=market.id, outcome_index=1, label="No", side="NO"),
                    MarketSnapshot(
                        market_id=market.id,
                        ts=utcnow(),
                        outcome0_label="Yes",
                        outcome0_best_bid=Decimal("0.55"),
                        outcome0_best_ask=Decimal("0.57"),
                        outcome0_spread=Decimal("0.02"),
                        outcome1_label="No",
                        outcome1_best_bid=Decimal("0.41"),
                        outcome1_best_ask=Decimal("0.43"),
                        outcome1_spread=Decimal("0.02"),
                        liquidity_usd=Decimal("25000"),
                        volume_usd_24h=Decimal("5000"),
                        trades_24h=Decimal("100"),
                        market_quality_score=Decimal("80"),
                    ),
                ]
            )
        await session.commit()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

