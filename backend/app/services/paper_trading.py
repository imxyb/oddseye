from __future__ import annotations

import csv
from io import StringIO
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import (
    MarketSnapshot,
    ModelSignal,
    PaperAccount,
    PaperFill,
    PaperOrder,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
)
from app.paper.engine import PaperAccountState, PaperOrderRequest, PaperTradingEngine, SnapshotQuote
from app.services.bootstrap import ensure_default_paper_account
from app.services.market_data import latest_snapshot_for_market


@dataclass(frozen=True)
class PaperOrderInput:
    market_id: str
    side: str
    outcome_index: int
    limit_price: Decimal
    quantity: Decimal
    account_id: str | None = None
    signal_id: str | None = None
    enforce_auto_gates: bool = False


async def create_paper_order(session: AsyncSession, order_input: PaperOrderInput) -> dict[str, Any]:
    account = (
        await session.get(PaperAccount, order_input.account_id)
        if order_input.account_id
        else await ensure_default_paper_account(session)
    )
    if account is None:
        raise ValueError("paper account not found")
    market = await session.get(PredictionMarket, order_input.market_id)
    if market is None:
        raise ValueError("market not found")

    risk_error = await _risk_error(session, account, market, order_input)
    order = PaperOrder(
        account_id=account.id,
        market_id=market.id,
        signal_id=order_input.signal_id,
        side=order_input.side.upper(),
        outcome_index=order_input.outcome_index,
        limit_price=order_input.limit_price,
        quantity=order_input.quantity,
        status="rejected" if risk_error else "open",
        reason=risk_error,
    )
    session.add(order)
    await session.flush()
    if risk_error:
        return {"order": _order_json(order), "fill": None, "position": None}

    snapshot = await latest_snapshot_for_market(session, market.id)
    if snapshot is None:
        order.reason = "waiting_for_snapshot"
        return {"order": _order_json(order), "fill": None, "position": None}

    engine = PaperTradingEngine(
        slippage_bps=get_settings().config.paper.slippage_bps,
        fee_bps=get_settings().config.paper.fee_bps,
    )
    db_position = await _load_position(session, account.id, market.id, order_input.outcome_index)
    if db_position is not None and db_position.quantity > 0:
        engine.open_position(
            account_id=account.id,
            market_id=market.id,
            outcome_index=order_input.outcome_index,
            quantity=db_position.quantity,
            avg_price=db_position.avg_price,
            realized_pnl=db_position.realized_pnl,
            unrealized_pnl=db_position.unrealized_pnl,
        )
    result = engine.try_fill(
        PaperAccountState(id=account.id, cash=account.cash, starting_cash=account.starting_cash),
        PaperOrderRequest(
            account_id=account.id,
            market_id=market.id,
            signal_id=order_input.signal_id,
            side=order_input.side.upper(),
            outcome_index=order_input.outcome_index,
            limit_price=order_input.limit_price,
            quantity=order_input.quantity,
        ),
        _snapshot_quote(snapshot),
    )
    if result is None:
        order.reason = "limit_not_executable"
        return {"order": _order_json(order), "fill": None, "position": _position_json(db_position)}

    account.cash = result.account.cash
    order.status = "filled"
    order.filled_at = utcnow()
    fill = PaperFill(
        order_id=order.id,
        account_id=account.id,
        market_id=market.id,
        outcome_index=order.outcome_index,
        side=order.side,
        price=result.fill.price,
        quantity=result.fill.quantity,
        notional=result.fill.notional,
        fee=result.fill.fee,
        snapshot_id=result.fill.snapshot_id,
    )
    session.add(fill)
    position = await _upsert_position(session, result.position)
    return {"order": _order_json(order), "fill": _fill_json(fill), "position": _position_json(position)}


async def list_positions(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(PaperPosition).order_by(PaperPosition.updated_at.desc()))
    return [_position_json(position) for position in result.scalars()]


