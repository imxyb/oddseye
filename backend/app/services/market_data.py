from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.core.config import get_settings
from app.services.ingestion import create_codex_client
from app.db.models import (
    MarketOutcome,
    MarketSnapshot,
    ModelSignal,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.services.usage import usage_hint_from_summary, usage_summary

CATEGORY_ALIASES = {
    "economics": {
        "economics",
        "economy",
        "macro",
        "fed",
        "cpi",
        "fomc",
        "inflation",
        "unemployment",
        "rates",
    },
    "macro": {
        "economics",
        "economy",
        "macro",
        "fed",
        "cpi",
        "fomc",
        "inflation",
        "unemployment",
        "rates",
    },
}


async def latest_snapshot_for_market(
    session: AsyncSession, market_id: str
) -> MarketSnapshot | None:
    result = await session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.market_id == market_id)
        .order_by(MarketSnapshot.ts.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def latest_signal_for_market(session: AsyncSession, market_id: str) -> ModelSignal | None:
    now = utcnow()
    result = await session.execute(
        select(ModelSignal)
        .where(ModelSignal.market_id == market_id)
        .where(or_(ModelSignal.expires_at.is_(None), ModelSignal.expires_at > now))
        .order_by(ModelSignal.ts.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def outcomes_for_market(session: AsyncSession, market_id: str) -> list[MarketOutcome]:
    result = await session.execute(
        select(MarketOutcome)
        .where(MarketOutcome.market_id == market_id)
        .order_by(MarketOutcome.outcome_index)
    )
    return list(result.scalars())


async def radar_markets(
    session: AsyncSession,
    category: str | None = None,
    protocol: str | None = None,
    q: str | None = None,
    sort: str = "quality",
    min_quality: float | None = None,
    min_volume: float | None = None,
    min_liquidity: float | None = None,
    max_spread: float | None = None,
    closes_within_hours: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    rows = await session.execute(
        select(PredictionMarket, PredictionEvent, Venue)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .join(Venue, PredictionMarket.venue_id == Venue.id)
    )
    items = []
    newest_snapshot: datetime | None = None
    for market, event, venue in rows.all():
        if category and not _category_matches(category, event.categories or []):
            continue
        if protocol and market.protocol.upper() != protocol.upper():
            continue
        if q and q.lower() not in market.question.lower():
            continue
        snapshot = await latest_snapshot_for_market(session, market.id)
        signal = await latest_signal_for_market(session, market.id)
        if min_quality is not None and (
            snapshot is None
            or snapshot.market_quality_score is None
            or float(snapshot.market_quality_score) < min_quality
        ):
            continue
        if min_volume is not None and (
            snapshot is None
            or snapshot.volume_usd_24h is None
            or float(snapshot.volume_usd_24h) < min_volume
        ):
            continue
        if min_liquidity is not None and (
            snapshot is None
            or snapshot.liquidity_usd is None
            or float(snapshot.liquidity_usd) < min_liquidity
        ):
            continue
        if max_spread is not None and (
            snapshot is None
            or snapshot.outcome0_spread is None
            or float(snapshot.outcome0_spread) > max_spread
        ):
            continue
        if closes_within_hours is not None:
            if market.closes_at is None:
                continue
            seconds_until_close = (_aware(market.closes_at) - utcnow()).total_seconds()
            if seconds_until_close < 0 or seconds_until_close > closes_within_hours * 3600:
                continue
        if snapshot and (newest_snapshot is None or snapshot.ts > newest_snapshot):
            newest_snapshot = snapshot.ts
        items.append(_radar_item(market, event, venue, snapshot, signal))

    items.sort(key=lambda item: _sort_key(item, sort), reverse=sort != "closingSoon")
    total = len(items)
    page = items[offset : offset + limit]
    summary = await usage_summary(session)
    return {
        "items": page,
        "total": total,
        "freshness": _freshness(newest_snapshot, summary),
    }


async def market_detail(session: AsyncSession, market_id: str) -> dict[str, Any] | None:
    row = await session.execute(
        select(PredictionMarket, PredictionEvent, Venue)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .join(Venue, PredictionMarket.venue_id == Venue.id)
        .where(PredictionMarket.id == market_id)
    )
    found = row.one_or_none()
    if found is None:
        return None
    market, event, venue = found
    snapshot = await latest_snapshot_for_market(session, market.id)
    signal = await latest_signal_for_market(session, market.id)
    outcomes = await outcomes_for_market(session, market.id)
    positions = await session.execute(
        select(PaperPosition).where(PaperPosition.market_id == market.id, PaperPosition.status == "open")
    )
    summary = await usage_summary(session)
    item = _radar_item(market, event, venue, snapshot, signal)
    item["description"] = event.description
    item["venue_url"] = event.venue_url
    item["raw_outcomes"] = [
        {
            "index": outcome.outcome_index,
            "label": outcome.label,
            "side": outcome.side,
        }
        for outcome in outcomes
    ]
    position_items = [_position_json(position) for position in positions.scalars()]
    item["positions"] = position_items
    item["current_position"] = position_items[0] if position_items else None
    item["freshness"] = _freshness(snapshot.ts if snapshot else None, summary)
    return item


RANGE_SECONDS = {
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
}

RESOLUTION_SECONDS = {
    "min15": 15 * 60,
    "hour1": 60 * 60,
    "hour4": 4 * 60 * 60,
    "day1": 24 * 60 * 60,
}


async def market_bars(
    session: AsyncSession,
    market_id: str,
    range_name: str = "7d",
    resolution: str = "hour1",
    limit: int = 500,
) -> dict[str, Any]:
    now = utcnow()
    from_dt = None if range_name == "all" else now - timedelta(seconds=RANGE_SECONDS[range_name])
    result = await session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.market_id == market_id)
        .where(MarketSnapshot.ts >= from_dt if from_dt is not None else True)
        .order_by(MarketSnapshot.ts.asc())
        .limit(limit)
    )
    bars = _thin_bars([_snapshot_bar(snapshot) for snapshot in result.scalars()], resolution)
    if bars:
        return {"market_id": market_id, "bars": bars, "source": "local_snapshots"}

    market = await session.get(PredictionMarket, market_id)
    if market is not None and get_settings().codex_api_key:
        try:
            client = create_codex_client()
            from_ts = int((from_dt or now - timedelta(days=365)).timestamp())
            data = await client.market_bars(
                market.external_market_id,
                from_ts=from_ts,
                to_ts=int(now.timestamp()),
                resolution=_codex_resolution(resolution),
            )
            await client.aclose()
            codex = data.get("predictionMarketBars") or {}
            return {
                "market_id": market_id,
                "bars": [_codex_bar(bar) for bar in codex.get("bars") or []],
                "source": "codex",
            }
        except Exception:
            pass
    return {"market_id": market_id, "bars": [], "source": "local_snapshots"}


def _snapshot_bar(snapshot: MarketSnapshot) -> dict[str, Any]:
    return {
        "t": int(snapshot.ts.timestamp()),
        "yes": _ohlc(snapshot.outcome0_last_price, snapshot.outcome0_best_bid, snapshot.outcome0_best_ask),
        "no": _ohlc(snapshot.outcome1_last_price, snapshot.outcome1_best_bid, snapshot.outcome1_best_ask),
        "yes_bid": _decimal(snapshot.outcome0_best_bid),
        "yes_ask": _decimal(snapshot.outcome0_best_ask),
        "volume_usd": _decimal(snapshot.volume_usd_24h),
        "open_interest_usd": _decimal(snapshot.open_interest_usd),
        "trades": _decimal(snapshot.trades_24h),
    }


def _thin_bars(bars: list[dict[str, Any]], resolution: str) -> list[dict[str, Any]]:
    bucket_seconds = RESOLUTION_SECONDS[resolution]
    seen: set[int] = set()
    thinned: list[dict[str, Any]] = []
    for bar in bars:
        bucket = int(bar["t"]) // bucket_seconds
        if bucket in seen:
            thinned[-1] = bar
            continue
        seen.add(bucket)
        thinned.append(bar)
    return thinned


def _codex_resolution(resolution: str) -> str:
    return {
        "min15": "min15",
        "hour1": "hour1",
        "hour4": "hour4",
        "day1": "day1",
    }[resolution]


def _codex_bar(bar: dict[str, Any]) -> dict[str, Any]:
    outcome0 = bar.get("outcome0") or {}
    outcome1 = bar.get("outcome1") or {}
    yes_price = outcome0.get("priceCollateralToken") or {}
    no_price = outcome1.get("priceCollateralToken") or {}
    yes_bid = outcome0.get("bidCollateralToken") or {}
    yes_ask = outcome0.get("askCollateralToken") or {}
    return {
        "t": bar.get("t"),
        "yes": yes_price,
        "no": no_price,
        "yes_bid": yes_bid.get("c"),
        "yes_ask": yes_ask.get("c"),
        "volume_usd": bar.get("volumeUsd"),
        "open_interest_usd": (bar.get("openInterestUsd") or {}).get("c"),
        "trades": bar.get("trades"),
    }


def _radar_item(
    market: PredictionMarket,
    event: PredictionEvent,
    venue: Venue,
    snapshot: MarketSnapshot | None,
    signal: ModelSignal | None,
) -> dict[str, Any]:
    outcomes = [
        {
            "index": 0,
            "label": snapshot.outcome0_label if snapshot else "Outcome 0",
            "bid": _decimal(snapshot.outcome0_best_bid if snapshot else None),
            "ask": _decimal(snapshot.outcome0_best_ask if snapshot else None),
            "spread": _decimal(snapshot.outcome0_spread if snapshot else None),
        },
        {
            "index": 1,
            "label": snapshot.outcome1_label if snapshot else "Outcome 1",
            "bid": _decimal(snapshot.outcome1_best_bid if snapshot else None),
            "ask": _decimal(snapshot.outcome1_best_ask if snapshot else None),
            "spread": _decimal(snapshot.outcome1_spread if snapshot else None),
        },
    ]
    return {
        "market_id": market.id,
        "event_id": event.id,
        "protocol": market.protocol or venue.code,
        "category": (event.categories or ["uncategorized"])[0],
        "categories": event.categories or [],
        "question": market.question,
        "status": market.status,
        "closes_at": market.closes_at.isoformat() if market.closes_at else None,
        "resolves_at": market.resolves_at.isoformat() if market.resolves_at else None,
        "outcomes": outcomes,
        "liquidity_usd": _decimal(snapshot.liquidity_usd if snapshot else None),
        "volume_usd_24h": _decimal(snapshot.volume_usd_24h if snapshot else None),
        "open_interest_usd": _decimal(snapshot.open_interest_usd if snapshot else None),
        "market_quality_score": _decimal(snapshot.market_quality_score if snapshot else None),
        "quality": _quality_json(snapshot),
        "risk_flags": _quality_risk_flags(snapshot),
        "latest_signal": _signal_json(signal) if signal else None,
        "last_snapshot_at": snapshot.ts.isoformat() if snapshot else None,
    }


def _quality_json(snapshot: MarketSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    quality = (snapshot.raw_json or {}).get("quality")
    if not isinstance(quality, dict):
        return None
    return {
        "components": quality.get("components") or {},
        "reason_codes": quality.get("reason_codes") or [],
        "risk_flags": quality.get("risk_flags") or [],
        "passes_paper_gate": bool(quality.get("passes_paper_gate")),
    }


def _quality_risk_flags(snapshot: MarketSnapshot | None) -> list[str]:
    quality = _quality_json(snapshot)
    return list(quality.get("risk_flags") or []) if quality else []


def _category_matches(category: str, categories: list) -> bool:
    wanted = category.lower()
    aliases = CATEGORY_ALIASES.get(wanted, {wanted})
    present = {str(item).lower() for item in categories}
    return bool(aliases.intersection(present))


def _signal_json(signal: ModelSignal) -> dict[str, Any]:
    return {
        "signal_id": signal.id,
        "action": signal.action,
        "side": signal.side,
        "edge": _decimal(signal.edge),
        "confidence": _decimal(signal.confidence),
        "reason_codes": signal.reason_codes,
        "risk_flags": signal.risk_flags,
    }


def _position_json(position: PaperPosition) -> dict[str, Any]:
    return {
        "position_id": position.id,
        "outcome_index": position.outcome_index,
        "quantity": _decimal(position.quantity),
        "avg_price": _decimal(position.avg_price),
        "mark_price": _decimal(position.mark_price),
        "realized_pnl": _decimal(position.realized_pnl),
        "unrealized_pnl": _decimal(position.unrealized_pnl),
        "status": position.status,
    }


def _freshness(last_snapshot_at: datetime | None, summary: dict[str, Any]) -> dict[str, Any]:
    if last_snapshot_at is None:
        age_seconds = None
        is_stale = True
    else:
        age_seconds = max(int((utcnow() - _aware(last_snapshot_at)).total_seconds()), 0)
        is_stale = age_seconds > 900
    return {
        "last_snapshot_at": last_snapshot_at.isoformat() if last_snapshot_at else None,
        "age_seconds": age_seconds,
        "is_stale": is_stale,
        "codex_usage_hint": usage_hint_from_summary(summary),
    }


def _sort_key(item: dict[str, Any], sort: str) -> float:
    if sort == "volume":
        return float(item.get("volume_usd_24h") or 0)
    if sort == "liquidity":
        return float(item.get("liquidity_usd") or 0)
    if sort == "closingSoon":
        value = item.get("closes_at")
        if value is None:
            return float("inf")
        return datetime.fromisoformat(value).timestamp()
    if sort == "edge":
        signal = item.get("latest_signal") or {}
        return float(signal.get("edge") or 0)
    return float(item.get("market_quality_score") or 0)


def _decimal(value: Decimal | int | float | None) -> float | None:
    return None if value is None else float(value)


def _ohlc(last: Decimal | None, bid: Decimal | None, ask: Decimal | None) -> dict[str, float | None]:
    close = last or (bid + ask) / Decimal("2") if bid is not None and ask is not None else last
    return {
        "o": _decimal(close),
        "h": _decimal(max(v for v in [bid, ask, close] if v is not None)) if any(v is not None for v in [bid, ask, close]) else None,
        "l": _decimal(min(v for v in [bid, ask, close] if v is not None)) if any(v is not None for v in [bid, ask, close]) else None,
        "c": _decimal(close),
    }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=utcnow().tzinfo)
    return value
