from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.models import MarketResolution, PaperAccount, PaperPosition, PredictionMarket

MONEY_Q = Decimal("0.00000001")


async def settle_due_markets(session: AsyncSession) -> int:
    result = await session.execute(
        select(PredictionMarket).where(
            PredictionMarket.closes_at.is_not(None),
            PredictionMarket.closes_at <= utcnow(),
        )
    )
    processed = 0
    for market in result.scalars():
        resolution = await _upsert_resolution(session, market)
        await _apply_resolution(session, market, resolution)
        processed += 1
    await session.flush()
    return processed


async def _upsert_resolution(
    session: AsyncSession, market: PredictionMarket
) -> MarketResolution:
    existing = await session.scalar(
        select(MarketResolution)
        .where(MarketResolution.market_id == market.id)
        .order_by(MarketResolution.created_at.desc())
        .limit(1)
    )
    outcome_index = _resolved_outcome_index(market.raw_json or {})
    resolved_label = _resolved_label(market.raw_json or {})
    status = "resolved" if outcome_index is not None else "pending_resolution"
    resolved_at = utcnow() if outcome_index is not None else None
    raw_json = {
        "source": "market_raw_json",
        "market_status": market.status,
        "market_raw_json": market.raw_json or {},
    }
    if existing is None:
        existing = MarketResolution(
            market_id=market.id,
            resolved_outcome_index=outcome_index,
            resolved_label=resolved_label,
            status=status,
            resolved_at=resolved_at,
            raw_json=raw_json,
        )
        session.add(existing)
    else:
        existing.resolved_outcome_index = outcome_index
        existing.resolved_label = resolved_label
        existing.status = status
        existing.resolved_at = resolved_at
        existing.raw_json = raw_json
    return existing


async def _apply_resolution(
    session: AsyncSession,
    market: PredictionMarket,
    resolution: MarketResolution,
) -> None:
    positions = await session.execute(
        select(PaperPosition).where(
            PaperPosition.market_id == market.id,
            PaperPosition.status.in_(("open", "pending_resolution")),
            PaperPosition.quantity > 0,
        )
    )
    for position in positions.scalars():
        if resolution.resolved_outcome_index is None:
            position.status = "pending_resolution"
            position.updated_at = utcnow()
            continue

        account = await session.get(PaperAccount, position.account_id)
        payout = (
            position.quantity
            if position.outcome_index == resolution.resolved_outcome_index
            else Decimal("0")
        )
        cost_basis = position.avg_price * position.quantity
        position.realized_pnl = (position.realized_pnl + payout - cost_basis).quantize(MONEY_Q)
        position.unrealized_pnl = Decimal("0").quantize(MONEY_Q)
        position.mark_price = Decimal("1") if payout > 0 else Decimal("0")
        position.quantity = Decimal("0").quantize(MONEY_Q)
        position.status = "closed"
        position.updated_at = utcnow()
        if account is not None:
            account.cash = (account.cash + payout).quantize(MONEY_Q)


def _resolved_outcome_index(raw_json: dict[str, Any]) -> int | None:
    for key in (
        "resolved_outcome_index",
        "resolvedOutcomeIndex",
        "winning_outcome_index",
        "winningOutcomeIndex",
        "winnerOutcomeIndex",
    ):
        value = raw_json.get(key)
        if value is not None:
            return int(value)
    resolution = raw_json.get("resolution")
    if isinstance(resolution, dict):
        return _resolved_outcome_index(resolution)
    return None


def _resolved_label(raw_json: dict[str, Any]) -> str | None:
    for key in ("resolved_label", "resolvedLabel", "winning_outcome", "winningOutcome"):
        value = raw_json.get(key)
        if value is not None:
            return str(value)
    resolution = raw_json.get("resolution")
    if isinstance(resolution, dict):
        return _resolved_label(resolution)
    return None
