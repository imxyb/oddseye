from __future__ import annotations

import asyncio

from app.workers.common import run_scheduler


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
