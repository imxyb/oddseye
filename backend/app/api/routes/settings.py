from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.services.usage import usage_summary

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/usage")
async def usage(
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await usage_summary(session)

