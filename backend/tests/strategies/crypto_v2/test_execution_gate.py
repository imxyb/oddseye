from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.strategies.crypto_v2.execution_gate import ExecutionGateConfig, evaluate_execution_gate
from app.strategies.crypto_v2.spec import (
    CryptoAssetSnapshot,
    CryptoMarketSpec,
    PredictionOrderBookSnapshot,
    ProbabilityEstimate,
)


def test_blocks_stale_spot_data() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now - timedelta(seconds=90)),
        orderbook=_orderbook(now),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("80"),
        now=now,
        config=ExecutionGateConfig(spot_seconds=30),
    )

    assert not decision.allowed
    assert "SPOT_DATA_STALE" in decision.risk_flags


def test_blocks_stale_orderbook() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now - timedelta(seconds=30), source="polymarket_clob"),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("80"),
        now=now,
        config=ExecutionGateConfig(orderbook_seconds=15),
    )

    assert not decision.allowed
    assert "ORDERBOOK_STALE" in decision.risk_flags


def test_uses_snapshot_freshness_for_market_snapshot_orderbook() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now - timedelta(seconds=120), source="market_snapshot"),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("80"),
        now=now,
        config=ExecutionGateConfig(orderbook_seconds=15, market_snapshot_seconds=300),
    )

    assert "ORDERBOOK_STALE" not in decision.risk_flags


def test_blocks_wide_spread() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    orderbook = _orderbook(now, spread=Decimal("0.08"))
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=orderbook,
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("80"),
        now=now,
        config=ExecutionGateConfig(max_spread_ct=0.04),
    )

    assert not decision.allowed
    assert "SPREAD_TOO_WIDE" in decision.risk_flags


def test_blocks_insufficient_depth() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now, depth=Decimal("20")),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("80"),
        intended_notional=Decimal("50"),
        now=now,
        config=ExecutionGateConfig(depth_multiplier=1.5),
    )

    assert not decision.allowed
    assert "INSUFFICIENT_DEPTH" in decision.risk_flags


def test_blocks_low_quality_market() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("50"),
        now=now,
    )

    assert not decision.allowed
    assert "MARKET_QUALITY_BELOW_GATE" in decision.risk_flags


def test_allows_when_edge_and_depth_sufficient() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now),
        estimate=_estimate(),
        side="YES",
        market_quality_score=Decimal("85"),
        intended_notional=Decimal("50"),
        now=now,
    )

    assert decision.allowed
    assert decision.edge_exec >= decision.required_edge
    assert decision.edge_stress >= 0.025
    assert decision.risk_flags == []


def test_touch_market_requires_higher_edge() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    decision = evaluate_execution_gate(
        spec=_spec(now, market_type="hit_above"),
        asset_snapshot=_asset_snapshot(now),
        orderbook=_orderbook(now, ask=Decimal("0.63"), bid=Decimal("0.61"), spread=Decimal("0.02")),
        estimate=_estimate(p=0.70, stress=0.67),
        side="YES",
        market_quality_score=Decimal("85"),
        intended_notional=Decimal("50"),
        now=now,
    )

    assert not decision.allowed
    assert "EDGE_BELOW_REQUIRED" in decision.risk_flags


def _spec(now: datetime, market_type: str = "close_above") -> CryptoMarketSpec:
    return CryptoMarketSpec(
        market_id="m1",
        event_id="e1",
        protocol="POLYMARKET",
        question="Will BTC be above $110,000 on July 31, 2026?",
        asset="BTC",
        quote_currency="USDT",
        metric="spot_price",
        market_type=market_type,
        threshold=Decimal("110000"),
        lower_threshold=None,
        upper_threshold=None,
        window_start=None,
        window_end=now + timedelta(days=7),
        settlement_time=None,
        settlement_timezone=None,
        resolution_source="Polymarket rules",
        parser_confidence=0.91,
        ambiguity_flags=[],
        raw_parse={},
    )


def _asset_snapshot(ts: datetime) -> CryptoAssetSnapshot:
    return CryptoAssetSnapshot(
        asset="BTC",
        ts=ts,
        source="test",
        spot=Decimal("108000"),
        spot_bid=None,
        spot_ask=None,
        spot_mid=Decimal("108000"),
        realized_vol_1d=None,
        realized_vol_3d=None,
        realized_vol_7d=0.48,
        realized_vol_30d=0.48,
        realized_vol_90d=0.48,
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
    ts: datetime,
    ask: Decimal = Decimal("0.50"),
    bid: Decimal = Decimal("0.48"),
    spread: Decimal = Decimal("0.02"),
    depth: Decimal = Decimal("150"),
    source: str = "market_snapshot",
) -> PredictionOrderBookSnapshot:
    return PredictionOrderBookSnapshot(
        market_id="m1",
        token_id=None,
        outcome="YES",
        ts=ts,
        best_bid=bid,
        best_ask=ask,
        spread=spread,
        mid=(bid + ask) / 2,
        best_bid_size=depth,
        best_ask_size=depth,
        depth_to_10_usd=depth,
        depth_to_50_usd=depth,
        depth_to_100_usd=depth,
        tick_size=None,
        min_order_size=None,
        book_hash=None,
        source=source,
        raw_json={},
    )


def _estimate(p: float = 0.70, stress: float = 0.66) -> ProbabilityEstimate:
    return ProbabilityEstimate(
        p_raw=p,
        p_calibrated=p,
        p_low=stress,
        p_high=p,
        model_family="close_lognormal_v2",
        confidence=0.75,
        uncertainty_penalty=0.015,
        diagnostics={},
    )
