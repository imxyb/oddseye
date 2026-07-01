from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.codex.client import CodexClient
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import (
    JobRun,
    MarketOutcome,
    MarketSnapshot,
    PredictionCategory,
    PredictionEvent,
    PredictionMarket,
    Venue,
)
from app.normalizer.prediction_market import normalize_event, normalize_market
from app.scoring.market_quality import QualityInputs, compute_market_quality
from app.services.bootstrap import ensure_default_venues
from app.services.usage import DatabaseUsageRecorder


def create_codex_client() -> CodexClient:
    settings = get_settings()
    return CodexClient(
        endpoint=settings.config.codex.endpoint,
        api_key=settings.codex_api_key,
        usage_recorder=DatabaseUsageRecorder(),
        timeout_seconds=settings.config.codex.timeout_seconds,
        max_retries=settings.config.codex.max_retries,
    )


@asynccontextmanager
async def job_run(session: AsyncSession, job_name: str) -> AsyncIterator[JobRun]:
    run = JobRun(job_name=job_name, started_at=utcnow(), status="running")
    session.add(run)
    await session.flush()
    try:
        yield run
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = utcnow()
        raise
    else:
        run.status = "success"
        run.finished_at = utcnow()


async def refresh_categories(
    session: AsyncSession, client: CodexClient | None = None, job_run_id: str | None = None
) -> int:
    if client is None and not get_settings().codex_api_key:
        return 0
    client = client or create_codex_client()
    data = await client.prediction_categories(job_run_id=job_run_id)
    categories = data.get("predictionCategories") or []
    count = 0
    for item in _flatten_categories(categories):
        existing = await session.scalar(
            select(PredictionCategory).where(PredictionCategory.slug == item["slug"])
        )
        if existing is None:
            session.add(PredictionCategory(**item))
        else:
            existing.name = item["name"]
            existing.parent_slug = item["parent_slug"]
            existing.raw_json = item["raw_json"]
            existing.updated_at = utcnow()
        count += 1
    return count


async def discover_events(
    session: AsyncSession, client: CodexClient | None = None, job_run_id: str | None = None
) -> int:
    settings = get_settings()
    if client is None and not settings.codex_api_key:
        return 0
    await ensure_default_venues(session)
    client = client or create_codex_client()
    data = await client.discover_events(
        categories=settings.config.radar.enabled_categories,
        limit=settings.config.radar.max_markets_per_ingest,
        offset=0,
        job_run_id=job_run_id,
    )
    rows = ((data.get("filterPredictionEvents") or {}).get("results")) or []
    count = 0
    for row in rows:
        normalized = normalize_event(row)
        venue = await _venue_for_protocol(session, normalized.protocol)
        existing = await session.scalar(
            select(PredictionEvent).where(
                PredictionEvent.venue_id == venue.id,
                PredictionEvent.external_event_id == normalized.external_event_id,
            )
        )
        if existing is None:
            session.add(
                PredictionEvent(
                    venue_id=venue.id,
                    external_event_id=normalized.external_event_id,
                    protocol=normalized.protocol,
                    slug=normalized.slug,
                    question=normalized.question,
                    description=normalized.description,
                    categories=normalized.categories,
                    status=normalized.status,
                    venue_url=normalized.venue_url,
                    image_thumb_url=normalized.image_thumb_url,
                    closes_at=normalized.closes_at,
                    resolves_at=normalized.resolves_at,
                    market_count=normalized.market_count,
                    raw_json=normalized.raw_json,
                )
            )
        else:
            existing.status = normalized.status
            existing.categories = normalized.categories
            existing.market_count = normalized.market_count
            existing.updated_at = utcnow()
            existing.raw_json = normalized.raw_json
        count += 1
    return count


async def sync_event_markets(
    session: AsyncSession,
    event_ids: list[str],
    client: CodexClient | None = None,
    job_run_id: str | None = None,
) -> int:
    settings = get_settings()
    if client is None and not settings.codex_api_key:
        return 0
    if not event_ids:
        return 0
    await ensure_default_venues(session)
    client = client or create_codex_client()
    data = await client.event_markets(
        event_ids, limit=settings.config.radar.max_markets_per_ingest, job_run_id=job_run_id
    )
    rows = ((data.get("filterPredictionMarkets") or {}).get("results")) or []
    count = 0
    for row in rows:
        normalized = normalize_market(row)
        venue = await _venue_for_protocol(session, normalized.protocol)
        event = await session.scalar(
            select(PredictionEvent).where(
                PredictionEvent.venue_id == venue.id,
                PredictionEvent.external_event_id == normalized.external_event_id,
            )
        )
        if event is None:
            continue
        market = await session.scalar(
            select(PredictionMarket).where(
                PredictionMarket.venue_id == venue.id,
                PredictionMarket.external_market_id == normalized.external_market_id,
            )
        )
        if market is None:
            market = PredictionMarket(
                event_id=event.id,
                venue_id=venue.id,
                external_market_id=normalized.external_market_id,
                protocol=normalized.protocol,
                label=normalized.label,
                question=normalized.question,
                status=normalized.status,
                image_thumb_url=normalized.image_thumb_url,
                closes_at=normalized.closes_at,
                resolves_at=normalized.resolves_at,
                raw_json=normalized.raw_json,
            )
            session.add(market)
            await session.flush()
        else:
            market.status = normalized.status
            market.raw_json = normalized.raw_json
            market.updated_at = utcnow()
        for outcome in normalized.outcomes:
            await _upsert_outcome(session, market.id, outcome)
        await _insert_snapshot(session, market, event, normalized.snapshot, normalized.raw_json)
        count += 1
    return count


