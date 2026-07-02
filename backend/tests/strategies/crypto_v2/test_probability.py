from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.strategies.crypto_v2.probability import (
    close_above_probability,
    close_below_probability,
    estimate_probability,
    range_close_probability,
    touch_probability_mc,
)
from app.strategies.crypto_v2.spec import CryptoAssetSnapshot, CryptoMarketSpec


def test_close_above_probability_increases_with_spot() -> None:
    low_spot = close_above_probability(spot=90, threshold=100, years_to_expiry=0.1, annualized_vol=0.5)
    high_spot = close_above_probability(spot=110, threshold=100, years_to_expiry=0.1, annualized_vol=0.5)

    assert high_spot > low_spot


def test_close_above_probability_decreases_with_threshold() -> None:
    low_threshold = close_above_probability(spot=100, threshold=95, years_to_expiry=0.1, annualized_vol=0.5)
    high_threshold = close_above_probability(spot=100, threshold=110, years_to_expiry=0.1, annualized_vol=0.5)

    assert low_threshold > high_threshold


def test_close_below_is_complement() -> None:
    above = close_above_probability(spot=100, threshold=105, years_to_expiry=0.1, annualized_vol=0.5)
    below = close_below_probability(spot=100, threshold=105, years_to_expiry=0.1, annualized_vol=0.5)

    assert above + below == 1.0


def test_range_probability_between_zero_and_one() -> None:
    probability = range_close_probability(
        spot=100,
        lower_threshold=90,
        upper_threshold=110,
        years_to_expiry=0.1,
        annualized_vol=0.5,
    )

    assert 0.0 <= probability <= 1.0


def test_touch_above_probability_at_least_close_above() -> None:
    close = close_above_probability(spot=100, threshold=120, years_to_expiry=0.1, annualized_vol=0.6)
    touch = touch_probability_mc(
        spot=100,
        threshold=120,
        years_to_expiry=0.1,
        annualized_vol=0.6,
        direction="above",
        n_paths=2_000,
        n_steps=48,
        seed=7,
    )

    assert touch >= close


def test_touch_below_probability_at_least_close_below() -> None:
    close = close_below_probability(spot=100, threshold=80, years_to_expiry=0.1, annualized_vol=0.6)
    touch = touch_probability_mc(
        spot=100,
        threshold=80,
        years_to_expiry=0.1,
        annualized_vol=0.6,
        direction="below",
        n_paths=2_000,
        n_steps=48,
        seed=7,
    )

    assert touch >= close


def test_mc_probability_is_deterministic_with_seed() -> None:
    first = touch_probability_mc(
        spot=100,
        threshold=120,
        years_to_expiry=0.1,
        annualized_vol=0.6,
        direction="above",
        n_paths=1_000,
        n_steps=24,
        seed=42,
    )
    second = touch_probability_mc(
        spot=100,
        threshold=120,
        years_to_expiry=0.1,
        annualized_vol=0.6,
        direction="above",
        n_paths=1_000,
        n_steps=24,
        seed=42,
    )

    assert first == second


def test_probability_stress_outputs_valid_range() -> None:
    now = datetime(2026, 7, 1, tzinfo=UTC)
    spec = CryptoMarketSpec(
        market_id="m1",
        event_id="e1",
        protocol="POLYMARKET",
        question="Will BTC be above $110,000 on July 31, 2026?",
        asset="BTC",
        quote_currency="USDT",
        metric="spot_price",
        market_type="close_above",
        threshold=Decimal("110000"),
        lower_threshold=None,
        upper_threshold=None,
        window_start=None,
        window_end=now + timedelta(days=30),
        settlement_time=None,
        settlement_timezone=None,
        resolution_source="Polymarket rules",
        parser_confidence=0.91,
        ambiguity_flags=[],
        raw_parse={},
    )
    estimate = estimate_probability(
        spec,
        _asset_snapshot(now, spot=Decimal("108000"), vol=0.48),
        now=now,
        market_mid=0.50,
        spread=0.02,
        mc_paths=1_000,
    )

    assert 0.0 <= estimate.p_low <= 1.0
    assert 0.0 <= estimate.p_calibrated <= 1.0
    assert 0.0 <= estimate.p_high <= 1.0
    assert estimate.p_low <= estimate.p_high or estimate.p_high <= estimate.p_low
    assert estimate.model_family == "close_lognormal_v2"


def _asset_snapshot(now: datetime, spot: Decimal, vol: float) -> CryptoAssetSnapshot:
    return CryptoAssetSnapshot(
        asset="BTC",
        ts=now,
        source="test",
        spot=spot,
        spot_bid=None,
        spot_ask=None,
        spot_mid=spot,
        realized_vol_1d=None,
        realized_vol_3d=None,
        realized_vol_7d=vol,
        realized_vol_30d=vol,
        realized_vol_90d=vol,
        ewma_vol=None,
        momentum_1h=None,
        momentum_4h=None,
        momentum_24h=None,
        momentum_7d=None,
        funding_rate=None,
        funding_zscore=None,
        raw_json={},
    )
