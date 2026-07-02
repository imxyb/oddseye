from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.normalizer.prediction_market import normalize_market, parse_ts


@pytest.mark.parametrize("value", [1_767_225_600, 1_767_225_600_000])
def test_parse_ts_accepts_unix_timestamps(value: int) -> None:
    assert parse_ts(value) == datetime.fromtimestamp(1_767_225_600, tz=UTC)


def test_normalize_market_extracts_resolution_source_from_codex_rules() -> None:
    normalized = normalize_market(
        {
            "id": "row-1",
            "eventLabel": "What price will Bitcoin hit in 2026?",
            "resolutionSource": "Unknown",
            "market": {
                "id": "market-1",
                "eventId": "event-1",
                "protocol": "POLYMARKET",
                "question": "Will Bitcoin reach $100,000 by December 31, 2026?",
                "status": "OPEN",
                "closesAt": "2027-01-01T05:00:00Z",
            },
            "predictionMarket": {
                "rules": (
                    "This market will immediately resolve to \"Yes\" if any Binance 1 minute "
                    "candle for Bitcoin (BTC/USDT) reaches the price specified in the title. "
                    "The resolution source for this market is Binance, specifically the BTC/USDT "
                    "\"High\" prices available at https://www.binance.com/en/trade/BTC_USDT, "
                    "with the chart settings on \"1m\"."
                ),
                "rules2": "",
            },
            "outcome0": {"label": "Yes"},
            "outcome1": {"label": "No"},
        }
    )

    assert normalized.resolution_source is not None
    assert normalized.resolution_source.startswith("The resolution source for this market is Binance")
    assert "BTC/USDT" in normalized.resolution_source


def test_normalize_market_extracts_top_level_clob_token_ids() -> None:
    normalized = normalize_market(
        {
            "id": "row-1",
            "clobTokenIds": ["yes-token", "no-token"],
            "market": {
                "id": "market-1",
                "eventId": "event-1",
                "protocol": "POLYMARKET",
                "question": "Will BTC be above $100,000?",
                "status": "OPEN",
            },
            "outcome0": {"label": "Yes"},
            "outcome1": {"label": "No"},
        }
    )

    assert normalized.outcomes[0]["external_token_id"] == "yes-token"
    assert normalized.outcomes[1]["external_token_id"] == "no-token"


def test_normalize_market_extracts_json_encoded_clob_token_ids() -> None:
    normalized = normalize_market(
        {
            "id": "row-1",
            "market": {
                "id": "market-1",
                "eventId": "event-1",
                "protocol": "POLYMARKET",
                "question": "Will BTC be above $100,000?",
                "status": "OPEN",
                "clobTokenIds": '["yes-token", "no-token"]',
            },
            "outcome0": {"label": "Yes"},
            "outcome1": {"label": "No"},
        }
    )

    assert normalized.outcomes[0]["external_token_id"] == "yes-token"
    assert normalized.outcomes[1]["external_token_id"] == "no-token"
