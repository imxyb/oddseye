from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.codex.client import UsageRecord
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import ApiUsageLedger, JobRun
from app.db.session import get_session_factory


class DatabaseUsageRecorder:
    async def record(self, record: UsageRecord) -> None:
        async with get_session_factory()() as session:
            session.add(
                ApiUsageLedger(
                    ts=utcnow(),
                    provider=record.provider,
                    kind=record.kind,
                    request_count=record.request_count,
                    status=record.status,
                    duration_ms=record.duration_ms,
                    job_run_id=record.job_run_id,
                    metadata_json=record.metadata,
                )
            )
            await session.commit()


async def usage_summary(session: AsyncSession) -> dict[str, Any]:
    now = utcnow()
    start_day = datetime(now.year, now.month, now.day, tzinfo=UTC)
    start_month = datetime(now.year, now.month, 1, tzinfo=UTC)
    config = get_settings().config
    settings = config.codex
    return {
        "provider": "codex",
        "today_requests": await _request_count_since(session, start_day),
        "month_requests": await _request_count_since(session, start_month),
        "today_failed": await _request_count_since(session, start_day, failed_only=True),
        "month_failed": await _request_count_since(session, start_month, failed_only=True),
        "fetch_profile": settings.fetch_profile,
        "usage_policy": settings.usage_policy,
        "radar_daily_target_requests": settings.radar_daily_target_requests,
        "radar_daily_review_threshold": settings.radar_daily_review_threshold,
        "radar_monthly_review_threshold": settings.radar_monthly_review_threshold,
        "external_daily_usage_estimate": settings.external_daily_usage_estimate,
        "global_monthly_reference_budget": settings.global_monthly_reference_budget,
        "jobs": config.jobs.model_dump(),
        "recent_jobs": await _latest_job_runs(session),
    }


def usage_hint_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "today_requests": summary["today_requests"],
        "month_requests": summary["month_requests"],
        "fetch_profile": summary["fetch_profile"],
    }


def _ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def _request_count_since(
    session: AsyncSession,
    start: datetime,
    failed_only: bool = False,
) -> int:
    conditions = [ApiUsageLedger.provider == "codex", ApiUsageLedger.ts >= start]
    if failed_only:
        conditions.append(ApiUsageLedger.status != "success")
    result = await session.execute(
        select(func.coalesce(func.sum(ApiUsageLedger.request_count), 0)).where(*conditions)
    )
    return int(result.scalar_one() or 0)


async def _latest_job_runs(session: AsyncSession) -> list[dict[str, Any]]:
    latest_started = (
        select(
            JobRun.job_name.label("job_name"),
            func.max(JobRun.started_at).label("started_at"),
        )
        .group_by(JobRun.job_name)
        .subquery()
    )
    result = await session.execute(
        select(JobRun)
        .join(
            latest_started,
            and_(
                JobRun.job_name == latest_started.c.job_name,
                JobRun.started_at == latest_started.c.started_at,
            ),
        )
        .order_by(JobRun.started_at.desc())
    )
    job_runs = list(result.scalars())
    return [
        {
            "job_name": job_run.job_name,
            "started_at": _ensure_aware(job_run.started_at).isoformat(),
            "finished_at": _ensure_aware(job_run.finished_at).isoformat() if job_run.finished_at else None,
            "status": job_run.status,
            "records_processed": job_run.records_processed,
            "codex_requests_used": job_run.codex_requests_used,
        }
        for job_run in job_runs
    ]
