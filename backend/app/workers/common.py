from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import get_session_factory


async def run_db_job(job_name: str, fn: Callable) -> None:
    async with get_session_factory()() as session:
        await fn(session)
        await session.commit()


def run_scheduler(scheduler: AsyncIOScheduler) -> None:
    try:
        asyncio.run(_run_scheduler(scheduler))
    except (KeyboardInterrupt, SystemExit):
        pass


async def _run_scheduler(scheduler: AsyncIOScheduler) -> None:
    try:
        scheduler.start()
        await asyncio.Event().wait()
    finally:
        if getattr(scheduler, "running", True):
            scheduler.shutdown()


def add_interval_job(
    scheduler: AsyncIOScheduler,
    name: str,
    seconds: int,
    fn: Callable[[], Awaitable[None]],
    run_immediately: bool = False,
) -> None:
    kwargs = {}
    if run_immediately:
        kwargs["next_run_time"] = datetime.now(UTC)
    scheduler.add_job(
        fn,
        "interval",
        seconds=seconds,
        id=name,
        name=name,
        max_instances=1,
        **kwargs,
    )
