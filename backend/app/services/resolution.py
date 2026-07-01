from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.codex.client import CodexClient
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import (
    MarketResolution,
    PaperAccount,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
)
from app.services.ingestion import create_codex_client, sync_event_markets

MONEY_Q = Decimal("0.00000001")


async def poll_resolutions(
    session: AsyncSession,
    client: CodexClient | None = None,
    job_run_id: str | None = None,
) -> int:
    event_ids = await _event_ids_due_for_resolution(session)
    settings = get_settings()
    if event_ids and (client is not None or settings.codex_api_key):
        close_client = client is None
        codex_client = client or create_codex_client()
        try:
            await sync_event_markets(
                session,
                event_ids,
                client=codex_client,
                job_run_id=job_run_id,
                kind="resolution",
            )
        finally:
            if close_client:
                await codex_client.aclose()
    return await settle_due_markets(session)


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


async def _event_ids_due_for_resolution(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(PredictionEvent.external_event_id)
        .join(PredictionMarket, PredictionMarket.event_id == PredictionEvent.id)
        .where(
            PredictionMarket.closes_at.is_not(None),
            PredictionMarket.closes_at <= utcnow(),
        )
        .distinct()
    )
    return [event_id for event_id in result.scalars() if event_id]


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
    inferred = _resolved_outcome_index_from_settled_prices(raw_json)
    if inferred is not None:
        return inferred
    return None


def _resolved_label(raw_json: dict[str, Any]) -> str | None:
    for key in ("resolved_label", "resolvedLabel", "winning_outcome", "winningOutcome"):
        value = raw_json.get(key)
        if value is not None:
            return str(value)
    resolution = raw_json.get("resolution")
    if isinstance(resolution, dict):
        return _resolved_label(resolution)
    outcome_index = _resolved_outcome_index_from_settled_prices(raw_json)
    if outcome_index is not None:
        outcome = raw_json.get(f"outcome{outcome_index}") or {}
        label = outcome.get("label")
        if label:
            return str(label)
    return None


def _resolved_outcome_index_from_settled_prices(raw_json: dict[str, Any]) -> int | None:
    if not _has_resolved_status(raw_json):
        return None
    outcome0 = raw_json.get("outcome0") or {}
    outcome1 = raw_json.get("outcome1") or {}
    outcome0_price = _settlement_price(outcome0)
    outcome1_price = _settlement_price(outcome1)
    if outcome0_price is None or outcome1_price is None:
        return None
    if outcome0_price >= Decimal("0.999999") and outcome1_price <= Decimal("0.000001"):
        return 0
    if outcome1_price >= Decimal("0.999999") and outcome0_price <= Decimal("0.000001"):
        return 1
    return None


def _has_resolved_status(raw_json: dict[str, Any]) -> bool:
    status = raw_json.get("status") or (raw_json.get("market") or {}).get("status")
    return str(status or "").upper() in {"CLOSED", "RESOLVED", "SETTLED", "FINALIZED"}


def _settlement_price(outcome: dict[str, Any]) -> Decimal | None:
    for key in ("lastPriceCT", "bestBidCT", "bestAskCT", "priceCT"):
        value = outcome.get(key)
        if value is not None:
            return Decimal(str(value))
    price = outcome.get("priceCollateralToken")
    if isinstance(price, dict) and price.get("c") is not None:
        return Decimal(str(price["c"]))
    return None
