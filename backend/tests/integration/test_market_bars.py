from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Request, Response
from sqlalchemy import func, select

from app.codex.client import CodexClient
from app.core.config import get_settings
from app.db.models import ApiUsageLedger, MarketSnapshot, PredictionEvent, PredictionMarket, Venue
from app.db.session import Base, create_sessionmaker, get_session_factory
from app.main import create_app
from app.services.usage import DatabaseUsageRecorder
from app.services.market_data import market_bars


@pytest.mark.asyncio
async def test_market_bars_respects_range_filter(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'bars.db'}")
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
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(days=2),
                    outcome0_best_bid=Decimal("0.40"),
                    outcome0_best_ask=Decimal("0.42"),
                ),
                MarketSnapshot(
                    market_id=market.id,
                    ts=datetime.now(UTC) - timedelta(hours=1),
                    outcome0_best_bid=Decimal("0.50"),
                    outcome0_best_ask=Decimal("0.52"),
                ),
            ]
        )
        await session.commit()

        response = await market_bars(session, market.id, range_name="24h", resolution="min15")

        assert response["source"] == "local_snapshots"
        assert len(response["bars"]) == 1
        assert response["bars"][0]["yes_bid"] == 0.5
    await sessionmaker.bind.dispose()


@pytest.mark.asyncio
async def test_market_manual_refresh_syncs_current_event_and_records_usage(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
app:
  timezone: UTC
auth:
  users:
    - username: biaoge
      password_hash: "$2b$12$0cgzVSQfBizQZRtksMnXk.sDshczF94EfjA9Ctz/G0RiMziWV.oEK"
      role: admin
codex:
  fetch_profile: light
radar:
  max_markets_per_ingest: 50
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'refresh.db'}")
    monkeypatch.setenv("CODEX_API_KEY", "test-key")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()
    get_session_factory.cache_clear()

    codex_requests: list[dict] = []

    def codex_handler(request: Request) -> Response:
        payload = request.read()
        import json

        decoded = json.loads(payload)
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
                                    "id": "market-external",
                                    "eventId": "event-external",
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
                                    "spreadCT": "0.02",
                                    "lastPriceCT": "0.60",
                                    "liquidityCT": "2000",
                                    "volumeUsd24h": "1000",
                                },
                                "outcome1": {
                                    "label": "No",
                                    "bestAskCT": "0.41",
                                    "bestBidCT": "0.39",
                                    "spreadCT": "0.02",
                                    "lastPriceCT": "0.40",
                                    "liquidityCT": "1500",
                                    "volumeUsd24h": "800",
                                },
                                "liquidityUsd": "12000",
                                "openInterestUsd": "15000",
                                "volumeUsd24h": "5000",
                                "trades24h": "70",
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

    app = create_app()
    sessionmaker = get_session_factory()
    try:
        async with sessionmaker.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessionmaker() as session:
            venue = Venue(code="POLYMARKET", name="Polymarket")
            session.add(venue)
            await session.flush()
            event = PredictionEvent(
                venue_id=venue.id,
                external_event_id="event-external",
                protocol="POLYMARKET",
                question="Will BTC be above $80,000?",
                categories=["crypto"],
                status="OPEN",
            )
            session.add(event)
            await session.flush()
            session.add(
                PredictionMarket(
                    id="00000000-0000-0000-0000-000000000001",
                    event_id=event.id,
                    venue_id=venue.id,
                    external_market_id="market-external",
                    protocol="POLYMARKET",
                    question=event.question,
                    status="OPEN",
                )
            )
            await session.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post("/auth/login", json={"username": "biaoge", "password": "password"})
            token = login.json()["access_token"]
            response = await client.post(
                "/markets/00000000-0000-0000-0000-000000000001/refresh",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert response.json()["records_processed"] == 1
        assert codex_requests[0]["variables"]["eventIds"] == ["event-external"]
        async with sessionmaker() as session:
            snapshot_count = await session.scalar(
                select(func.count()).select_from(MarketSnapshot)
            )
            ledger = await session.scalar(select(ApiUsageLedger))

        assert snapshot_count == 1
        assert ledger is not None
        assert ledger.kind == "manual_refresh"
        assert ledger.metadata_json["market_count"] == 1
        assert ledger.metadata_json["fetch_profile"] == "light"
    finally:
        await codex_client.aclose()
        await mock_http_client.aclose()
        await sessionmaker.bind.dispose()
        get_session_factory.cache_clear()
        get_settings.cache_clear()
