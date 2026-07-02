from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.core.time import utcnow
from app.db.models import MarketSnapshot, PredictionMarket
from app.normalizer.prediction_market import coerce_token_ids
from app.strategies.crypto_v2.spec import PredictionOrderBookSnapshot


class PolymarketClobClient:
    def __init__(
        self,
        base_url: str = "https://clob.polymarket.com",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: int = 5,
    ):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds, trust_env=False)
        self._owns_http_client = http_client is None

    async def get_orderbook(self, token_id: str) -> dict[str, Any] | None:
        response = await self.http_client.get(f"{self.base_url}/book", params={"token_id": token_id})
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http_client.aclose()


class PredictionOrderBookService:
    def __init__(
        self,
        clob_client: Any | None = None,
        use_direct_clob: bool = True,
    ):
        self.clob_client = clob_client
        self.use_direct_clob = use_direct_clob

    async def get_orderbook(
        self,
        market: PredictionMarket,
        snapshot: MarketSnapshot,
        outcome: str,
    ) -> PredictionOrderBookSnapshot:
        outcome = outcome.upper()
        token_id = _token_id_for_outcome(market, outcome)
        if self.use_direct_clob and token_id:
            try:
                clob_client = self.clob_client or PolymarketClobClient()
                raw_book = await clob_client.get_orderbook(token_id)
            except Exception:
                raw_book = None
            direct = _snapshot_from_clob_book(market, snapshot, outcome, token_id, raw_book)
            if direct is not None:
                return direct

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
            token_id=token_id,
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


def _snapshot_from_clob_book(
    market: PredictionMarket,
    snapshot: MarketSnapshot,
    outcome: str,
    token_id: str,
    raw_book: dict[str, Any] | None,
) -> PredictionOrderBookSnapshot | None:
    if not raw_book:
        return None
    best_bid = _first_decimal(raw_book, "best_bid", "bestBid", "bid")
    best_ask = _first_decimal(raw_book, "best_ask", "bestAsk", "ask")
    best_bid_size = _first_decimal(raw_book, "best_bid_size", "bestBidSize", "bid_size")
    best_ask_size = _first_decimal(raw_book, "best_ask_size", "bestAskSize", "ask_size")
    bids = raw_book.get("bids") if isinstance(raw_book.get("bids"), list) else []
    asks = raw_book.get("asks") if isinstance(raw_book.get("asks"), list) else []
    if best_bid is None and bids:
        bid_levels = [_price_size(level) for level in bids]
        bid_levels = [level for level in bid_levels if level[0] is not None]
        if bid_levels:
            best_bid, best_bid_size = max(bid_levels, key=lambda level: level[0] or Decimal("0"))
    if best_ask is None and asks:
        ask_levels = [_price_size(level) for level in asks]
        ask_levels = [level for level in ask_levels if level[0] is not None]
        if ask_levels:
            best_ask, best_ask_size = min(ask_levels, key=lambda level: level[0] or Decimal("1"))
    if best_bid is None and best_ask is None:
        return None
    spread = _first_decimal(raw_book, "spread")
    if spread is None and best_bid is not None and best_ask is not None:
        spread = abs(best_ask - best_bid)
    mid = (
        ((best_bid + best_ask) / Decimal("2"))
        if best_bid is not None and best_ask is not None
        else None
    )
    depth_to_10_usd = _first_decimal(raw_book, "depth_to_10_usd", "depthTo10Usd")
    depth_to_50_usd = _first_decimal(raw_book, "depth_to_50_usd", "depthTo50Usd")
    depth_to_100_usd = _first_decimal(raw_book, "depth_to_100_usd", "depthTo100Usd")
    fallback_depth = _sum_depth_to_notional(asks, Decimal("100")) or best_ask_size or best_bid_size
    return PredictionOrderBookSnapshot(
        market_id=market.id,
        token_id=token_id,
        outcome=outcome,  # type: ignore[arg-type]
        ts=utcnow(),
        best_bid=best_bid,
        best_ask=best_ask,
        spread=spread,
        mid=mid,
        best_bid_size=best_bid_size,
        best_ask_size=best_ask_size,
        depth_to_10_usd=depth_to_10_usd or fallback_depth,
        depth_to_50_usd=depth_to_50_usd or fallback_depth,
        depth_to_100_usd=depth_to_100_usd or fallback_depth,
        tick_size=_first_decimal(raw_book, "tick_size", "tickSize"),
        min_order_size=_first_decimal(raw_book, "min_order_size", "minOrderSize"),
        book_hash=str(raw_book.get("hash") or raw_book.get("book_hash") or "") or None,
        source="polymarket_clob",
        raw_json={"snapshot_id": snapshot.id, "token_id": token_id, "book": raw_book},
    )


def _token_id_for_outcome(market: PredictionMarket, outcome: str) -> str | None:
    raw = market.raw_json or {}
    outcome_key = "outcome0" if outcome == "YES" else "outcome1"
    token_id = _token_id_from_mapping(raw.get(outcome_key))
    if token_id:
        return token_id
    for container in (raw, raw.get("market") if isinstance(raw.get("market"), dict) else {}):
        for key in ("tokens", "clobTokenIds", "clob_token_ids", "tokenIds", "token_ids"):
            value = container.get(key)
            token_ids = coerce_token_ids(value)
            index = 0 if outcome == "YES" else 1
            if len(token_ids) > index:
                return token_ids[index]
    return None


def _token_id_from_mapping(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in (
        "token_id",
        "tokenId",
        "tokenID",
        "external_token_id",
        "externalTokenId",
        "clob_token_id",
        "clobTokenId",
    ):
        token_id = value.get(key)
        if token_id:
            return str(token_id)
    token = value.get("token")
    if isinstance(token, dict):
        return _token_id_from_mapping(token)
    return None


def _first_decimal(raw: dict[str, Any], *keys: str) -> Decimal | None:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return _decimal(value)
    return None


def _price_size(level: Any) -> tuple[Decimal | None, Decimal | None]:
    if isinstance(level, dict):
        return _decimal(level.get("price")), _decimal(level.get("size"))
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        return _decimal(level[0]), _decimal(level[1])
    return None, None


def _sum_depth_to_notional(levels: list[Any], target: Decimal) -> Decimal | None:
    if not levels:
        return None
    total = Decimal("0")
    for level in levels:
        price, size = _price_size(level)
        if price is None or size is None:
            continue
        total += price * size
        if total >= target:
            return total
    return total or None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
