from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.ingestion import job_run
from app.services.paper_trading import mark_positions, try_fill_open_orders
from app.workers.common import add_interval_job, run_scheduler


async def try_fill_paper_orders_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "try_fill_paper_orders") as run:
            run.records_processed = await try_fill_open_orders(session)
        await session.commit()


async def mark_positions_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "mark_positions") as run:
            run.records_processed = await mark_positions(session)
        await session.commit()


def main() -> None:
    jobs = get_settings().config.jobs
    scheduler = AsyncIOScheduler(timezone=get_settings().config.app.timezone)
    add_interval_job(scheduler, "try_fill_paper_orders", jobs.paper_mark_seconds, try_fill_paper_orders_job)
    add_interval_job(scheduler, "mark_positions", jobs.paper_mark_seconds, mark_positions_job)
    run_scheduler(scheduler)


if __name__ == "__main__":
    main()
