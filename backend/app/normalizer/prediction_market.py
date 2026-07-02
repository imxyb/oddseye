from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
import json
import re
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
    resolution_source: str | None
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


def outcome_token_id(outcome: dict[str, Any]) -> str | None:
    for key in ("token_id", "tokenId", "tokenID", "externalTokenId", "clobTokenId", "clob_token_id"):
        value = outcome.get(key)
        if value:
            return str(value)
    token = outcome.get("token")
    if isinstance(token, dict):
        return outcome_token_id(token)
    return None


def clob_token_ids(row: dict[str, Any]) -> list[str]:
    market = row.get("market") if isinstance(row.get("market"), dict) else {}
    prediction_market = (
        row.get("predictionMarket") if isinstance(row.get("predictionMarket"), dict) else {}
    )
    for container in (row, market, prediction_market):
        if not isinstance(container, dict):
            continue
        for key in ("clobTokenIds", "clob_token_ids", "tokenIds", "token_ids"):
            token_ids = coerce_token_ids(container.get(key))
            if len(token_ids) >= 2:
                return token_ids
    return []


def coerce_token_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            return coerce_token_ids(json.loads(stripped))
        except json.JSONDecodeError:
            return [stripped]
    if isinstance(value, list | tuple):
        token_ids: list[str] = []
        for item in value:
            token_id = outcome_token_id(item) if isinstance(item, dict) else str(item) if item else None
            if token_id:
                token_ids.append(token_id)
        return token_ids
    return []


def with_clob_token_ids(
    normalized: NormalizedMarket,
    token_ids: list[str],
    metadata_raw_json: dict[str, Any] | None = None,
) -> NormalizedMarket:
    if len(token_ids) < 2:
        return normalized
    raw_json = dict(normalized.raw_json or {})
    raw_json["clobTokenIds"] = token_ids[:2]
    if metadata_raw_json:
        raw_json["polymarketMetadata"] = metadata_raw_json
    outcomes: list[dict[str, Any]] = []
    for index, outcome in enumerate(normalized.outcomes):
        enriched = dict(outcome)
        token_id = token_ids[index] if len(token_ids) > index else None
        if token_id and not enriched.get("external_token_id"):
            enriched["external_token_id"] = token_id
        outcome_raw = dict(enriched.get("raw_json") or {})
        if token_id:
            outcome_raw.setdefault("token_id", token_id)
            outcome_raw.setdefault("clobTokenId", token_id)
        enriched["raw_json"] = outcome_raw
        outcomes.append(enriched)
    return replace(normalized, outcomes=outcomes, raw_json=raw_json)


def resolution_source(row: dict[str, Any], market: dict[str, Any]) -> str | None:
    prediction_market = row.get("predictionMarket") or {}
    for value in (
        market.get("resolutionSource"),
        row.get("resolutionSource"),
        market.get("resolution_source"),
        row.get("resolution_source"),
        prediction_market.get("resolutionSource"),
    ):
        source = _clean_resolution_source(value)
        if source:
            return source
    for value in (
        prediction_market.get("rules"),
        prediction_market.get("rules2"),
        market.get("rules"),
        row.get("rules"),
        market.get("resolutionRules"),
        row.get("resolutionRules"),
    ):
        source = _resolution_source_from_rules(value)
        if source:
            return source
    return None


def _clean_resolution_source(value: Any) -> str | None:
    if isinstance(value, list):
        parts = [_clean_resolution_source(item) for item in value]
        joined = ", ".join(part for part in parts if part)
        return joined or None
    if value is None:
        return None
    source = str(value).strip()
    if not source or source.lower() in {"unknown", "none", "null", "n/a", "na"}:
        return None
    return source


def _resolution_source_from_rules(value: Any) -> str | None:
    rules = _clean_resolution_source(value)
    if rules is None:
        return None
    for sentence in re.split(r"(?<=[.!?])\s+", rules):
        if "resolution source" in sentence.lower():
            return sentence.strip()
    return None


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
    row_token_ids = clob_token_ids(row)
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
    outcome0_token_id = outcome_token_id(row.get("outcome0") or {}) or _token_id_at(row_token_ids, 0)
    outcome1_token_id = outcome_token_id(row.get("outcome1") or {}) or _token_id_at(row_token_ids, 1)
    normalized = NormalizedMarket(
        external_market_id=str(market.get("id") or row.get("id")),
        external_event_id=str(market.get("eventId") or row.get("eventId") or ""),
        protocol=str(market.get("protocol") or "UNKNOWN"),
        label=market.get("label") or row.get("eventLabel"),
        question=market.get("question") or market.get("label") or "Untitled market",
        status=market.get("status") or row.get("status") or "UNKNOWN",
        image_thumb_url=market.get("imageThumbUrl"),
        closes_at=parse_ts(market.get("closesAt")),
        resolves_at=parse_ts(market.get("resolvesAt")),
        resolution_source=resolution_source(row, market),
        outcomes=[
            {
                "outcome_index": 0,
                "label": outcome0_label,
                "side": outcome0_side,
                "external_token_id": outcome0_token_id,
                "raw_json": row.get("outcome0") or {},
            },
            {
                "outcome_index": 1,
                "label": outcome1_label,
                "side": outcome1_side,
                "external_token_id": outcome1_token_id,
                "raw_json": row.get("outcome1") or {},
            },
        ],
        snapshot=snapshot,
        raw_json=row,
    )
    return with_clob_token_ids(normalized, row_token_ids) if len(row_token_ids) >= 2 else normalized


def _token_id_at(token_ids: list[str], index: int) -> str | None:
    if len(token_ids) <= index:
        return None
    return token_ids[index]
