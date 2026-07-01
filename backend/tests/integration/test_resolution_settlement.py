from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

from httpx import AsyncClient, MockTransport, Request, Response
import pytest
from sqlalchemy import select

from app.codex.client import CodexClient
from app.core.config import get_settings
from app.db.models import (
    ApiUsageLedger,
    MarketResolution,
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker, get_session_factory
from app.services.resolution import poll_resolutions, settle_due_markets
from app.services.usage import DatabaseUsageRecorder


@pytest.mark.asyncio
async def test_settle_due_markets_closes_winning_position_and_pays_cash(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'settle.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9996"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="RESOLVED",
            closes_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="RESOLVED",
            closes_at=event.closes_at,
            raw_json={"resolved_outcome_index": 0, "resolved_label": "Yes"},
        )
        session.add(market)
        await session.flush()
        position = PaperPosition(
            account_id=account.id,
            market_id=market.id,
            outcome_index=0,
            quantity=Decimal("10"),
            avg_price=Decimal("0.40"),
            mark_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
        )
        session.add(position)
        await session.commit()

        processed = await settle_due_markets(session)

        await session.refresh(account)
        await session.refresh(position)
        assert processed == 1
        assert account.cash == Decimal("10006.00000000")
        assert position.status == "closed"
        assert position.quantity == Decimal("0E-8")
        assert position.realized_pnl == Decimal("6.00000000")
        assert position.unrealized_pnl == Decimal("0E-8")
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_settle_due_markets_marks_unknown_resolution_pending(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'pending.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9996"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="CLOSED",
            closes_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="CLOSED",
            closes_at=event.closes_at,
        )
        session.add(market)
        await session.flush()
        position = PaperPosition(
            account_id=account.id,
            market_id=market.id,
            outcome_index=0,
            quantity=Decimal("10"),
            avg_price=Decimal("0.40"),
            mark_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
        )
        session.add(position)
        await session.commit()

        processed = await settle_due_markets(session)

        await session.refresh(position)
        assert processed == 1
        assert position.status == "pending_resolution"
        assert position.quantity == Decimal("10.00000000")
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_settle_due_markets_infers_resolution_from_settled_prices(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'price-resolution.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9996"))
        session.add_all([venue, account])
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000?",
            categories=["crypto"],
            status="RESOLVED",
            closes_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market",
            protocol="POLYMARKET",
            question=event.question,
            status="RESOLVED",
            closes_at=event.closes_at,
            raw_json={
                "status": "CLOSED",
                "outcome0": {"label": "Yes", "lastPriceCT": "1"},
                "outcome1": {"label": "No", "lastPriceCT": "0"},
            },
        )
        session.add(market)
        await session.flush()
        position = PaperPosition(
            account_id=account.id,
            market_id=market.id,
            outcome_index=0,
            quantity=Decimal("10"),
            avg_price=Decimal("0.40"),
            mark_price=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            status="open",
        )
        session.add(position)
        await session.commit()

        processed = await settle_due_markets(session)

        await session.refresh(account)
        await session.refresh(position)
        resolution = await session.scalar(select(MarketResolution))
        assert processed == 1
        assert resolution is not None
        assert resolution.resolved_outcome_index == 0
        assert position.status == "closed"
        assert account.cash == Decimal("10006.00000000")
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_poll_resolutions_refreshes_due_markets_and_records_resolution_usage(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
app:
  timezone: UTC
auth:
  users: []
codex:
  fetch_profile: light
radar:
  max_markets_per_ingest: 50
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'resolution.db'}")
    monkeypatch.setenv("CODEX_API_KEY", "test-key")
    get_settings.cache_clear()
    get_session_factory.cache_clear()

    codex_requests: list[dict] = []

    def codex_handler(request: Request) -> Response:
        decoded = json.loads(request.read())
        codex_requests.append(decoded)
        return Response(
            200,
            json={
                "data": {
                    "filterPredictionMarkets": {
                        "results": [
                            {
                                "id": "row-1",
                                "eventLabel": "BTC",
                                "status": "RESOLVED",
                                "resolution": {
                                    "resolvedOutcomeIndex": 0,
                                    "resolvedLabel": "Yes",
                                },
                                "market": {
                                    "id": "market-external",
                                    "eventId": "event-external",
                                    "protocol": "POLYMARKET",
                                    "label": "BTC above 80000",
                                    "question": "Will BTC be above $80,000?",
                                    "status": "RESOLVED",
                                    "closesAt": "2026-07-01T00:00:00Z",
                                    "resolvesAt": "2026-07-01T01:00:00Z",
                                },
                                "outcome0": {
                                    "label": "Yes",
                                    "bestAskCT": "1",
                                    "bestBidCT": "1",
                                    "lastPriceCT": "1",
                                },
                                "outcome1": {
                                    "label": "No",
                                    "bestAskCT": "0",
                                    "bestBidCT": "0",
                                    "lastPriceCT": "0",
                                },
                            }
                        ]
                    }
                }
            },
        )

    mock_http_client = AsyncClient(transport=MockTransport(codex_handler))
    codex_client = CodexClient(
        endpoint="https://codex.test/graphql",
        api_key="test-key",
        usage_recorder=DatabaseUsageRecorder(),
        http_client=mock_http_client,
    )

    sessionmaker = get_session_factory()
    try:
        async with sessionmaker.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            venue = Venue(code="POLYMARKET", name="Polymarket")
            account = PaperAccount(
                name="Default",
                starting_cash=Decimal("10000"),
                cash=Decimal("9996"),
            )
            session.add_all([venue, account])
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="event-external",
                protocol="POLYMARKET",
                question="Will BTC be above $80,000?",
                categories=["crypto"],
                status="CLOSED",
                closes_at=datetime.now(UTC) - timedelta(hours=2),
            )
            session.add(event)
            await session.flush()
            market = PredictionMarket(
                event_id=event.id,
                venue_id=venue.id,
                external_market_id="market-external",
                protocol="POLYMARKET",
                question=event.question,
                status="CLOSED",
                closes_at=event.closes_at,
            )
            session.add(market)
            await session.flush()
            position = PaperPosition(
                account_id=account.id,
                market_id=market.id,
                outcome_index=0,
                quantity=Decimal("10"),
                avg_price=Decimal("0.40"),
                mark_price=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                status="open",
            )
            session.add(position)
            await session.commit()

            processed = await poll_resolutions(session, client=codex_client)
            await session.commit()

            await session.refresh(account)
            await session.refresh(position)
            refreshed_market = await session.get(PredictionMarket, market.id)
            resolution = await session.scalar(select(MarketResolution))
            ledger = await session.scalar(select(ApiUsageLedger))

        assert processed == 1
        assert codex_requests[0]["variables"]["eventIds"] == ["event-external"]
        assert refreshed_market is not None
        assert refreshed_market.raw_json["resolution"]["resolvedOutcomeIndex"] == 0
        assert resolution is not None
        assert resolution.status == "resolved"
        assert position.status == "closed"
        assert account.cash == Decimal("10006.00000000")
        assert ledger is not None
        assert ledger.kind == "resolution"
        assert ledger.metadata_json["fetch_profile"] == "light"
    finally:
        await codex_client.aclose()
        await mock_http_client.aclose()
        await sessionmaker.bind.dispose()
        get_session_factory.cache_clear()
        get_settings.cache_clear()
