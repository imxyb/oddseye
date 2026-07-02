from __future__ import annotations

from decimal import Decimal

from app.strategies.crypto_v2.sizing import SizingConfig, suggested_notional


def test_sizing_zero_when_no_edge() -> None:
    notional = suggested_notional(
        equity=Decimal("10000"),
        p=0.50,
        price=0.55,
        edge_stress=-0.01,
        market_quality_score=85,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=SizingConfig(),
    )

    assert notional == Decimal("0")


def test_sizing_capped_by_max_position_pct() -> None:
    notional = suggested_notional(
        equity=Decimal("10000"),
        p=0.90,
        price=0.20,
        edge_stress=0.25,
        market_quality_score=95,
        parser_confidence=0.98,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=SizingConfig(max_position_pct=0.01, default_paper_notional_cap=Decimal("100")),
    )

    assert notional == Decimal("100.000000")


def test_sizing_reduced_by_low_quality() -> None:
    high = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=95,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=SizingConfig(),
    )
    low = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=65,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=SizingConfig(),
    )

    assert high > low


def test_sizing_reduced_by_touch_market_type() -> None:
    uncapped = SizingConfig(max_position_pct=1.0, default_paper_notional_cap=Decimal("10000"))
    close_size = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=95,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=uncapped,
    )
    touch_size = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=95,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="hit_above",
        config=uncapped,
    )

    assert touch_size < close_size


def test_sizing_reduced_by_existing_exposure() -> None:
    uncapped = SizingConfig(max_position_pct=1.0, default_paper_notional_cap=Decimal("10000"))
    full = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=95,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=1.0,
        market_type="close_above",
        config=uncapped,
    )
    reduced = suggested_notional(
        equity=Decimal("10000"),
        p=0.70,
        price=0.50,
        edge_stress=0.12,
        market_quality_score=95,
        parser_confidence=0.95,
        liquidity_multiplier=1.0,
        existing_exposure_multiplier=0.25,
        market_type="close_above",
        config=uncapped,
    )

    assert reduced == (full * Decimal("0.25")).quantize(Decimal("0.000001"))
