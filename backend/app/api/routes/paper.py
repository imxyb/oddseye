from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.services.paper_trading import (
    PaperOrderInput,
    create_paper_order,
    list_positions,
    performance,
    review_report,
    trades_csv,
)

router = APIRouter(prefix="/paper", tags=["paper"])


class PaperOrderRequest(BaseModel):
    account_id: str | None = None
    market_id: str
    side: str
    outcome_index: int = Field(ge=0, le=1)
    limit_price: Decimal = Field(gt=Decimal("0"), lt=Decimal("1"))
    quantity: Decimal = Field(gt=Decimal("0"))

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return normalized


@router.post("/orders")
async def create_order(
    request: PaperOrderRequest,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await create_paper_order(
            session,
            PaperOrderInput(
                account_id=request.account_id,
                market_id=request.market_id,
                side=request.side,
                outcome_index=request.outcome_index,
                limit_price=request.limit_price,
                quantity=request.quantity,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/positions")
async def positions(
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    items = await list_positions(session)
    return {"items": items, "total": len(items)}


@router.get("/performance")
async def paper_performance(
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await performance(session)


@router.get("/review")
async def paper_review(
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await review_report(session)


@router.get("/trades.csv")
async def paper_trades_csv(
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    return Response(
        content=await trades_csv(session),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paper_trades.csv"},
    )
