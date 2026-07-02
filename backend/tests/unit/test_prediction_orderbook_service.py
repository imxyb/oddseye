from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.prediction_orderbook import PredictionOrderBookService


class FakeClobClient:
    async def get_orderbook(self, token_id: str):
        assert token_id == "yes-token"
        return {
            "best_bid": "0.41",
            "best_ask": "0.43",
            "best_bid_size": "90",
            "best_ask_size": "120",
            "depth_to_100_usd": "120",
            "tick_size": "0.01",
            "min_order_size": "5",
            "book_hash": "abc",
            "raw_json": {"source": "fake"},
        }


@pytest.mark.asyncio
async def test_orderbook_service_prefers_direct_clob_when_token_id_is_available() -> None:
    snapshot = SimpleNamespace(
        id=1,
        ts=datetime(2026, 7, 1, tzinfo=UTC),
        outcome0_best_bid=Decimal("0.39"),
        outcome0_best_ask=Decimal("0.45"),
        outcome0_spread=Decimal("0.06"),
        outcome0_liquidity=Decimal("50"),
        outcome1_best_bid=Decimal("0.55"),
        outcome1_best_ask=Decimal("0.61"),
        outcome1_spread=Decimal("0.06"),
        outcome1_liquidity=Decimal("50"),
        liquidity_usd=Decimal("100"),
    )
    market = SimpleNamespace(
        id="market-1",
        raw_json={
            "outcome0": {"token_id": "yes-token"},
            "outcome1": {"token_id": "no-token"},
        },
    )

    orderbook = await PredictionOrderBookService(clob_client=FakeClobClient()).get_orderbook(
        market,
        snapshot,
        "YES",
    )

    assert orderbook.source == "polymarket_clob"
    assert orderbook.token_id == "yes-token"
    assert orderbook.best_bid == Decimal("0.41")
    assert orderbook.best_ask == Decimal("0.43")
    assert orderbook.spread == Decimal("0.02")
    assert orderbook.depth_to_100_usd == Decimal("120")
