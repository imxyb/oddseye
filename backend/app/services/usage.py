from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.codex.client import UsageRecord
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import ApiUsageLedger
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
    result = await session.execute(select(ApiUsageLedger))
    records = list(result.scalars())
    today = [record for record in records if _ensure_aware(record.ts) >= start_day]
    month = [record for record in records if _ensure_aware(record.ts) >= start_month]
    settings = get_settings().config.codex
    return {
        "provider": "codex",
        "today_requests": sum(record.request_count for record in today),
        "month_requests": sum(record.request_count for record in month),
        "today_failed": sum(record.request_count for record in today if record.status != "success"),
        "month_failed": sum(record.request_count for record in month if record.status != "success"),
        "fetch_profile": settings.fetch_profile,
        "usage_policy": settings.usage_policy,
        "radar_daily_target_requests": settings.radar_daily_target_requests,
        "radar_daily_review_threshold": settings.radar_daily_review_threshold,
        "radar_monthly_review_threshold": settings.radar_monthly_review_threshold,
        "external_daily_usage_estimate": settings.external_daily_usage_estimate,
        "global_monthly_reference_budget": settings.global_monthly_reference_budget,
    }


def usage_hint_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "today_requests": summary["today_requests"],
        "month_requests": summary["month_requests"],
        "fetch_profile": summary["fetch_profile"],
    }


def _ensure_aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value

