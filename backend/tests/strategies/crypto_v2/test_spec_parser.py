from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.strategies.crypto_v2.spec_parser import CryptoMarketSpecParserV2


def test_parse_btc_close_above() -> None:
    closes_at = datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC)
    result = CryptoMarketSpecParserV2().parse(
        _market("m1", "Will Bitcoin be above $110,000 on July 31, 2026?", closes_at=closes_at),
        _event("e1"),
    )

    assert not result.failed
    assert result.spec is not None
    assert result.spec.asset == "BTC"
    assert result.spec.protocol == "POLYMARKET"
    assert result.spec.market_type == "close_above"
    assert result.spec.threshold == Decimal("110000")
    assert result.spec.window_end == closes_at
    assert result.spec.parser_confidence >= 0.85
    assert result.spec.ambiguity_flags == []


def test_parse_eth_close_below() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market(
            "m2",
            "Will ETH close below 3.5k by July 31, 2026?",
            closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        ),
        _event("e2"),
    )

    assert not result.failed
    assert result.spec is not None
    assert result.spec.asset == "ETH"
    assert result.spec.market_type == "close_below"
    assert result.spec.threshold == Decimal("3500")


def test_parse_sol_hit_above() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market(
            "m3",
            "Will Solana reach $220 before July 31, 2026?",
            closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        ),
        _event("e3"),
    )

    assert not result.failed
    assert result.spec is not None
    assert result.spec.asset == "SOL"
    assert result.spec.market_type == "hit_above"
    assert result.spec.threshold == Decimal("220")
    assert result.spec.parser_confidence >= 0.90


def test_parse_btc_hit_below() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market(
            "m4",
            "Will BTC fall below $95k before July 31, 2026?",
            closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        ),
        _event("e4"),
    )

    assert not result.failed
    assert result.spec is not None
    assert result.spec.asset == "BTC"
    assert result.spec.market_type == "hit_below"
    assert result.spec.threshold == Decimal("95000")


def test_parse_range_close() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market(
            "m5",
            "Will BTC be between $100k and $110k on July 31, 2026?",
            closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        ),
        _event("e5"),
    )

    assert not result.failed
    assert result.spec is not None
    assert result.spec.market_type == "range_close"
    assert result.spec.lower_threshold == Decimal("100000")
    assert result.spec.upper_threshold == Decimal("110000")
    assert result.spec.threshold is None


def test_reject_no_deadline() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m6", "Will BTC be above $110,000?", closes_at=None),
        _event("e6", closes_at=None),
    )

    assert result.failed
    assert result.spec is None
    assert "NO_DEADLINE" in result.ambiguity_flags


def test_reject_no_threshold() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m7", "Will Ethereum trend higher by July 31, 2026?"),
        _event("e7"),
    )

    assert result.failed
    assert "NO_THRESHOLD" in result.ambiguity_flags


def test_reject_multi_asset_condition() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m8", "Will BTC be above $110k and ETH be above $4k on July 31, 2026?"),
        _event("e8"),
    )

    assert result.failed
    assert "MULTI_ASSET_CONDITION" in result.ambiguity_flags


def test_reject_market_cap_metric() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m9", "Will Bitcoin market cap be above $2T by July 31, 2026?"),
        _event("e9"),
    )

    assert result.failed
    assert "MARKET_CAP_METRIC" in result.ambiguity_flags


def test_reject_ath_market_initially() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m10", "Will BTC make a new all-time high before July 31, 2026?"),
        _event("e10"),
    )

    assert result.failed
    assert "ATH_REQUIRES_HISTORY" in result.ambiguity_flags


def test_reject_unclear_resolution_source() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market(
            "m11",
            "Will BTC be above $110,000 on July 31, 2026?",
            closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
            resolution_source=None,
        ),
        _event("e11"),
    )

    assert result.failed
    assert "UNCLEAR_RESOLUTION_SOURCE" in result.ambiguity_flags


def test_reject_question_deadline_without_market_timestamp_as_unclear_timezone() -> None:
    result = CryptoMarketSpecParserV2().parse(
        _market("m12", "Will BTC be above $110,000 on July 31, 2026?", closes_at=None),
        _event("e12", closes_at=None),
    )

    assert result.failed
    assert "UNCLEAR_TIMEZONE" in result.ambiguity_flags


def _market(
    market_id: str,
    question: str,
    closes_at: datetime | None = None,
    resolution_source: str | None = "Polymarket rules",
):
    return SimpleNamespace(
        id=market_id,
        event_id="event-id",
        protocol="POLYMARKET",
        question=question,
        closes_at=closes_at,
        resolution_source=resolution_source,
        raw_json={"id": market_id},
    )


def _event(event_id: str, closes_at: datetime | None = None):
    return SimpleNamespace(
        id=event_id,
        protocol="POLYMARKET",
        question="Crypto event",
        closes_at=closes_at,
        raw_json={"id": event_id},
    )
