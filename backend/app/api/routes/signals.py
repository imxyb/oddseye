from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.services.signals import create_order_from_signal, list_signals

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalPaperOrderRequest(BaseModel):
    account_id: str | None = None
    notional: Decimal
    limit_price: Decimal


@router.get("")
async def signals(
    action: str | None = None,
    category: str | None = None,
    min_edge: Decimal | None = Query(None, alias="minEdge"),
    limit: int = Query(50, ge=1, le=200),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await list_signals(session, action=action, category=category, min_edge=min_edge, limit=limit)


@router.post("/{signal_id}/paper-order")
async def signal_paper_order(
    signal_id: str,
    request: SignalPaperOrderRequest,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_order_from_signal(
            session,
            signal_id=signal_id,
            account_id=request.account_id,
            notional=request.notional,
            limit_price=request.limit_price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

