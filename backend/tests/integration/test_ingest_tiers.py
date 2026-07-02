from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from types import SimpleNamespace

from httpx import AsyncClient, MockTransport, Request, Response
import pytest
from sqlalchemy import select

from app.codex.client import CodexClient
from app.core.config import get_settings
from app.db.models import (
    ApiUsageLedger,
    JobRun,
    MarketOutcome,
    ModelSignal,
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.db.session import Base, create_sessionmaker, get_session_factory
from app.services.ingestion import sync_event_markets
from app.services.usage import DatabaseUsageRecorder
from app.workers.ingest import _sync_markets, event_ids_for_sync


@pytest.mark.asyncio
async def test_event_ids_for_sync_prioritizes_positions_and_buy_signals(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'tiers.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9900"))
        session.add_all([venue, account])
        await session.flush()

        position_event = await _event(session, venue.id, "position-event", days=5)
        signal_event = await _event(session, venue.id, "signal-event", days=4)
        recent_event = await _event(session, venue.id, "recent-event", days=1)
        position_market = await _market(session, venue.id, position_event)
        signal_market = await _market(session, venue.id, signal_event)
        await _market(session, venue.id, recent_event)
        session.add(
            PaperPosition(
                account_id=account.id,
                market_id=position_market.id,
                outcome_index=0,
                quantity=Decimal("10"),
                avg_price=Decimal("0.50"),
                mark_price=Decimal("0.50"),
                status="open",
            )
        )
        session.add(
            ModelSignal(
                market_id=signal_market.id,
                ts=datetime.now(UTC),
                strategy_code="crypto_threshold_v2",
                action="BUY",
                side="YES",
                executable_price=Decimal("0.50"),
                edge=Decimal("0.10"),
                confidence=Decimal("0.80"),
                reason_codes=[],
                risk_flags=[],
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await session.commit()

        event_ids = await event_ids_for_sync(session, limit=2)

        assert event_ids == ["position-event", "signal-event"]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_event_ids_for_sync_prioritizes_watchlist_before_positions(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'watchlist-tiers.db'}")
    watchlist_path = tmp_path / "watchlist.yaml"
    watchlist_path.write_text(
        """
watchlist:
  event_ids:
    - watch-event
  market_ids: []
  keywords: []
""",
        encoding="utf-8",
    )
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9900"))
        session.add_all([venue, account])
        await session.flush()

        watch_event = await _event(session, venue.id, "watch-event", days=6)
        position_event = await _event(session, venue.id, "position-event", days=5)
        await _market(session, venue.id, watch_event)
        position_market = await _market(session, venue.id, position_event)
        session.add(
            PaperPosition(
                account_id=account.id,
                market_id=position_market.id,
                outcome_index=0,
                quantity=Decimal("10"),
                avg_price=Decimal("0.50"),
                mark_price=Decimal("0.50"),
                status="open",
            )
        )
        await session.commit()

        event_ids = await event_ids_for_sync(
            session,
            limit=2,
            watchlist_path=watchlist_path,
        )

        assert event_ids == ["watch-event", "position-event"]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_event_ids_for_sync_bootstraps_open_polymarket_events_without_markets(
    tmp_path,
) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'fresh-tiers.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        poly = Venue(code="POLYMARKET", name="Polymarket")
        kalshi = Venue(code="KALSHI", name="Kalshi")
        session.add_all([poly, kalshi])
        await session.flush()

        await _event(session, poly.id, "poly-newer", days=3)
        await _event(session, poly.id, "poly-older", days=9)
        await _event(session, kalshi.id, "kalshi-event", days=2, protocol="KALSHI")
        await session.commit()

        event_ids = await event_ids_for_sync(session, limit=2)

        assert event_ids == ["poly-newer", "poly-older"]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_event_ids_for_sync_ignores_non_polymarket_priority_candidates(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'poly-only-tiers.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        poly = Venue(code="POLYMARKET", name="Polymarket")
        kalshi = Venue(code="KALSHI", name="Kalshi")
        account = PaperAccount(name="Default", starting_cash=Decimal("10000"), cash=Decimal("9900"))
        session.add_all([poly, kalshi, account])
        await session.flush()

        poly_event = await _event(session, poly.id, "poly-event", days=5)
        kalshi_event = await _event(session, kalshi.id, "kalshi-position", days=1, protocol="KALSHI")
        kalshi_market = await _market(
            session,
            kalshi.id,
            kalshi_event,
            protocol="KALSHI",
        )
        session.add(
            PaperPosition(
                account_id=account.id,
                market_id=kalshi_market.id,
                outcome_index=0,
                quantity=Decimal("10"),
                avg_price=Decimal("0.50"),
                mark_price=Decimal("0.50"),
                status="open",
            )
        )
        await session.commit()

        event_ids = await event_ids_for_sync(session, limit=1)

        assert event_ids == [poly_event.external_event_id]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_sync_event_markets_chunks_codex_event_ids(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'chunk-events.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        event_ids = [f"event-{index}" for index in range(201)]
        client = FakeChunkingCodexClient()

        count = await sync_event_markets(session, event_ids, client=client)

    assert count == 0
    assert client.calls == [event_ids[:200], event_ids[200:]]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_sync_event_markets_enriches_missing_clob_token_ids(tmp_path, monkeypatch) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'clob-enrichment.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    metadata_client = FakePolymarketMetadataClient()
    monkeypatch.setattr(
        "app.services.ingestion.create_polymarket_metadata_client",
        lambda: metadata_client,
    )
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        await _event(session, venue.id, "event-1", days=7)
        await session.commit()

        count = await sync_event_markets(
            session,
            ["event-1"],
            client=FakeCodexMarketsClient(
                [
                    {
                        "id": "row-1",
                        "eventLabel": "BTC",
                        "status": "OPEN",
                        "market": {
                            "id": "0xabc:Polymarket:0xdef:137",
                            "eventId": "event-1",
                            "protocol": "POLYMARKET",
                            "label": "BTC above 80000",
                            "question": "Will BTC be above $80,000?",
                            "status": "OPEN",
                            "closesAt": "2026-08-01T00:00:00Z",
                            "resolvesAt": "2026-08-02T00:00:00Z",
                        },
                        "outcome0": {
                            "label": "Yes",
                            "bestAskCT": "0.61",
                            "bestBidCT": "0.59",
                        },
                        "outcome1": {
                            "label": "No",
                            "bestAskCT": "0.41",
                            "bestBidCT": "0.39",
                        },
                    }
                ]
            ),
        )

        market = await session.scalar(select(PredictionMarket))
        outcomes = (
            await session.execute(select(MarketOutcome).order_by(MarketOutcome.outcome_index))
        ).scalars().all()

    assert count == 1
    assert metadata_client.calls == ["0xabc:Polymarket:0xdef:137"]
    assert market is not None
    assert market.raw_json["clobTokenIds"] == ["yes-token", "no-token"]
    assert [outcome.external_token_id for outcome in outcomes] == ["yes-token", "no-token"]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_sync_event_markets_reuses_existing_clob_token_ids(tmp_path, monkeypatch) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'clob-reuse.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    metadata_client = FakePolymarketMetadataClient()
    monkeypatch.setattr(
        "app.services.ingestion.create_polymarket_metadata_client",
        lambda: metadata_client,
    )
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        event = await _event(session, venue.id, "event-1", days=7)
        existing_market = await _market(
            session,
            venue.id,
            event,
            external_market_id="0xabc:Polymarket:0xdef:137",
        )
        existing_market.raw_json = {"clobTokenIds": ["old-yes-token", "old-no-token"]}
        await session.commit()

        count = await sync_event_markets(
            session,
            ["event-1"],
            client=FakeCodexMarketsClient([_codex_market_row()]),
        )

        market = await session.scalar(select(PredictionMarket))
        outcomes = (
            await session.execute(select(MarketOutcome).order_by(MarketOutcome.outcome_index))
        ).scalars().all()

    assert count == 1
    assert metadata_client.calls == []
    assert market is not None
    assert market.raw_json["clobTokenIds"] == ["old-yes-token", "old-no-token"]
    assert [outcome.external_token_id for outcome in outcomes] == [
        "old-yes-token",
        "old-no-token",
    ]
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_sync_markets_records_tier_job_and_usage_kind(tmp_path, monkeypatch) -> None:
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
    watchlist_path = tmp_path / "watchlist.yaml"
    watchlist_path.write_text(
        """
watchlist:
  event_ids:
    - watch-event
  market_ids: []
  keywords: []
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'tier-sync.db'}")
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
                                "status": "OPEN",
                                "market": {
                                    "id": "watch-market",
                                    "eventId": "watch-event",
                                    "protocol": "POLYMARKET",
                                    "label": "BTC above 80000",
                                    "question": "Will BTC be above $80,000?",
                                    "status": "OPEN",
                                    "closesAt": "2026-08-01T00:00:00Z",
                                    "resolvesAt": "2026-08-02T00:00:00Z",
                                },
                                "outcome0": {
                                    "label": "Yes",
                                    "bestAskCT": "0.61",
                                    "bestBidCT": "0.59",
                                    "lastPriceCT": "0.60",
                                },
                                "outcome1": {
                                    "label": "No",
                                    "bestAskCT": "0.41",
                                    "bestBidCT": "0.39",
                                    "lastPriceCT": "0.40",
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
    monkeypatch.setattr("app.services.ingestion.create_codex_client", lambda: codex_client)

    sessionmaker = get_session_factory()
    try:
        async with sessionmaker.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            venue = Venue(code="POLYMARKET", name="Polymarket")
            session.add(venue)
            await session.flush()
            event = await _event(session, venue.id, "watch-event", days=7)
            await _market(session, venue.id, event, external_market_id="watch-market")
            await session.commit()

        await _sync_markets(
            limit=1,
            job_name="sync_hot_markets",
            usage_kind="hot_snapshot",
            watchlist_path=watchlist_path,
        )

        async with sessionmaker() as session:
            job = await session.scalar(select(JobRun))
            ledger = await session.scalar(select(ApiUsageLedger))

        assert codex_requests[0]["variables"]["eventIds"] == ["watch-event"]
        assert job is not None
        assert job.job_name == "sync_hot_markets"
        assert job.codex_requests_used == 1
        assert ledger is not None
        assert ledger.kind == "hot_snapshot"
        assert ledger.metadata_json["fetch_profile"] == "light"
    finally:
        await codex_client.aclose()
        await mock_http_client.aclose()
        await sessionmaker.bind.dispose()
        get_session_factory.cache_clear()
        get_settings.cache_clear()


async def _event(
    session,
    venue_id: str,
    external_id: str,
    days: int,
    protocol: str = "POLYMARKET",
) -> PredictionEvent:
    event = PredictionEvent(
        venue_id=venue_id,
        external_event_id=external_id,
        protocol=protocol,
        question=external_id,
        categories=["crypto"],
        status="OPEN",
        closes_at=datetime.now(UTC) + timedelta(days=days),
    )
    session.add(event)
    await session.flush()
    return event


async def _market(
    session,
    venue_id: str,
    event: PredictionEvent,
    external_market_id: str | None = None,
    protocol: str = "POLYMARKET",
) -> PredictionMarket:
    market = PredictionMarket(
        event_id=event.id,
        venue_id=venue_id,
        external_market_id=external_market_id or f"{event.external_event_id}-market",
        protocol=protocol,
        question=event.question,
        status="OPEN",
        closes_at=event.closes_at,
    )
    session.add(market)
    await session.flush()
    return market


class FakeChunkingCodexClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def event_markets(
        self,
        event_ids: list[str],
        **_: object,
    ) -> dict:
        self.calls.append(event_ids)
        return {"filterPredictionMarkets": {"results": []}}


def _codex_market_row() -> dict:
    return {
        "id": "row-1",
        "eventLabel": "BTC",
        "status": "OPEN",
        "market": {
            "id": "0xabc:Polymarket:0xdef:137",
            "eventId": "event-1",
            "protocol": "POLYMARKET",
            "label": "BTC above 80000",
            "question": "Will BTC be above $80,000?",
            "status": "OPEN",
            "closesAt": "2026-08-01T00:00:00Z",
            "resolvesAt": "2026-08-02T00:00:00Z",
        },
        "outcome0": {
            "label": "Yes",
            "bestAskCT": "0.61",
            "bestBidCT": "0.59",
        },
        "outcome1": {
            "label": "No",
            "bestAskCT": "0.41",
            "bestBidCT": "0.39",
        },
    }


class FakeCodexMarketsClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def event_markets(
        self,
        event_ids: list[str],
        **_: object,
    ) -> dict:
        return {"filterPredictionMarkets": {"results": self.rows}}


class FakePolymarketMetadataClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_market_tokens(self, external_market_id: str, raw_json: dict):
        self.calls.append(external_market_id)
        return SimpleNamespace(
            condition_id="0xabc",
            token_ids=["yes-token", "no-token"],
            raw_json={"id": "gamma-market-1"},
        )

    async def aclose(self) -> None:
        pass
