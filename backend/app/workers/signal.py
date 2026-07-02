from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.ingestion import job_run
from app.services.signals import compute_signals, prewarm_crypto_semantic_parse_caches
from app.workers.common import add_interval_job, run_scheduler


async def prewarm_crypto_semantic_parse_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "prewarm_crypto_semantic_parse") as run:
            run.records_processed = await prewarm_crypto_semantic_parse_caches(session)
        await session.commit()


async def compute_signals_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "compute_signals") as run:
            run.records_processed = await compute_signals(session)
        await session.commit()


def main() -> None:
    scheduler = AsyncIOScheduler(timezone=get_settings().config.app.timezone)
    add_interval_job(
        scheduler,
        "prewarm_crypto_semantic_parse",
        get_settings().config.jobs.signal_seconds,
        prewarm_crypto_semantic_parse_job,
        run_immediately=True,
    )
    add_interval_job(
        scheduler,
        "compute_signals",
        get_settings().config.jobs.signal_seconds,
        compute_signals_job,
        run_immediately=False,
    )
    run_scheduler(scheduler)


if __name__ == "__main__":
    main()