async def performance(session: AsyncSession) -> dict[str, Any]:
    account = await ensure_default_paper_account(session)
    positions = (
        await session.execute(select(PaperPosition).where(PaperPosition.account_id == account.id))
    ).scalars().all()
    fills = (
        await session.execute(
            select(PaperFill)
            .where(PaperFill.account_id == account.id)
            .order_by(PaperFill.created_at.asc())
        )
    ).scalars().all()
    realized = sum((position.realized_pnl for position in positions), Decimal("0"))
    unrealized = sum((position.unrealized_pnl for position in positions), Decimal("0"))
    position_value = sum(
        ((position.mark_price or Decimal("0")) * position.quantity for position in positions if position.status == "open"),
        Decimal("0"),
    )
    equity = account.cash + position_value
    closed_positions = [position for position in positions if position.status == "closed"]
    wins = [position for position in closed_positions if position.realized_pnl > 0]
    max_drawdown = _historical_max_drawdown(account.starting_cash, fills, equity)
    return {
        "equity": float(equity),
        "cash": float(account.cash),
        "position_value": float(position_value),
        "unrealized_pnl": float(unrealized),
        "realized_pnl": float(realized),
        "win_rate": len(wins) / len(closed_positions) if closed_positions else 0,
        "max_drawdown": float(max_drawdown),
        "total_trades": len(fills),
    }


async def review_report(session: AsyncSession) -> dict[str, Any]:
    trades = await trade_rows(session)
    strategy_stats: dict[str, dict[str, Any]] = {}
    category_stats: dict[str, dict[str, Any]] = {}
    for trade in trades:
        strategy = trade["strategy_code"] or "manual"
        category = trade["category"] or "uncategorized"
        _accumulate(strategy_stats, strategy, trade)
        _accumulate(category_stats, category, trade)
    for collection in (strategy_stats, category_stats):
        for item in collection.values():
            item.pop("_edge_sum", None)
            item.pop("_edge_count", None)
    return {
        "strategy_stats": list(strategy_stats.values()),
        "category_stats": list(category_stats.values()),
        "trades": trades,
    }