async def compute_quality_for_latest_snapshots(session: AsyncSession) -> int:
    rows = await session.execute(
        select(PredictionMarket, PredictionEvent, MarketSnapshot)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .join(MarketSnapshot, MarketSnapshot.market_id == PredictionMarket.id)
        .order_by(MarketSnapshot.ts.desc())
    )
    seen: set[str] = set()
    count = 0
    for market, event, snapshot in rows.all():
        if market.id in seen:
            continue
        seen.add(market.id)
        quality = compute_market_quality(
            QualityInputs(
                question=market.question,
                description=event.description,
                categories=event.categories or [],
                status=market.status,
                venue_url=event.venue_url,
                closes_at=market.closes_at,
                resolves_at=market.resolves_at,
                liquidity_usd=_float(snapshot.liquidity_usd),
                spread_ct=_float(snapshot.outcome0_spread),
                volume_usd_24h=_float(snapshot.volume_usd_24h),
                trades_24h=_float(snapshot.trades_24h),
            ),
            now=utcnow(),
        )
        snapshot.market_quality_score = Decimal(str(quality.score))
        raw = dict(snapshot.raw_json or {})
        raw["quality"] = {
            "components": quality.components,
            "reason_codes": quality.reason_codes,
            "risk_flags": quality.risk_flags,
            "passes_paper_gate": quality.passes_paper_gate,
        }
        snapshot.raw_json = raw
        count += 1
    return count


async def _venue_for_protocol(session: AsyncSession, protocol: str) -> Venue:
    code = protocol.upper()
    venue = await session.scalar(select(Venue).where(Venue.code == code))
    if venue is None:
        venue = Venue(code=code, name=code.title(), supports_execution=False)
        session.add(venue)
        await session.flush()
    return venue


async def _upsert_outcome(session: AsyncSession, market_id: str, outcome: dict[str, Any]) -> None:
    existing = await session.scalar(
        select(MarketOutcome).where(
            MarketOutcome.market_id == market_id,
            MarketOutcome.outcome_index == outcome["outcome_index"],
        )
    )
    if existing is None:
        session.add(MarketOutcome(market_id=market_id, **outcome))
    else:
        existing.label = outcome["label"]
        existing.side = outcome["side"]
        existing.raw_json = outcome["raw_json"]


async def _insert_snapshot(
    session: AsyncSession,
    market: PredictionMarket,
    event: PredictionEvent,
    snapshot: dict[str, Any],
    raw_json: dict[str, Any],
) -> None:
    quality = compute_market_quality(
        QualityInputs(
            question=market.question,
            description=event.description,
            categories=event.categories or [],
            status=market.status,
            venue_url=event.venue_url,
            closes_at=market.closes_at,
            resolves_at=market.resolves_at,
            liquidity_usd=_float(snapshot.get("liquidity_usd")),
            spread_ct=_float(snapshot.get("outcome0_spread")),
            volume_usd_24h=_float(snapshot.get("volume_usd_24h")),
            trades_24h=_float(snapshot.get("trades_24h")),
        ),
        now=utcnow(),
    )
    session.add(
        MarketSnapshot(
            market_id=market.id,
            ts=utcnow(),
            market_quality_score=Decimal(str(quality.score)),
            raw_json={
                **raw_json,
                "quality": {
                    "components": quality.components,
                    "reason_codes": quality.reason_codes,
                    "risk_flags": quality.risk_flags,
                    "passes_paper_gate": quality.passes_paper_gate,
                },
            },
            **{key: value for key, value in snapshot.items() if not key.endswith("_side")},
        )
    )


def _flatten_categories(
    categories: list[dict[str, Any]], parent_slug: str | None = None
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for category in categories:
        item = {
            "slug": category["slug"],
            "name": category["name"],
            "parent_slug": parent_slug,
            "raw_json": category,
        }
        items.append(item)
        items.extend(_flatten_categories(category.get("subcategories") or [], category["slug"]))
    return items


def _float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
