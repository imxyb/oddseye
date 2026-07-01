from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.ingestion import job_run
from app.services.usage import usage_summary
from app.workers.common import add_interval_job, run_scheduler


async def daily_budget_rollup_job() -> None:
    async with get_session_factory()() as session:
        async with job_run(session, "daily_budget_rollup") as run:
            summary = await usage_summary(session)
            run.records_processed = summary["today_requests"]
            run.codex_requests_used = summary["today_requests"]
        await session.commit()


def main() -> None:
    scheduler = AsyncIOScheduler(timezone=get_settings().config.app.timezone)
    add_interval_job(scheduler, "daily_budget_rollup", 24 * 60 * 60, daily_budget_rollup_job)
    run_scheduler(scheduler)


if __name__ == "__main__":
    main()

