from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.models import MarketSnapshot, ModelSignal, PredictionEvent, PredictionMarket
from app.services.paper_trading import PaperOrderInput, create_paper_order
from app.strategies.crypto_threshold import CryptoMarketContext, CryptoThresholdStrategy


async def list_signals(
    session: AsyncSession,
    action: str | None = None,
    category: str | None = None,
    min_edge: Decimal | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    query = (
        select(ModelSignal, PredictionMarket, PredictionEvent)
        .join(PredictionMarket, ModelSignal.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .order_by(ModelSignal.ts.desc())
    )
    if action:
        query = query.where(ModelSignal.action == action.upper())
    if min_edge is not None:
        query = query.where(ModelSignal.edge.is_not(None), ModelSignal.edge >= min_edge)
    query = query.limit(limit if category is None else max(limit * 10, 200))
    rows = await session.execute(query)
    items = []
    for signal, market, event in rows.all():
        if category and category.lower() not in [c.lower() for c in event.categories or []]:
            continue
        items.append(_signal_item(signal, market, event))
        if len(items) >= limit:
            break
    return {"items": items, "total": len(items)}


async def create_order_from_signal(
    session: AsyncSession,
    signal_id: str,
    account_id: str | None,
    notional: Decimal,
    limit_price: Decimal,
) -> dict[str, Any]:
    signal = await session.get(ModelSignal, signal_id)
    if signal is None:
        raise ValueError("signal not found")
    if signal.action != "BUY" or signal.side not in {"YES", "NO"}:
        raise ValueError("signal is not orderable")
    outcome_index = 0 if signal.side == "YES" else 1
    quantity = notional / limit_price
    return await create_paper_order(
        session,
        PaperOrderInput(
            account_id=account_id,
            market_id=signal.market_id,
            signal_id=signal.id,
            side="BUY",
            outcome_index=outcome_index,
            limit_price=limit_price,
            quantity=quantity,
            enforce_auto_gates=True,
        ),
    )


async def compute_crypto_signals(session: AsyncSession) -> int:
    strategy = CryptoThresholdStrategy()
    rows = await session.execute(
        select(PredictionMarket, PredictionEvent, MarketSnapshot)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .join(MarketSnapshot, MarketSnapshot.market_id == PredictionMarket.id)
        .order_by(MarketSnapshot.ts.desc())
    )
    seen: set[str] = set()
    count = 0
    for market, event, snapshot in rows.all():
        if market.id in seen:
            continue
        seen.add(market.id)
        if "crypto" not in [str(c).lower() for c in event.categories or []]:
            continue
        if snapshot.market_quality_score is None or market.closes_at is None:
            continue
        # V1 leaves market price ingestion external; use threshold parser plus current probability inputs
        # when a seed or enrichment process has written current_price/volatility into raw_json.
        raw = market.raw_json or {}
        current_price = raw.get("current_price")
        volatility = raw.get("annualized_volatility")
        if current_price is None or volatility is None:
            continue
        signal = strategy.evaluate(
            CryptoMarketContext(
                market_id=market.id,
                question=market.question,
                now=utcnow(),
                deadline=market.closes_at,
                current_price=Decimal(str(current_price)),
                annualized_volatility=Decimal(str(volatility)),
                yes_ask=snapshot.outcome0_best_ask,
                no_ask=snapshot.outcome1_best_ask,
                market_quality_score=snapshot.market_quality_score,
                parser_confidence=Decimal("0.86"),
                snapshot_id=snapshot.id,
            )
        )
        session.add(
            ModelSignal(
                market_id=market.id,
                ts=utcnow(),
                strategy_code=signal.strategy_code,
                action=signal.action,
                side=signal.side,
                model_probability=signal.model_probability,
                executable_price=signal.executable_price,
                edge=signal.edge,
                confidence=signal.confidence,
                suggested_notional=signal.suggested_notional,
                market_quality_score=signal.market_quality_score,
                reason_codes=signal.reason_codes,
                risk_flags=signal.risk_flags,
                expires_at=signal.expires_at,
                raw_json={"snapshot_id": signal.snapshot_id},
            )
        )
        count += 1
    return count


def _signal_item(signal: ModelSignal, market: PredictionMarket, event: PredictionEvent) -> dict[str, Any]:
    return {
        "signal_id": signal.id,
        "market_id": signal.market_id,
        "question": market.question,
        "category": (event.categories or ["uncategorized"])[0],
        "action": signal.action,
        "side": signal.side,
        "model_probability": _decimal(signal.model_probability),
        "executable_price": _decimal(signal.executable_price),
        "edge": _decimal(signal.edge),
        "confidence": _decimal(signal.confidence),
        "suggested_notional": _decimal(signal.suggested_notional),
        "market_quality_score": _decimal(signal.market_quality_score),
        "reason_codes": signal.reason_codes,
        "risk_flags": signal.risk_flags,
        "expires_at": signal.expires_at.isoformat() if signal.expires_at else None,
    }


def _decimal(value: Decimal | None) -> float | None:
    return None if value is None else float(value)
