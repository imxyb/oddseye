from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import MarketSnapshot, ModelSignal, PaperPosition, PredictionEvent, PredictionMarket
from app.db.session import get_session_factory
from app.services.ingestion import (
    compute_quality_for_latest_snapshots,
    discover_events,
    job_run,
    refresh_categories,
    sync_event_markets,
)
from app.services.watchlist import default_watchlist_path, load_watchlist
from app.workers.common import add_interval_job, run_scheduler


async def refresh_categories_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "refresh_categories") as run:
            run.records_processed = await refresh_categories(session, job_run_id=run.id)
        await session.commit()


async def discover_events_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "discover_events") as run:
            run.records_processed = await discover_events(session, job_run_id=run.id)
        await session.commit()


async def sync_hot_markets_job() -> None:
    await _sync_markets(
        limit=get_settings().config.ingestion_tiers.hot_watchlist_max_markets,
        job_name="sync_hot_markets",
        usage_kind="hot_snapshot",
        watchlist_path=default_watchlist_path(),
    )


async def sync_warm_markets_job() -> None:
    await _sync_markets(
        limit=get_settings().config.ingestion_tiers.warm_pool_max_markets,
        job_name="sync_warm_markets",
        usage_kind="warm_snapshot",
    )


async def sync_cold_markets_job() -> None:
    await _sync_markets(
        limit=get_settings().config.ingestion_tiers.cold_pool_max_markets,
        job_name="sync_cold_markets",
        usage_kind="cold_snapshot",
    )


async def compute_quality_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "compute_quality") as run:
            run.records_processed = await compute_quality_for_latest_snapshots(session)
        await session.commit()


async def _sync_markets(
    limit: int,
    job_name: str = "sync_markets",
    usage_kind: str = "market_snapshot",
    watchlist_path: str | Path | None = None,
) -> None:
    async with get_session_factory()() as session:
        async with job_run(session, job_name) as run:
            event_ids = await event_ids_for_sync(
                session,
                limit,
                watchlist_path=watchlist_path,
            )
            run.records_processed = await sync_event_markets(
                session,
                event_ids,
                job_run_id=run.id,
                kind=usage_kind,
            )
        await session.commit()


async def event_ids_for_sync(
    session,
    limit: int,
    watchlist_path: str | Path | None = None,
) -> list[str]:
    event_ids: list[str] = []

    async def append(query) -> None:
        result = await session.execute(query)
        for external_event_id in result.scalars():
            if external_event_id not in event_ids:
                event_ids.append(external_event_id)
            if len(event_ids) >= limit:
                return

    await _append_watchlist_event_ids(session, event_ids, limit, watchlist_path)
    await append(
        select(PredictionEvent.external_event_id)
        .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
        .join(PaperPosition, PaperPosition.market_id == PredictionMarket.id)
        .where(PredictionEvent.status == "OPEN", PaperPosition.status == "open")
        .order_by(PaperPosition.updated_at.desc())
    )
    await append(
        select(PredictionEvent.external_event_id)
        .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
        .join(ModelSignal, ModelSignal.market_id == PredictionMarket.id)
        .where(
            PredictionEvent.status == "OPEN",
            ModelSignal.action == "BUY",
            or_(ModelSignal.expires_at.is_(None), ModelSignal.expires_at > utcnow()),
        )
        .order_by(ModelSignal.edge.desc(), ModelSignal.ts.desc())
    )
    await append(
        select(PredictionEvent.external_event_id)
        .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
        .outerjoin(MarketSnapshot, MarketSnapshot.market_id == PredictionMarket.id)
        .where(PredictionEvent.status == "OPEN")
        .order_by(MarketSnapshot.market_quality_score.desc(), PredictionEvent.updated_at.desc())
    )
    return event_ids[:limit]


async def _append_watchlist_event_ids(
    session,
    event_ids: list[str],
    limit: int,
    watchlist_path: str | Path | None,
) -> None:
    watchlist = load_watchlist(watchlist_path)
    if not watchlist:
        return

    async def append(query) -> None:
        result = await session.execute(query)
        for external_event_id in result.scalars():
            if external_event_id not in event_ids:
                event_ids.append(external_event_id)
            if len(event_ids) >= limit:
                return

    for external_event_id in watchlist["event_ids"]:
        if len(event_ids) >= limit:
            return
        await append(
            select(PredictionEvent.external_event_id).where(
                PredictionEvent.status == "OPEN",
                PredictionEvent.external_event_id == external_event_id,
            )
        )

    for external_market_id in watchlist["market_ids"]:
        if len(event_ids) >= limit:
            return
        await append(
            select(PredictionEvent.external_event_id)
            .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
            .where(
                PredictionEvent.status == "OPEN",
                PredictionMarket.external_market_id == external_market_id,
            )
        )

    for keyword in watchlist["keywords"]:
        if len(event_ids) >= limit:
            return
        like = f"%{keyword}%"
        await append(
            select(PredictionEvent.external_event_id)
            .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
            .where(
                PredictionEvent.status == "OPEN",
                or_(
                    PredictionEvent.question.ilike(like),
                    PredictionMarket.question.ilike(like),
                ),
            )
            .order_by(PredictionEvent.updated_at.desc())
        )

def main() -> None:
    jobs = get_settings().config.jobs
    scheduler = AsyncIOScheduler(timezone=get_settings().config.app.timezone)
    add_interval_job(scheduler, "refresh_categories", 24 * 60 * 60, refresh_categories_job)
    add_interval_job(scheduler, "discover_events", jobs.market_discovery_seconds, discover_events_job)
    add_interval_job(scheduler, "sync_hot_markets", jobs.hot_market_snapshot_seconds, sync_hot_markets_job)
    add_interval_job(scheduler, "sync_warm_markets", jobs.warm_market_snapshot_seconds, sync_warm_markets_job)
    add_interval_job(scheduler, "sync_cold_markets", jobs.cold_market_snapshot_seconds, sync_cold_markets_job)
    add_interval_job(scheduler, "compute_quality", 300, compute_quality_job)
    run_scheduler(scheduler)


if __name__ == "__main__":
    main()