async def trades_csv(session: AsyncSession) -> str:
    trades = await trade_rows(session)
    output = StringIO()
    fieldnames = [
        "fill_id",
        "order_id",
        "signal_id",
        "snapshot_id",
        "market_id",
        "question",
        "category",
        "strategy_code",
        "side",
        "outcome_index",
        "price",
        "quantity",
        "notional",
        "fee",
        "edge",
        "market_quality_score",
        "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(trades)
    return output.getvalue()


async def trade_rows(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        select(PaperFill, PaperOrder, PredictionMarket, PredictionEvent, ModelSignal)
        .join(PaperOrder, PaperFill.order_id == PaperOrder.id)
        .join(PredictionMarket, PaperFill.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .outerjoin(ModelSignal, PaperOrder.signal_id == ModelSignal.id)
        .order_by(PaperFill.created_at.desc())
    )
    rows: list[dict[str, Any]] = []
    for fill, order, market, event, signal in result.all():
        rows.append(
            {
                "fill_id": fill.id,
                "order_id": fill.order_id,
                "signal_id": order.signal_id,
                "snapshot_id": fill.snapshot_id,
                "market_id": fill.market_id,
                "question": market.question,
                "category": (event.categories or ["uncategorized"])[0],
                "strategy_code": signal.strategy_code if signal else None,
                "side": fill.side,
                "outcome_index": fill.outcome_index,
                "price": float(fill.price),
                "quantity": float(fill.quantity),
                "notional": float(fill.notional),
                "fee": float(fill.fee),
                "edge": float(signal.edge) if signal and signal.edge is not None else None,
                "market_quality_score": (
                    float(signal.market_quality_score)
                    if signal and signal.market_quality_score is not None
                    else None
                ),
                "created_at": fill.created_at.isoformat(),
            }
        )
    return rows


def _accumulate(stats: dict[str, dict[str, Any]], key: str, trade: dict[str, Any]) -> None:
    item = stats.setdefault(
        key,
        {
            "key": key,
            "total_trades": 0,
            "total_notional": 0.0,
            "average_edge": None,
            "_edge_sum": 0.0,
            "_edge_count": 0,
        },
    )
    item["total_trades"] += 1
    item["total_notional"] += trade["notional"]
    if trade["edge"] is not None:
        item["_edge_sum"] += trade["edge"]
        item["_edge_count"] += 1
        item["average_edge"] = item["_edge_sum"] / item["_edge_count"]


def _drawdown_from_starting_cash(starting_cash: Decimal, equity: Decimal) -> Decimal:
    if starting_cash <= 0 or equity >= starting_cash:
        return Decimal("0")
    return (starting_cash - equity) / starting_cash


def _historical_max_drawdown(
    starting_cash: Decimal,
    fills: list[PaperFill],
    current_equity: Decimal,
) -> Decimal:
    if starting_cash <= 0:
        return Decimal("0")

    cash = starting_cash
    peak = starting_cash
    max_drawdown = Decimal("0")
    quantities: dict[tuple[str, int], Decimal] = {}
    marks: dict[tuple[str, int], Decimal] = {}

    for fill in fills:
        key = (fill.market_id, fill.outcome_index)
        side = fill.side.upper()
        if side == "BUY":
            cash -= fill.notional + fill.fee
            quantities[key] = quantities.get(key, Decimal("0")) + fill.quantity
        elif side in {"SELL", "EXIT"}:
            cash += fill.notional - fill.fee
            quantities[key] = max(
                quantities.get(key, Decimal("0")) - fill.quantity,
                Decimal("0"),
            )
        else:
            continue
        marks[key] = fill.price
        peak, max_drawdown = _update_drawdown(
            peak,
            _historical_equity(cash, quantities, marks),
            max_drawdown,
        )

    _peak, max_drawdown = _update_drawdown(peak, current_equity, max_drawdown)
    return max(max_drawdown, _drawdown_from_starting_cash(starting_cash, current_equity))


def _historical_equity(
    cash: Decimal,
    quantities: dict[tuple[str, int], Decimal],
    marks: dict[tuple[str, int], Decimal],
) -> Decimal:
    position_value = sum(
        (quantity * marks.get(key, Decimal("0")) for key, quantity in quantities.items()),
        Decimal("0"),
    )
    return cash + position_value


def _update_drawdown(
    peak: Decimal,
    equity: Decimal,
    max_drawdown: Decimal,
) -> tuple[Decimal, Decimal]:
    if equity > peak:
        return equity, max_drawdown
    if peak <= 0:
        return peak, max_drawdown
    return peak, max(max_drawdown, (peak - equity) / peak)


async def mark_positions(session: AsyncSession) -> int:
    result = await session.execute(select(PaperPosition).where(PaperPosition.status == "open"))
    count = 0
    for position in result.scalars():
        snapshot = await latest_snapshot_for_market(session, position.market_id)
        if snapshot is None:
            continue
        quote = _snapshot_quote(snapshot)
        mark = quote.outcome0_best_bid if position.outcome_index == 0 else quote.outcome1_best_bid
        if mark is None:
            continue
        position.mark_price = mark
        position.unrealized_pnl = (mark - position.avg_price) * position.quantity
        position.updated_at = utcnow()
        count += 1
    return count


async def try_fill_open_orders(session: AsyncSession) -> int:
    result = await session.execute(select(PaperOrder).where(PaperOrder.status == "open"))
    filled = 0
    for order in result.scalars():
        if await _try_fill_existing_order(session, order):
            filled += 1
    return filled


async def _try_fill_existing_order(session: AsyncSession, order: PaperOrder) -> bool:
    account = await session.get(PaperAccount, order.account_id)
    market = await session.get(PredictionMarket, order.market_id)
    if account is None or market is None:
        order.status = "rejected"
        order.reason = "missing_account_or_market"
        return False
    snapshot = await latest_snapshot_for_market(session, market.id)
    if snapshot is None:
        order.reason = "waiting_for_snapshot"
        return False
    engine = PaperTradingEngine(
        slippage_bps=get_settings().config.paper.slippage_bps,
        fee_bps=get_settings().config.paper.fee_bps,
    )
    db_position = await _load_position(session, account.id, market.id, order.outcome_index)
    if db_position is not None and db_position.quantity > 0:
        engine.open_position(
            account_id=account.id,
            market_id=market.id,
            outcome_index=order.outcome_index,
            quantity=db_position.quantity,
            avg_price=db_position.avg_price,
            realized_pnl=db_position.realized_pnl,
            unrealized_pnl=db_position.unrealized_pnl,
        )
    result = engine.try_fill(
        PaperAccountState(id=account.id, cash=account.cash, starting_cash=account.starting_cash),
        PaperOrderRequest(
            account_id=account.id,
            market_id=market.id,
            signal_id=order.signal_id,
            side=order.side,
            outcome_index=order.outcome_index,
            limit_price=order.limit_price,
            quantity=order.quantity,
        ),
        _snapshot_quote(snapshot),
    )
    if result is None:
        order.reason = "limit_not_executable"
        return False
    account.cash = result.account.cash
    order.status = "filled"
    order.filled_at = utcnow()
    fill = PaperFill(
        order_id=order.id,
        account_id=account.id,
        market_id=market.id,
        outcome_index=order.outcome_index,
        side=order.side,
        price=result.fill.price,
        quantity=result.fill.quantity,
        notional=result.fill.notional,
        fee=result.fill.fee,
        snapshot_id=result.fill.snapshot_id,
    )
    session.add(fill)
    await _upsert_position(session, result.position)
    return True


async def _risk_error(
    session: AsyncSession,
    account: PaperAccount,
    market: PredictionMarket,
    order_input: PaperOrderInput,
) -> str | None:
    settings = get_settings().config.paper
    latest = await latest_snapshot_for_market(session, market.id)
    notional = order_input.limit_price * order_input.quantity
    equity = await _account_equity(session, account)
    if order_input.side.upper() == "SELL" and not settings.allow_short:
        position = await _load_position(session, account.id, market.id, order_input.outcome_index)
        if position is None or position.quantity < order_input.quantity:
            return "insufficient_inventory"
    if order_input.side.upper() == "BUY" and notional > equity * Decimal(str(settings.max_position_pct)):
        return "single_order_notional_exceeds_3pct_equity"
    if order_input.side.upper() == "BUY":
        market_exposure = await _market_exposure(session, account.id, market.id)
        if market_exposure + notional > equity * Decimal(str(settings.max_market_risk_pct)):
            return "market_exposure_exceeds_5pct_equity"
        if market.closes_at is not None and _aware(market.closes_at) <= utcnow() + timedelta(minutes=30):
            return "market_closing_soon"
    if order_input.enforce_auto_gates and latest is not None:
        if latest.market_quality_score is not None and latest.market_quality_score < Decimal("65"):
            return "market_quality_below_gate"
        spread = latest.outcome0_spread if order_input.outcome_index == 0 else latest.outcome1_spread
        if spread is not None and spread > Decimal("0.08"):
            return "spread_above_gate"
    if order_input.enforce_auto_gates and market.closes_at is not None and _aware(market.closes_at) <= utcnow():
        return "market_closed"
    daily_loss = await _daily_loss(session, account.id)
    if daily_loss <= -(equity * Decimal(str(settings.max_daily_loss_pct))):
        return "daily_loss_limit_reached"
    event = await session.get(PredictionEvent, market.event_id)
    if event is not None:
        exposure = await _category_exposure(session, account.id, event.categories)
        if exposure + notional > equity * Decimal(str(settings.max_category_exposure_pct)):
            return "category_exposure_exceeds_15pct_equity"
    return None


async def _account_equity(session: AsyncSession, account: PaperAccount) -> Decimal:
    result = await session.execute(
        select(PaperPosition).where(
            PaperPosition.account_id == account.id,
            PaperPosition.status == "open",
        )
    )
    position_value = sum(
        ((position.mark_price or Decimal("0")) * position.quantity for position in result.scalars()),
        Decimal("0"),
    )
    return account.cash + position_value


async def _daily_loss(session: AsyncSession, account_id: str) -> Decimal:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.coalesce(func.sum(PaperPosition.realized_pnl), 0)).where(
            PaperPosition.account_id == account_id,
            PaperPosition.updated_at >= start,
        )
    )
    return Decimal(str(result.scalar_one() or 0))


