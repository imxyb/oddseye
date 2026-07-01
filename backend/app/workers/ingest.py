from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import PredictionEvent
from app.db.session import get_session_factory
from app.services.ingestion import (
    compute_quality_for_latest_snapshots,
    discover_events,
    job_run,
    refresh_categories,
    sync_event_markets,
)
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
    await _sync_markets(limit=get_settings().config.ingestion_tiers.hot_watchlist_max_markets)


async def sync_warm_markets_job() -> None:
    await _sync_markets(limit=get_settings().config.ingestion_tiers.warm_pool_max_markets)


async def sync_cold_markets_job() -> None:
    await _sync_markets(limit=get_settings().config.ingestion_tiers.cold_pool_max_markets)


async def compute_quality_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "compute_quality") as run:
            run.records_processed = await compute_quality_for_latest_snapshots(session)
        await session.commit()


async def _sync_markets(limit: int) -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "sync_markets") as run:
            result = await session.execute(
                select(PredictionEvent.external_event_id)
                .where(PredictionEvent.status == "OPEN")
                .order_by(PredictionEvent.updated_at.desc())
                .limit(limit)
            )
            run.records_processed = await sync_event_markets(
                session, list(result.scalars()), job_run_id=run.id
            )
        await session.commit()


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
