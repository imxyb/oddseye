from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.codex.client import UsageRecord
from app.core.config import get_settings
from app.db.models import ApiUsageLedger, JobRun
from app.db.session import Base, get_session_factory
from app.services.ingestion import job_run
from app.services.usage import DatabaseUsageRecorder, usage_summary


@pytest.mark.asyncio
async def test_job_run_is_visible_to_usage_recorder_before_work_starts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    sessionmaker = get_session_factory()
    try:
        async with sessionmaker.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with sessionmaker() as session:
            async with job_run(session, "discover_events") as run:
                run_id = run.id
                async with sessionmaker() as verification_session:
                    assert await verification_session.get(JobRun, run_id) is not None

                await DatabaseUsageRecorder().record(
                    UsageRecord(
                        provider="codex",
                        kind="discovery",
                        request_count=1,
                        status="success",
                        duration_ms=12,
                        job_run_id=run_id,
                    )
                )

        async with sessionmaker() as session:
            ledger = await session.scalar(select(ApiUsageLedger))
            persisted_run = await session.get(JobRun, run_id)

        assert ledger is not None
        assert ledger.job_run_id == run_id
        assert persisted_run is not None
        assert persisted_run.status == "success"
        assert persisted_run.codex_requests_used == 1
    finally:
        await sessionmaker.bind.dispose()
        get_session_factory.cache_clear()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_usage_summary_includes_recent_job_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'usage-jobs.db'}")
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    sessionmaker = get_session_factory()
    try:
        async with sessionmaker.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        now = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
        async with sessionmaker() as session:
            session.add_all(
                [
                    JobRun(
                        job_name="discover_events",
                        started_at=now - timedelta(minutes=10),
                        finished_at=now - timedelta(minutes=9),
                        status="success",
                        records_processed=12,
                        codex_requests_used=1,
                    ),
                    JobRun(
                        job_name="sync_hot_markets",
                        started_at=now - timedelta(minutes=5),
                        finished_at=now - timedelta(minutes=4),
                        status="success",
                        records_processed=24,
                        codex_requests_used=3,
                    ),
                ]
            )
            await session.commit()

        async with sessionmaker() as session:
            summary = await usage_summary(session)

        assert summary["recent_jobs"] == [
            {
                "job_name": "sync_hot_markets",
                "started_at": (now - timedelta(minutes=5)).isoformat(),
                "finished_at": (now - timedelta(minutes=4)).isoformat(),
                "status": "success",
                "records_processed": 24,
                "codex_requests_used": 3,
            },
            {
                "job_name": "discover_events",
                "started_at": (now - timedelta(minutes=10)).isoformat(),
                "finished_at": (now - timedelta(minutes=9)).isoformat(),
                "status": "success",
                "records_processed": 12,
                "codex_requests_used": 1,
            },
        ]
    finally:
        await sessionmaker.bind.dispose()
        get_session_factory.cache_clear()
        get_settings.cache_clear()
