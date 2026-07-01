from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.ingestion import job_run
from app.services.resolution import settle_due_markets
from app.workers.common import add_interval_job, run_scheduler


async def poll_resolutions_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "poll_resolutions") as run:
            run.records_processed = await settle_due_markets(session)
        await session.commit()


def main() -> None:
    scheduler = AsyncIOScheduler(timezone=get_settings().config.app.timezone)
    add_interval_job(
        scheduler,
        "poll_resolutions",
        get_settings().config.jobs.resolution_poll_seconds,
        poll_resolutions_job,
    )
    run_scheduler(scheduler)


if __name__ == "__main__":
    main()
