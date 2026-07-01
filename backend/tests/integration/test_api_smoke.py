from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.models import MarketOutcome, MarketSnapshot, PredictionEvent, PredictionMarket, Venue
from app.db.session import Base, create_sessionmaker, get_session_factory
from app.main import create_app


@pytest.mark.asyncio
async def test_health_login_radar_settings_and_paper_flow(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        """
app:
  name: prediction-radar-test
  timezone: UTC
auth:
  users:
    - username: biaoge
      password_hash: "$2b$12$0cgzVSQfBizQZRtksMnXk.sDshczF94EfjA9Ctz/G0RiMziWV.oEK"
      role: admin
codex:
  endpoint: "https://graph.codex.io/graphql"
  usage_tracking_enabled: true
  usage_policy: advisory_only
  fetch_profile: light
paper:
  starting_cash: 10000
  slippage_bps: 25
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    get_settings.cache_clear()

    app = create_app()
    sessionmaker = create_sessionmaker()
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker() as session:
        venue = Venue(code="POLYMARKET", name="Polymarket")
        session.add(venue)
        await session.flush()
        event = PredictionEvent(
            venue_id=venue.id,
            external_event_id="event-1",
            protocol="POLYMARKET",
            question="Will BTC be above $80,000 on July 31, 2026?",
            description="This market resolves according to a clear BTC reference price at the listed settlement time.",
            categories=["crypto"],
            status="OPEN",
            venue_url="https://example.com",
            closes_at=datetime.now(UTC) + timedelta(days=20),
            resolves_at=datetime.now(UTC) + timedelta(days=21),
            market_count=1,
        )
        session.add(event)
        await session.flush()
        market = PredictionMarket(
            id="00000000-0000-0000-0000-000000000001",
            event_id=event.id,
            venue_id=venue.id,
            external_market_id="market-1",
            protocol="POLYMARKET",
            label="BTC above 80000",
            question="Will BTC be above $80,000 on July 31, 2026?",
            status="OPEN",
            closes_at=event.closes_at,
            resolves_at=event.resolves_at,
            raw_json={"current_price": 85000, "annualized_volatility": 0.45},
        )
        session.add(market)
        session.add_all(
            [
                MarketOutcome(market_id=market.id, outcome_index=0, label="Yes", side="YES"),
                MarketOutcome(market_id=market.id, outcome_index=1, label="No", side="NO"),
            ]
        )
        session.add(
            MarketSnapshot(
                market_id=market.id,
                ts=datetime.now(UTC),
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
            )
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).json()["status"] == "ok"

        login = await client.post("/auth/login", json={"username": "biaoge", "password": "password"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = await client.get("/auth/me", headers=headers)
        assert me.json()["username"] == "biaoge"

        radar = await client.get("/radar/markets", headers=headers)
        assert radar.status_code == 200
        assert "freshness" in radar.json()
        filtered = await client.get(
            "/radar/markets?minVolume=4000&minLiquidity=20000&maxSpread=0.03&closesWithinHours=1000",
            headers=headers,
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1

        settings_response = await client.get("/settings/usage", headers=headers)
        assert settings_response.status_code == 200
        assert settings_response.json()["fetch_profile"] == "light"

        order = await client.post(
            "/paper/orders",
            headers=headers,
            json={
                "market_id": "00000000-0000-0000-0000-000000000001",
                "side": "BUY",
                "outcome_index": 0,
                "limit_price": "0.58",
                "quantity": "10",
            },
        )
        assert order.status_code in {200, 202}
        review = await client.get("/paper/review", headers=headers)
        assert review.status_code == 200
        assert "strategy_stats" in review.json()
        csv_response = await client.get("/paper/trades.csv", headers=headers)
        assert csv_response.status_code == 200
        assert "signal_id,snapshot_id" in csv_response.text
    await sessionmaker.bind.dispose()
    await get_session_factory().bind.dispose()
    get_session_factory.cache_clear()