async def _category_exposure(session: AsyncSession, account_id: str, categories: list) -> Decimal:
    if not categories:
        return Decimal("0")
    result = await session.execute(
        select(PaperPosition, PredictionMarket, PredictionEvent)
        .join(PredictionMarket, PaperPosition.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .where(PaperPosition.account_id == account_id, PaperPosition.status == "open")
    )
    exposure = Decimal("0")
    wanted = {str(category).lower() for category in categories}
    for position, _market, event in result.all():
        if wanted.intersection({str(category).lower() for category in event.categories or []}):
            exposure += position.quantity * position.avg_price
    return exposure


async def _market_exposure(session: AsyncSession, account_id: str, market_id: str) -> Decimal:
    result = await session.execute(
        select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.market_id == market_id,
            PaperPosition.status == "open",
        )
    )
    return sum((position.quantity * position.avg_price for position in result.scalars()), Decimal("0"))


async def _load_position(
    session: AsyncSession, account_id: str, market_id: str, outcome_index: int
) -> PaperPosition | None:
    return await session.scalar(
        select(PaperPosition).where(
            PaperPosition.account_id == account_id,
            PaperPosition.market_id == market_id,
            PaperPosition.outcome_index == outcome_index,
        )
    )


async def _upsert_position(session: AsyncSession, state) -> PaperPosition:
    position = await _load_position(
        session, str(state.account_id), str(state.market_id), state.outcome_index
    )
    if position is None:
        position = PaperPosition(
            account_id=str(state.account_id),
            market_id=str(state.market_id),
            outcome_index=state.outcome_index,
            quantity=state.quantity,
            avg_price=state.avg_price,
            mark_price=state.mark_price,
            realized_pnl=state.realized_pnl,
            unrealized_pnl=state.unrealized_pnl,
            status=state.status,
        )
        session.add(position)
    else:
        position.quantity = state.quantity
        position.avg_price = state.avg_price
        position.mark_price = state.mark_price
        position.realized_pnl = state.realized_pnl
        position.unrealized_pnl = state.unrealized_pnl
        position.status = state.status
        position.updated_at = utcnow()
    await session.flush()
    return position


