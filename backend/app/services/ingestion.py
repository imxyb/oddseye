from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

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
    ApiUsageLedger,
    Venue,
)
from app.normalizer.prediction_market import (
    NormalizedMarket,
    coerce_token_ids,
    normalize_event,
    normalize_market,
    with_clob_token_ids,
)
from app.scoring.market_quality import QualityInputs, compute_market_quality
from app.services.bootstrap import ensure_default_venues
from app.services.polymarket_metadata import PolymarketMarketMetadataClient, PolymarketMarketTokens
from app.services.usage import DatabaseUsageRecorder
from app.strategies.crypto_v2.semantic_parser import SEMANTIC_CACHE_KEY

CODEX_MAX_EVENT_IDS = 200
logger = structlog.get_logger(__name__)
PRESERVED_MARKET_RAW_JSON_KEYS = (SEMANTIC_CACHE_KEY,)


def create_codex_client() -> CodexClient:
    settings = get_settings()
    return CodexClient(
        endpoint=settings.config.codex.endpoint,
        api_key=settings.codex_api_key,
        usage_recorder=DatabaseUsageRecorder(),
        timeout_seconds=settings.config.codex.timeout_seconds,
        max_retries=settings.config.codex.max_retries,
    )


def create_polymarket_metadata_client() -> PolymarketMarketMetadataClient:
    return PolymarketMarketMetadataClient()


@asynccontextmanager
async def job_run(session: AsyncSession, job_name: str) -> AsyncIterator[JobRun]:
    run = JobRun(job_name=job_name, started_at=utcnow(), status="running")
    session.add(run)
    await session.flush()
    run_id = run.id
    await session.commit()
    try:
        yield run
    except Exception as exc:
        await session.rollback()
        persisted_run = await session.get(JobRun, run_id)
        if persisted_run is None:
            raise
        persisted_run.status = "failed"
        persisted_run.error_message = str(exc)
        persisted_run.finished_at = utcnow()
        await session.commit()
        raise
    else:
        persisted_run = await session.get(JobRun, run_id)
        if persisted_run is None:
            raise RuntimeError(f"job run disappeared before completion: {run_id}")
        persisted_run.status = "success"
        persisted_run.finished_at = utcnow()
        persisted_run.codex_requests_used = await _codex_requests_for_run(session, run_id)
        await session.commit()


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


