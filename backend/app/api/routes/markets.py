from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.services.ingestion import job_run, refresh_market
from app.services.market_data import market_bars, market_detail

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/{market_id}")
async def detail(
    market_id: str,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    item = await market_detail(session, market_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Market not found")
    return item


@router.post("/{market_id}/refresh")
async def refresh(
    market_id: str,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if not get_settings().config.ingestion_tiers.manual_refresh_enabled:
        raise HTTPException(status_code=403, detail="Manual refresh is disabled")
    async with job_run(session, "manual_refresh") as run:
        records_processed = await refresh_market(session, market_id, job_run_id=run.id)
        if records_processed is None:
            raise HTTPException(status_code=404, detail="Market not found")
        run.records_processed = records_processed
    detail_item = await market_detail(session, market_id)
    return {
        "market_id": market_id,
        "records_processed": records_processed,
        "market": detail_item,
    }


@router.get("/{market_id}/bars")
async def bars(
    market_id: str,
    range: str = Query("7d", pattern="^(24h|7d|30d|all)$"),
    resolution: str = Query("hour1", pattern="^(min15|hour1|hour4|day1)$"),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await market_bars(session, market_id, range_name=range, resolution=resolution)
