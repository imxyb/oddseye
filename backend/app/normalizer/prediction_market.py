from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class NormalizedEvent:
    external_event_id: str
    protocol: str
    slug: str | None
    question: str
    description: str | None
    categories: list[str]
    status: str
    venue_url: str | None
    image_thumb_url: str | None
    closes_at: datetime | None
    resolves_at: datetime | None
    market_count: int
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class NormalizedMarket:
    external_market_id: str
    external_event_id: str
    protocol: str
    label: str | None
    question: str
    status: str
    image_thumb_url: str | None
    closes_at: datetime | None
    resolves_at: datetime | None
    outcomes: list[dict[str, Any]]
    snapshot: dict[str, Any]
    raw_json: dict[str, Any]


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, int | float):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def normalize_outcome_label(label: str | None, outcome_index: int) -> tuple[str, str]:
    normalized = (label or "").strip()
    upper = normalized.upper()
    if upper in {"YES", "Y"}:
        return normalized or "Yes", "YES"
    if upper in {"NO", "N"}:
        return normalized or "No", "NO"
    return normalized or f"Outcome {outcome_index}", "UNKNOWN"


def normalize_event(row: dict[str, Any]) -> NormalizedEvent:
    event = row.get("event") or row
    return NormalizedEvent(
        external_event_id=str(event.get("id") or row.get("id")),
        protocol=str(event.get("protocol") or "UNKNOWN"),
        slug=event.get("slug"),
        question=event.get("question") or row.get("eventLabel") or "Untitled event",
        description=event.get("description"),
        categories=list(row.get("categories") or []),
        status=event.get("status") or row.get("status") or "UNKNOWN",
        venue_url=event.get("venueUrl"),
        image_thumb_url=event.get("imageThumbUrl"),
        closes_at=parse_ts(event.get("closesAt")),
        resolves_at=parse_ts(event.get("resolvesAt")),
        market_count=int(row.get("marketCount") or 0),
        raw_json=row,
    )


def normalize_market(row: dict[str, Any]) -> NormalizedMarket:
    market = row.get("market") or row
    outcome0_label, outcome0_side = normalize_outcome_label(
        (row.get("outcome0") or {}).get("label"), 0
    )
    outcome1_label, outcome1_side = normalize_outcome_label(
        (row.get("outcome1") or {}).get("label"), 1
    )
    snapshot = {
        "outcome0_label": outcome0_label,
        "outcome0_side": outcome0_side,
        "outcome0_best_ask": decimal_or_none((row.get("outcome0") or {}).get("bestAskCT")),
        "outcome0_best_bid": decimal_or_none((row.get("outcome0") or {}).get("bestBidCT")),
        "outcome0_spread": decimal_or_none((row.get("outcome0") or {}).get("spreadCT")),
        "outcome0_last_price": decimal_or_none((row.get("outcome0") or {}).get("lastPriceCT")),
        "outcome0_liquidity": decimal_or_none((row.get("outcome0") or {}).get("liquidityCT")),
        "outcome0_volume_usd_24h": decimal_or_none((row.get("outcome0") or {}).get("volumeUsd24h")),
        "outcome1_label": outcome1_label,
        "outcome1_side": outcome1_side,
        "outcome1_best_ask": decimal_or_none((row.get("outcome1") or {}).get("bestAskCT")),
        "outcome1_best_bid": decimal_or_none((row.get("outcome1") or {}).get("bestBidCT")),
        "outcome1_spread": decimal_or_none((row.get("outcome1") or {}).get("spreadCT")),
        "outcome1_last_price": decimal_or_none((row.get("outcome1") or {}).get("lastPriceCT")),
        "outcome1_liquidity": decimal_or_none((row.get("outcome1") or {}).get("liquidityCT")),
        "outcome1_volume_usd_24h": decimal_or_none((row.get("outcome1") or {}).get("volumeUsd24h")),
        "liquidity_usd": decimal_or_none(row.get("liquidityUsd")),
        "open_interest_usd": decimal_or_none(row.get("openInterestUsd")),
        "volume_usd_24h": decimal_or_none(row.get("volumeUsd24h")),
        "trades_24h": decimal_or_none(row.get("trades24h")),
        "competitive_score_24h": decimal_or_none(row.get("competitiveScore24h")),
        "trending_score_24h": decimal_or_none(row.get("trendingScore24h")),
    }
    return NormalizedMarket(
        external_market_id=str(market.get("id") or row.get("id")),
        external_event_id=str(market.get("eventId") or row.get("eventId") or ""),
        protocol=str(market.get("protocol") or "UNKNOWN"),
        label=market.get("label") or row.get("eventLabel"),
        question=market.get("question") or market.get("label") or "Untitled market",
        status=market.get("status") or row.get("status") or "UNKNOWN",
        image_thumb_url=market.get("imageThumbUrl"),
        closes_at=parse_ts(market.get("closesAt")),
        resolves_at=parse_ts(market.get("resolvesAt")),
        outcomes=[
            {"outcome_index": 0, "label": outcome0_label, "side": outcome0_side, "raw_json": row.get("outcome0") or {}},
            {"outcome_index": 1, "label": outcome1_label, "side": outcome1_side, "raw_json": row.get("outcome1") or {}},
        ],
        snapshot=snapshot,
        raw_json=row,
    )