async def _codex_requests_for_run(session: AsyncSession, run_id: str) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(ApiUsageLedger.request_count), 0)).where(
            ApiUsageLedger.job_run_id == run_id
        )
    )
    return int(result.scalar_one() or 0)


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
        protocols=settings.config.radar.protocols,
        limit=settings.config.radar.max_markets_per_ingest,
        offset=0,
        job_run_id=job_run_id,
    )
    rows = ((data.get("filterPredictionEvents") or {}).get("results")) or []
    count = 0
    for row in rows:
        normalized = normalize_event(row)
        if normalized.protocol.upper() != "POLYMARKET":
            continue
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
    kind: str = "market_snapshot",
) -> int:
    settings = get_settings()
    if client is None and not settings.codex_api_key:
        return 0
    if not event_ids:
        return 0
    await ensure_default_venues(session)
    client = client or create_codex_client()
    count = 0
    metadata_client: PolymarketMarketMetadataClient | None = None
    metadata_cache: dict[str, PolymarketMarketTokens | None] = {}
    try:
        for event_id_chunk in _chunks(event_ids, CODEX_MAX_EVENT_IDS):
            data = await client.event_markets(
                event_id_chunk,
                limit=settings.config.radar.max_markets_per_ingest,
                job_run_id=job_run_id,
                kind=kind,
                metadata={"fetch_profile": settings.config.codex.fetch_profile},
            )
            rows = ((data.get("filterPredictionMarkets") or {}).get("results")) or []
            for row in rows:
                normalized = normalize_market(row)
                if normalized.protocol.upper() != "POLYMARKET":
                    continue
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
                if _needs_clob_token_enrichment(normalized):
                    existing_token_ids = await _existing_clob_token_ids(session, market)
                    if existing_token_ids:
                        normalized = with_clob_token_ids(normalized, existing_token_ids)
                    else:
                        if normalized.external_market_id not in metadata_cache:
                            metadata_client = metadata_client or create_polymarket_metadata_client()
                            metadata_cache[normalized.external_market_id] = await _safe_market_tokens(
                                metadata_client,
                                normalized.external_market_id,
                                normalized.raw_json,
                            )
                        tokens = metadata_cache[normalized.external_market_id]
                        if tokens is not None:
                            normalized = with_clob_token_ids(
                                normalized,
                                tokens.token_ids,
                                metadata_raw_json=tokens.raw_json,
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
                        resolution_source=normalized.resolution_source,
                        raw_json=normalized.raw_json,
                    )
                    session.add(market)
                    await session.flush()
                else:
                    market.status = normalized.status
                    market.label = normalized.label
                    market.question = normalized.question
                    market.image_thumb_url = normalized.image_thumb_url
                    market.closes_at = normalized.closes_at
                    market.resolves_at = normalized.resolves_at
                    market.resolution_source = normalized.resolution_source
                    market.raw_json = _preserve_market_raw_json(
                        current=market.raw_json,
                        incoming=normalized.raw_json,
                    )
                    market.updated_at = utcnow()
                for outcome in normalized.outcomes:
                    await _upsert_outcome(session, market.id, outcome)
                await _insert_snapshot(session, market, event, normalized.snapshot, normalized.raw_json)
                count += 1
    finally:
        if metadata_client is not None:
            await metadata_client.aclose()
    return count


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _needs_clob_token_enrichment(normalized: NormalizedMarket) -> bool:
    return any(not outcome.get("external_token_id") for outcome in normalized.outcomes[:2])


def _preserve_market_raw_json(*, current: dict | None, incoming: dict | None) -> dict:
    merged = dict(incoming or {})
    for key in PRESERVED_MARKET_RAW_JSON_KEYS:
        if current and key in current and key not in merged:
            merged[key] = current[key]
    return merged


async def _existing_clob_token_ids(
    session: AsyncSession,
    market: PredictionMarket | None,
) -> list[str]:
    if market is None:
        return []
    token_ids = coerce_token_ids((market.raw_json or {}).get("clobTokenIds"))
    if len(token_ids) >= 2:
        return token_ids[:2]
    result = await session.execute(
        select(MarketOutcome)
        .where(MarketOutcome.market_id == market.id)
        .order_by(MarketOutcome.outcome_index)
    )
    outcome_token_ids = [outcome.external_token_id for outcome in result.scalars().all()]
    if len(outcome_token_ids) >= 2 and all(outcome_token_ids[:2]):
        return [str(token_id) for token_id in outcome_token_ids[:2]]
    return []


async def _safe_market_tokens(
    metadata_client: PolymarketMarketMetadataClient,
    external_market_id: str,
    raw_json: dict[str, Any],
) -> PolymarketMarketTokens | None:
    try:
        return await metadata_client.get_market_tokens(external_market_id, raw_json)
    except Exception as exc:
        logger.warning(
            "polymarket_metadata_token_enrichment_failed",
            external_market_id=external_market_id,
            error=str(exc),
        )
        return None


async def refresh_market(
    session: AsyncSession,
    market_id: str,
    client: CodexClient | None = None,
    job_run_id: str | None = None,
) -> int | None:
    market = await session.get(PredictionMarket, market_id)
    if market is None:
        return None
    event = await session.get(PredictionEvent, market.event_id)
    if event is None:
        return None
    return await sync_event_markets(
        session,
        [event.external_event_id],
        client=client,
        job_run_id=job_run_id,
        kind="manual_refresh",
    )


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
        existing.external_token_id = outcome.get("external_token_id")
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
