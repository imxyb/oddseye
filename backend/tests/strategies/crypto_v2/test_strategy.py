from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.strategies.crypto_v2.spec import CryptoAssetSnapshot, CryptoMarketSpec, PredictionOrderBookSnapshot
from app.strategies.crypto_v2.strategy import CryptoThresholdV2Strategy


def test_strategy_blocks_buy_when_existing_exposure_multiplier_exhausts_risk() -> None:
    now = datetime.now(UTC)
    result = CryptoThresholdV2Strategy().evaluate(
        market=SimpleNamespace(id="market-1"),
        event=SimpleNamespace(id="event-1"),
        snapshot=SimpleNamespace(
            id=1,
            market_quality_score=Decimal("90"),
        ),
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        yes_orderbook=_orderbook(now, "YES", ask=Decimal("0.25"), bid=Decimal("0.24")),
        no_orderbook=_orderbook(now, "NO", ask=Decimal("0.74"), bid=Decimal("0.73")),
        current_position=None,
        equity=Decimal("10000"),
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=0.0,
    )

    assert result.signal.action == "BLOCKED"
    assert result.signal.suggested_notional is None
    assert "SIZE_BELOW_MIN_NOTIONAL" in result.signal.risk_flags
    assert result.raw_json["sizing"]["existing_exposure_multiplier"] == 0.0


def test_strategy_trace_records_orderbook_source_and_token_ids() -> None:
    now = datetime.now(UTC)
    result = CryptoThresholdV2Strategy().evaluate(
        market=SimpleNamespace(id="market-1"),
        event=SimpleNamespace(id="event-1"),
        snapshot=SimpleNamespace(
            id=1,
            market_quality_score=Decimal("90"),
        ),
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        yes_orderbook=_orderbook(
            now,
            "YES",
            ask=Decimal("0.25"),
            bid=Decimal("0.24"),
            token_id="yes-token",
        ),
        no_orderbook=_orderbook(
            now,
            "NO",
            ask=Decimal("0.74"),
            bid=Decimal("0.73"),
            token_id="no-token",
        ),
        current_position=None,
        equity=Decimal("10000"),
    )

    orderbook = result.raw_json["prediction_orderbook"]
    assert orderbook["yes_source"] == "polymarket_clob"
    assert orderbook["no_source"] == "polymarket_clob"
    assert orderbook["yes_token_id"] == "yes-token"
    assert orderbook["no_token_id"] == "no-token"


def _spec(now: datetime) -> CryptoMarketSpec:
    return CryptoMarketSpec(
        market_id="market-1",
        event_id="event-1",
        protocol="POLYMARKET",
        question="Will ETH be above $3,000 on July 10, 2026?",
        asset="ETH",
        quote_currency="USDT",
        metric="spot_price",
        market_type="close_above",
        threshold=Decimal("3000"),
        lower_threshold=None,
        upper_threshold=None,
        window_start=None,
        window_end=now + timedelta(days=7),
        settlement_time=None,
        settlement_timezone="UTC",
        resolution_source="Polymarket rules",
        parser_confidence=0.95,
        ambiguity_flags=[],
        raw_parse={},
    )


def _asset_snapshot(now: datetime) -> CryptoAssetSnapshot:
    return CryptoAssetSnapshot(
        asset="ETH",
        ts=now,
        source="test",
        spot=Decimal("3500"),
        spot_bid=None,
        spot_ask=None,
        spot_mid=Decimal("3500"),
        realized_vol_1d=0.35,
        realized_vol_3d=0.35,
        realized_vol_7d=0.35,
        realized_vol_30d=0.35,
        realized_vol_90d=0.35,
        ewma_vol=None,
        momentum_1h=None,
        momentum_4h=None,
        momentum_24h=None,
        momentum_7d=None,
        funding_rate=None,
        funding_zscore=None,
        raw_json={},
    )


def _orderbook(
    now: datetime,
    outcome: str,
    ask: Decimal,
    bid: Decimal,
    token_id: str | None = None,
) -> PredictionOrderBookSnapshot:
    return PredictionOrderBookSnapshot(
        market_id="market-1",
        token_id=token_id or f"{outcome.lower()}-token",
        outcome=outcome,  # type: ignore[arg-type]
        ts=now,
        best_bid=bid,
        best_ask=ask,
        spread=ask - bid,
        mid=(ask + bid) / Decimal("2"),
        best_bid_size=Decimal("10000"),
        best_ask_size=Decimal("10000"),
        depth_to_10_usd=Decimal("10000"),
        depth_to_50_usd=Decimal("10000"),
        depth_to_100_usd=Decimal("10000"),
        tick_size=None,
        min_order_size=None,
        book_hash=None,
        source="polymarket_clob",
        raw_json={},
    )
