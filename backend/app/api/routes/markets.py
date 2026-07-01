from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
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


@router.get("/{market_id}/bars")
async def bars(
    market_id: str,
    range: str = Query("7d", pattern="^(24h|7d|30d|all)$"),
    resolution: str = Query("hour1", pattern="^(min15|hour1|hour4|day1)$"),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await market_bars(session, market_id, range_name=range, resolution=resolution)
