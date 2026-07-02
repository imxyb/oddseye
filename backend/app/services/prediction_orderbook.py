from __future__ import annotations

from decimal import Decimal

from app.db.models import MarketSnapshot, PredictionMarket
from app.strategies.crypto_v2.spec import PredictionOrderBookSnapshot


class PredictionOrderBookService:
    async def get_orderbook(
        self,
        market: PredictionMarket,
        snapshot: MarketSnapshot,
        outcome: str,
    ) -> PredictionOrderBookSnapshot:
        outcome = outcome.upper()
        if outcome == "YES":
            best_bid = snapshot.outcome0_best_bid
            best_ask = snapshot.outcome0_best_ask
            spread = snapshot.outcome0_spread
            depth = snapshot.outcome0_liquidity or snapshot.liquidity_usd
        else:
            best_bid = snapshot.outcome1_best_bid
            best_ask = snapshot.outcome1_best_ask
            spread = snapshot.outcome1_spread
            depth = snapshot.outcome1_liquidity or snapshot.liquidity_usd
        mid = (
            ((best_bid + best_ask) / Decimal("2"))
            if best_bid is not None and best_ask is not None
            else None
        )
        if spread is None and best_bid is not None and best_ask is not None:
            spread = abs(best_ask - best_bid)
        return PredictionOrderBookSnapshot(
            market_id=market.id,
            token_id=None,
            outcome=outcome,  # type: ignore[arg-type]
            ts=snapshot.ts,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            mid=mid,
            best_bid_size=depth,
            best_ask_size=depth,
            depth_to_10_usd=depth,
            depth_to_50_usd=depth,
            depth_to_100_usd=depth,
            tick_size=None,
            min_order_size=None,
            book_hash=None,
            source="market_snapshot",
            raw_json={"snapshot_id": snapshot.id},
        )
