from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.crypto_threshold import (
    CryptoMarketContext,
    CryptoThresholdStrategy,
    parse_crypto_threshold,
)


def test_parse_crypto_threshold_market_extracts_asset_threshold_and_direction() -> None:
    parsed = parse_crypto_threshold("Will BTC be above $80,000 on July 31, 2026?")

    assert parsed is not None
    assert parsed.asset == "BTC"
    assert parsed.condition_type == "close_above"
    assert parsed.threshold == Decimal("80000")
    assert parsed.confidence >= 0.75


def test_strategy_generates_buy_yes_when_model_edge_exceeds_market_ask() -> None:
    strategy = CryptoThresholdStrategy(min_edge=Decimal("0.07"))

    signal = strategy.evaluate(
        CryptoMarketContext(
            market_id="market-1",
            question="Will ETH be above $3000 on July 31, 2026?",
            now=datetime(2026, 7, 1, tzinfo=timezone.utc),
            deadline=datetime(2026, 7, 31, tzinfo=timezone.utc),
            current_price=Decimal("3500"),
            annualized_volatility=Decimal("0.35"),
            yes_ask=Decimal("0.50"),
            no_ask=Decimal("0.53"),
            market_quality_score=Decimal("80"),
            parser_confidence=Decimal("0.86"),
            snapshot_id=1,
        )
    )

    assert signal.action == "BUY"
    assert signal.side == "YES"
    assert signal.edge >= Decimal("0.07")
    assert "MODEL_EDGE_POSITIVE" in signal.reason_codes


def test_strategy_observes_when_quality_or_edge_is_too_low() -> None:
    strategy = CryptoThresholdStrategy(min_edge=Decimal("0.07"))

    signal = strategy.evaluate(
        CryptoMarketContext(
            market_id="market-2",
            question="Will SOL be above $200 on July 31, 2026?",
            now=datetime(2026, 7, 1, tzinfo=timezone.utc),
            deadline=datetime(2026, 7, 31, tzinfo=timezone.utc),
            current_price=Decimal("160"),
            annualized_volatility=Decimal("0.50"),
            yes_ask=Decimal("0.90"),
            no_ask=Decimal("0.12"),
            market_quality_score=Decimal("50"),
            parser_confidence=Decimal("0.86"),
            snapshot_id=2,
        )
    )

    assert signal.action == "OBSERVE"
    assert "QUALITY_BELOW_GATE" in signal.risk_flags
