from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.models import (
    MarketSnapshot,
    ModelSignal,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
)
from app.services.asset_market_data import (
    AssetMarketData,
    AssetMarketDataProvider,
    BinanceAssetMarketDataProvider,
)
from app.services.paper_trading import PaperOrderInput, create_paper_order
from app.strategies.crypto_threshold import (
    CryptoMarketContext,
    CryptoThresholdStrategy,
    parse_crypto_threshold,
)
from app.strategies.base import StrategySignal


async def list_signals(
    session: AsyncSession,
    action: str | None = None,
    category: str | None = None,
    min_edge: Decimal | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    now = utcnow()
    query = (
        select(ModelSignal, PredictionMarket, PredictionEvent)
        .join(PredictionMarket, ModelSignal.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .where(or_(ModelSignal.expires_at.is_(None), ModelSignal.expires_at > now))
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
    if signal.expires_at is not None and _aware(signal.expires_at) <= utcnow():
        raise ValueError("signal expired")
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


async def compute_crypto_signals(
    session: AsyncSession,
    asset_market_data_provider: AssetMarketDataProvider | None = None,
) -> int:
    strategy = CryptoThresholdStrategy()
    provider = asset_market_data_provider or BinanceAssetMarketDataProvider()
    owns_provider = asset_market_data_provider is None
    asset_cache: dict[str, AssetMarketData | dict | None] = {}
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
        parsed = parse_crypto_threshold(market.question)
        if parsed is None:
            signal = _ignore_signal(strategy.strategy_code, market, snapshot)
            raw_signal_json = {"snapshot_id": signal.snapshot_id}
        else:
            raw = market.raw_json or {}
            asset_data = await _asset_market_data(provider, asset_cache, parsed.asset)
            strategy_inputs = _strategy_inputs(raw, asset_data)
            if strategy_inputs is None:
                continue
            signal = strategy.evaluate(
                CryptoMarketContext(
                    market_id=market.id,
                    question=market.question,
                    now=utcnow(),
                    deadline=market.closes_at,
                    current_price=strategy_inputs["current_price"],
                    annualized_volatility=strategy_inputs["annualized_volatility"],
                    yes_ask=snapshot.outcome0_best_ask,
                    no_ask=snapshot.outcome1_best_ask,
                    market_quality_score=snapshot.market_quality_score,
                    parser_confidence=Decimal("0.86"),
                    snapshot_id=snapshot.id,
                )
            )
            raw_signal_json = {
                "snapshot_id": signal.snapshot_id,
                "asset_market_data": strategy_inputs["metadata"],
            }
        signal = await _position_adjusted_signal(session, signal, snapshot)
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
                raw_json=raw_signal_json,
            )
        )
        count += 1
    if owns_provider and hasattr(provider, "aclose"):
        await provider.aclose()
    return count


def _ignore_signal(strategy_code: str, market: PredictionMarket, snapshot: MarketSnapshot) -> StrategySignal:
    now = utcnow()
    return StrategySignal(
        market_id=market.id,
        strategy_code=strategy_code,
        action="IGNORE",
        side=None,
        model_probability=None,
        executable_price=None,
        edge=None,
        confidence=Decimal("0"),
        suggested_notional=None,
        market_quality_score=snapshot.market_quality_score,
        reason_codes=[],
        risk_flags=["PARSER_FAILED"],
        expires_at=now + timedelta(minutes=5),
        snapshot_id=snapshot.id,
    )


async def _asset_market_data(
    provider: AssetMarketDataProvider,
    cache: dict[str, AssetMarketData | dict | None],
    asset: str,
) -> AssetMarketData | dict | None:
    if asset not in cache:
        try:
            cache[asset] = await provider.asset_market_data(asset)
        except Exception:
            cache[asset] = None
    return cache[asset]


def _strategy_inputs(
    raw: dict[str, Any],
    asset_data: AssetMarketData | dict | None,
) -> dict[str, Any] | None:
    raw_inputs = raw.get("strategy_inputs") if isinstance(raw.get("strategy_inputs"), dict) else raw
    current_price = raw_inputs.get("current_price")
    volatility = raw_inputs.get("annualized_volatility")
    source = "raw_json"
    asset = raw_inputs.get("asset")
    if (current_price is None or volatility is None) and asset_data is not None:
        if isinstance(asset_data, AssetMarketData):
            current_price = asset_data.current_price
            volatility = asset_data.annualized_volatility
            source = asset_data.source
            asset = asset_data.asset
        else:
            current_price = asset_data.get("current_price")
            volatility = asset_data.get("annualized_volatility")
            source = asset_data.get("source", "asset_market_data")
            asset = asset_data.get("asset")
    if current_price is None or volatility is None:
        return None
    return {
        "current_price": Decimal(str(current_price)),
        "annualized_volatility": Decimal(str(volatility)),
        "metadata": {
            "asset": asset,
            "current_price": str(current_price),
            "annualized_volatility": str(volatility),
            "source": source,
        },
    }


async def _position_adjusted_signal(
    session: AsyncSession,
    signal: StrategySignal,
    snapshot: MarketSnapshot,
) -> StrategySignal:
    position = await session.scalar(
        select(PaperPosition)
        .where(
            PaperPosition.market_id == signal.market_id,
            PaperPosition.status == "open",
            PaperPosition.quantity > 0,
        )
        .order_by(PaperPosition.updated_at.desc())
    )
    if position is None:
        return signal
    if signal.action == "BUY" and signal.side in {"YES", "NO"}:
        target_index = 0 if signal.side == "YES" else 1
        if position.outcome_index == target_index:
            return replace(
                signal,
                action="HOLD",
                executable_price=None,
                suggested_notional=None,
                reason_codes=[*signal.reason_codes, "HOLD_EXISTING_POSITION"],
            )
        exit_price = _exit_price(snapshot, position.outcome_index)
        return replace(
            signal,
            action="EXIT",
            side=_side_for_outcome(position.outcome_index),
            executable_price=exit_price,
            suggested_notional=position.quantity * exit_price if exit_price is not None else None,
            reason_codes=[*signal.reason_codes, "EXIT_OPPOSING_MODEL_EDGE"],
        )
    if signal.action == "OBSERVE":
        return replace(
            signal,
            action="HOLD",
            side=_side_for_outcome(position.outcome_index),
            executable_price=None,
            suggested_notional=None,
            reason_codes=[*signal.reason_codes, "HOLD_EXISTING_POSITION"],
        )
    return signal


def _side_for_outcome(outcome_index: int) -> str:
    return "YES" if outcome_index == 0 else "NO"


def _exit_price(snapshot: MarketSnapshot, outcome_index: int) -> Decimal | None:
    return snapshot.outcome0_best_bid if outcome_index == 0 else snapshot.outcome1_best_bid


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


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=utcnow().tzinfo)
    return value
