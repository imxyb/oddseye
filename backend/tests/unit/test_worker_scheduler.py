from __future__ import annotations

import asyncio
from datetime import datetime

from app.workers.common import add_interval_job, run_scheduler
from app.workers import signal as signal_worker


def test_run_scheduler_starts_scheduler_inside_running_event_loop() -> None:
    events: list[str] = []

    class LoopAwareScheduler:
        def start(self) -> None:
            asyncio.get_running_loop()
            events.append("start")
            raise KeyboardInterrupt

        def shutdown(self) -> None:
            events.append("shutdown")

    run_scheduler(LoopAwareScheduler())  # type: ignore[arg-type]

    assert events == ["start", "shutdown"]


def test_add_interval_job_can_schedule_first_run_immediately() -> None:
    calls: list[dict] = []

    class RecordingScheduler:
        def add_job(self, fn, trigger, **kwargs) -> None:
            calls.append({"fn": fn, "trigger": trigger, "kwargs": kwargs})

    async def job() -> None:
        return None

    add_interval_job(
        RecordingScheduler(),  # type: ignore[arg-type]
        "compute_signals",
        300,
        job,
        run_immediately=True,
    )

    assert calls[0]["trigger"] == "interval"
    assert calls[0]["kwargs"]["next_run_time"] is not None
    assert isinstance(calls[0]["kwargs"]["next_run_time"], datetime)


def test_signal_worker_schedules_compute_signals_immediately(monkeypatch) -> None:
    calls: list[dict] = []

    class RecordingScheduler:
        def __init__(self, timezone: str) -> None:
            self.timezone = timezone

    def record_interval_job(scheduler, name, seconds, fn, **kwargs) -> None:
        calls.append(
            {
                "scheduler": scheduler,
                "name": name,
                "seconds": seconds,
                "fn": fn,
                "kwargs": kwargs,
            }
        )

    monkeypatch.setattr(signal_worker, "AsyncIOScheduler", RecordingScheduler)
    monkeypatch.setattr(signal_worker, "add_interval_job", record_interval_job)
    monkeypatch.setattr(signal_worker, "run_scheduler", lambda scheduler: None)

    signal_worker.main()

    assert calls[0]["name"] == "compute_signals"
    assert calls[0]["kwargs"]["run_immediately"] is True
