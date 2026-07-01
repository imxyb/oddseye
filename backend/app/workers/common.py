from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import get_session_factory


async def run_db_job(job_name: str, fn: Callable) -> None:
    async with get_session_factory()() as session:
        await fn(session)
        await session.commit()


def run_scheduler(scheduler: AsyncIOScheduler) -> None:
    scheduler.start()
    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def add_interval_job(
    scheduler: AsyncIOScheduler,
    name: str,
    seconds: int,
    fn: Callable[[], Awaitable[None]],
) -> None:
    scheduler.add_job(fn, "interval", seconds=seconds, id=name, name=name, max_instances=1)