def _snapshot_quote(snapshot: MarketSnapshot) -> SnapshotQuote:
    return SnapshotQuote(
        id=snapshot.id,
        market_id=snapshot.market_id,
        ts=snapshot.ts,
        outcome0_best_bid=snapshot.outcome0_best_bid,
        outcome0_best_ask=snapshot.outcome0_best_ask,
        outcome1_best_bid=snapshot.outcome1_best_bid,
        outcome1_best_ask=snapshot.outcome1_best_ask,
    )


def _order_json(order: PaperOrder) -> dict[str, Any]:
    return {
        "order_id": order.id,
        "account_id": order.account_id,
        "market_id": order.market_id,
        "signal_id": order.signal_id,
        "side": order.side,
        "outcome_index": order.outcome_index,
        "order_type": order.order_type,
        "limit_price": float(order.limit_price),
        "quantity": float(order.quantity),
        "status": order.status,
        "reason": order.reason,
    }


def _fill_json(fill: PaperFill) -> dict[str, Any]:
    return {
        "fill_id": fill.id,
        "order_id": fill.order_id,
        "price": float(fill.price),
        "quantity": float(fill.quantity),
        "notional": float(fill.notional),
        "fee": float(fill.fee),
        "snapshot_id": fill.snapshot_id,
    }


def _position_json(position: PaperPosition | None) -> dict[str, Any] | None:
    if position is None:
        return None
    return {
        "position_id": position.id,
        "account_id": position.account_id,
        "market_id": position.market_id,
        "outcome_index": position.outcome_index,
        "quantity": float(position.quantity),
        "avg_price": float(position.avg_price),
        "mark_price": float(position.mark_price) if position.mark_price is not None else None,
        "realized_pnl": float(position.realized_pnl),
        "unrealized_pnl": float(position.unrealized_pnl),
        "status": position.status,
    }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=utcnow().tzinfo)
    return value
