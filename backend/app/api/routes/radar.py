from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.services.market_data import radar_markets

router = APIRouter(prefix="/radar", tags=["radar"])


@router.get("/markets")
async def markets(
    category: str | None = None,
    protocol: str | None = None,
    q: str | None = None,
    sort: str = Query("quality", pattern="^(quality|volume|liquidity|closingSoon|edge)$"),
    min_quality: float | None = Query(None, alias="minQuality"),
    min_volume: float | None = Query(None, alias="minVolume"),
    min_liquidity: float | None = Query(None, alias="minLiquidity"),
    max_spread: float | None = Query(None, alias="maxSpread"),
    closes_within_hours: float | None = Query(None, alias="closesWithinHours"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await radar_markets(
        session,
        category=category,
        protocol=protocol,
        q=q,
        sort=sort,
        min_quality=min_quality,
        min_volume=min_volume,
        min_liquidity=min_liquidity,
        max_spread=max_spread,
        closes_within_hours=closes_within_hours,
        limit=limit,
        offset=offset,
    )
