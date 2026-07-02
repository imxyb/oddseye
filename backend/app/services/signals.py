from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.time import utcnow
from app.db.models import (
    MarketSnapshot,
    ModelSignal,
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PredictionEvent,
    PredictionMarket,
)
from app.services.bootstrap import ensure_default_paper_account
from app.services.asset_market_data import (
    AssetMarketDataProvider,
    BinanceAssetMarketDataProvider,
)
from app.services.crypto_market_data import CryptoMarketDataService
from app.services.market_data import CATEGORY_ALIASES
from app.services.paper_trading import PaperOrderInput, create_paper_order
from app.services.prediction_orderbook import PredictionOrderBookService
from app.strategies.base import StrategySignal
from app.strategies.crypto_v2.lifecycle import PositionState
from app.strategies.crypto_v2.spec import CryptoMarketSpec
from app.strategies.crypto_v2.spec_parser import CryptoMarketSpecParserV2
from app.strategies.crypto_v2.strategy import (
    SIGNAL_TTL,
    STRATEGY_CODE,
    STRATEGY_VERSION,
    CryptoThresholdV2Strategy,
    V2StrategyResult,
)
from app.strategies.macro_calendar import macro_v1_observe_only_signal


async def list_signals(
    session: AsyncSession,
    action: str | None = None,
    category: str | None = None,
    min_edge: Decimal | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    now = utcnow()
    action_upper = action.upper() if action else None
    filters = [
        or_(ModelSignal.expires_at.is_(None), ModelSignal.expires_at > now),
        not_(_invalid_buy_signal_clause()),
    ]
    if action_upper:
        filters.append(ModelSignal.action == action_upper)
    if min_edge is not None:
        filters.extend([ModelSignal.edge.is_not(None), ModelSignal.edge >= min_edge])
    query = (
        select(ModelSignal, PredictionMarket, PredictionEvent)
        .join(PredictionMarket, ModelSignal.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .where(*filters)
        .order_by(ModelSignal.ts.desc())
    )
    if action_upper == "HOLD":
        ranked_signals = (
            select(
                ModelSignal.id.label("signal_id"),
                func.row_number()
                .over(
                    partition_by=(ModelSignal.market_id, ModelSignal.side),
                    order_by=(ModelSignal.ts.desc(), ModelSignal.id.desc()),
                )
                .label("signal_rank"),
            )
            .where(*filters)
            .subquery()
        )
        query = query.join(ranked_signals, ModelSignal.id == ranked_signals.c.signal_id).where(
            ranked_signals.c.signal_rank == 1
        )
    query = query.limit(limit if category is None else max(limit * 10, 200))
    rows = await session.execute(query)
    items = []
    for signal, market, event in rows.all():
        if category and not _category_matches(event.categories, category):
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
    if not _is_orderable_buy_signal(signal):
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


def _invalid_buy_signal_clause():
    return and_(
        ModelSignal.action == "BUY",
        or_(
            ModelSignal.side.is_(None),
            ModelSignal.side.notin_(["YES", "NO"]),
            ModelSignal.executable_price.is_(None),
            ModelSignal.executable_price <= Decimal("0"),
            ModelSignal.executable_price >= Decimal("1"),
        ),
    )


def _is_orderable_buy_signal(signal: ModelSignal) -> bool:
    executable_price = signal.executable_price
    return (
        signal.action == "BUY"
        and signal.side in {"YES", "NO"}
        and executable_price is not None
        and Decimal("0") < executable_price < Decimal("1")
    )


async def compute_signals(
    session: AsyncSession,
    asset_market_data_provider: AssetMarketDataProvider | None = None,
) -> int:
    count = await compute_crypto_signals(session, asset_market_data_provider=asset_market_data_provider)
    count += await compute_macro_signals(session)
    return count


async def compute_crypto_signals(
    session: AsyncSession,
    asset_market_data_provider: AssetMarketDataProvider | None = None,
) -> int:
    strategy_config = get_settings().config.strategies.crypto_threshold_v2
    if not strategy_config.enabled:
        return 0
    strategy = CryptoThresholdV2Strategy(config=strategy_config)
    provider = asset_market_data_provider or BinanceAssetMarketDataProvider()
    owns_provider = asset_market_data_provider is None
    market_data = CryptoMarketDataService(provider)
    orderbooks = PredictionOrderBookService()
    account = await ensure_default_paper_account(session)
    asset_cache: dict[str, Any] = {}
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
        if market.protocol.upper() != "POLYMARKET" or event.protocol.upper() != "POLYMARKET":
            continue
        if snapshot.market_quality_score is None:
            continue
        current_position = await _current_position_state(session, account.id, market.id)
        parsed = strategy.parser.parse(market, event)
        if parsed.failed or parsed.spec is None:
            if current_position is not None and strategy_config.exits.parser_block_exit_enabled:
                result = _v2_exit_result_from_blocked(
                    market,
                    snapshot,
                    current_position,
                    reason="PARSER_FAILED",
                    risk_flags=parsed.ambiguity_flags or ["PARSER_FAILED"],
                )
            else:
                result = strategy.blocked_from_parse(market, event, snapshot)
        else:
            if parsed.spec.asset not in asset_cache:
                asset_cache[parsed.spec.asset] = await market_data.get_asset_snapshot(parsed.spec.asset)
            asset_snapshot = asset_cache[parsed.spec.asset]
            if asset_snapshot is None:
                if current_position is not None and strategy_config.exits.asset_data_unavailable_exit_enabled:
                    result = _v2_exit_result_from_blocked(
                        market,
                        snapshot,
                        current_position,
                        reason="ASSET_MARKET_DATA_UNAVAILABLE",
                        risk_flags=["ASSET_MARKET_DATA_UNAVAILABLE"],
                    )
                else:
                    result = _v2_blocked_result(
                        market,
                        snapshot,
                        reason="ASSET_MARKET_DATA_UNAVAILABLE",
                        risk_flags=["ASSET_MARKET_DATA_UNAVAILABLE"],
                    )
            else:
                yes_orderbook = await orderbooks.get_orderbook(market, snapshot, "YES")
                no_orderbook = await orderbooks.get_orderbook(market, snapshot, "NO")
                equity = await _paper_equity(session, account)
                result = strategy.evaluate(
                    market=market,
                    event=event,
                    snapshot=snapshot,
                    spec=parsed.spec,
                    asset_snapshot=asset_snapshot,
                    yes_orderbook=yes_orderbook,
                    no_orderbook=no_orderbook,
                    current_position=current_position,
                    equity=equity,
                    existing_exposure_multiplier=await _asset_horizon_exposure_multiplier(
                        session,
                        account_id=account.id,
                        spec=parsed.spec,
                        equity=equity,
                        max_exposure_pct=strategy_config.sizing.max_asset_horizon_exposure_pct,
                        parser=strategy.parser,
                    ),
                )
        model_signal = _model_signal_from_result(result)
        session.add(model_signal)
        await session.flush()
        await _auto_execute_v2_signal(
            session,
            account=account,
            model_signal=model_signal,
            current_position=await _current_position_state(session, account.id, market.id),
        )
        count += 1
    if owns_provider and hasattr(provider, "aclose"):
        await provider.aclose()
    return count


def _model_signal_from_result(result: V2StrategyResult) -> ModelSignal:
    signal = result.signal
    return ModelSignal(
        market_id=signal.market_id,
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
        raw_json=result.raw_json,
    )


def _v2_blocked_result(
    market: PredictionMarket,
    snapshot: MarketSnapshot,
    *,
    reason: str,
    risk_flags: list[str],
) -> V2StrategyResult:
    now = utcnow()
    signal = StrategySignal(
        market_id=market.id,
        strategy_code=STRATEGY_CODE,
        action="BLOCKED",
        side=None,
        model_probability=None,
        executable_price=None,
        edge=None,
        confidence=Decimal("0"),
        suggested_notional=None,
        market_quality_score=snapshot.market_quality_score or Decimal("0"),
        reason_codes=[reason],
        risk_flags=risk_flags,
        expires_at=now + SIGNAL_TTL,
        snapshot_id=snapshot.id,
    )
    return V2StrategyResult(
        signal=signal,
        raw_json={
            "strategy_code": STRATEGY_CODE,
            "strategy_version": STRATEGY_VERSION,
            "snapshot_id": snapshot.id,
            "decision": {
                "action": "BLOCKED",
                "side": None,
                "blocked_reason": reason,
                "risk_flags": risk_flags,
            },
            "decision_trace": [reason],
        },
    )


def _v2_exit_result_from_blocked(
    market: PredictionMarket,
    snapshot: MarketSnapshot,
    current_position: PositionState,
    *,
    reason: str,
    risk_flags: list[str],
) -> V2StrategyResult:
    now = utcnow()
    executable_price = _exit_price(snapshot, 0 if current_position.side == "YES" else 1)
    suggested_notional = (
        (current_position.quantity * executable_price).quantize(Decimal("0.000001"))
        if executable_price is not None
        else None
    )
    signal = StrategySignal(
        market_id=market.id,
        strategy_code=STRATEGY_CODE,
        action="EXIT",
        side=current_position.side,
        model_probability=None,
        executable_price=executable_price,
        edge=None,
        confidence=Decimal("0"),
        suggested_notional=suggested_notional,
        market_quality_score=snapshot.market_quality_score or Decimal("0"),
        reason_codes=[reason],
        risk_flags=risk_flags,
        expires_at=now + SIGNAL_TTL,
        snapshot_id=snapshot.id,
    )
    return V2StrategyResult(
        signal=signal,
        raw_json={
            "strategy_code": STRATEGY_CODE,
            "strategy_version": STRATEGY_VERSION,
            "snapshot_id": snapshot.id,
            "decision": {
                "action": "EXIT",
                "side": current_position.side,
                "limit_price": float(executable_price) if executable_price is not None else None,
                "blocked_reason": reason,
                "risk_flags": risk_flags,
            },
            "decision_trace": [reason, "EXIT"],
        },
    )


async def _current_position_state(
    session: AsyncSession,
    account_id: str,
    market_id: str,
) -> PositionState | None:
    position = await session.scalar(
        select(PaperPosition)
        .where(
            PaperPosition.account_id == account_id,
            PaperPosition.market_id == market_id,
            PaperPosition.status == "open",
            PaperPosition.quantity > 0,
        )
        .order_by(PaperPosition.updated_at.desc())
    )
    if position is None:
        return None
    return PositionState(
        side=_side_for_outcome(position.outcome_index),
        quantity=position.quantity,
        avg_price=position.avg_price,
        mark_price=position.mark_price,
        opened_probability=await _opened_probability_for_position(session, position),
        last_buy_at=None,
    )


async def _opened_probability_for_position(
    session: AsyncSession,
    position: PaperPosition,
) -> float | None:
    order = await session.scalar(
        select(PaperOrder)
        .where(
            PaperOrder.account_id == position.account_id,
            PaperOrder.market_id == position.market_id,
            PaperOrder.outcome_index == position.outcome_index,
            PaperOrder.side == "BUY",
            PaperOrder.status == "filled",
            PaperOrder.signal_id.is_not(None),
        )
        .order_by(PaperOrder.filled_at.desc(), PaperOrder.created_at.desc())
    )
    if order is None or order.signal_id is None:
        return None
    signal = await session.get(ModelSignal, order.signal_id)
    if signal is None:
        return None
    probability = ((signal.raw_json or {}).get("probability") or {}).get("p_calibrated")
    if probability is None:
        return None
    value = float(probability)
    return value if position.outcome_index == 0 else 1.0 - value


async def _paper_equity(session: AsyncSession, account: PaperAccount) -> Decimal:
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


async def _asset_horizon_exposure_multiplier(
    session: AsyncSession,
    *,
    account_id: str,
    spec: CryptoMarketSpec,
    equity: Decimal,
    max_exposure_pct: float,
    parser: CryptoMarketSpecParserV2,
) -> float:
    if equity <= 0 or max_exposure_pct <= 0:
        return 0.0
    exposure_limit = equity * Decimal(str(max_exposure_pct))
    if exposure_limit <= 0:
        return 0.0
    rows = await session.execute(
        select(PaperPosition, PredictionMarket, PredictionEvent)
        .join(PredictionMarket, PaperPosition.market_id == PredictionMarket.id)
        .join(PredictionEvent, PredictionMarket.event_id == PredictionEvent.id)
        .where(
            PaperPosition.account_id == account_id,
            PaperPosition.status == "open",
            PaperPosition.quantity > 0,
        )
    )
    target_bucket = _horizon_bucket(spec.window_end)
    current_exposure = Decimal("0")
    for position, market, event in rows.all():
        parsed = parser.parse(market, event)
        if parsed.failed or parsed.spec is None:
            continue
        if parsed.spec.asset != spec.asset or _horizon_bucket(parsed.spec.window_end) != target_bucket:
            continue
        mark = position.mark_price or position.avg_price
        current_exposure += position.quantity * mark
    remaining = exposure_limit - current_exposure
    if remaining <= 0:
        return 0.0
    return float(min(Decimal("1"), remaining / exposure_limit))


def _horizon_bucket(value: datetime) -> str:
    iso = value.date().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def _auto_execute_v2_signal(
    session: AsyncSession,
    *,
    account: PaperAccount,
    model_signal: ModelSignal,
    current_position: PositionState | None,
) -> None:
    strategy_config = get_settings().config.strategies.crypto_threshold_v2
    if model_signal.strategy_code != STRATEGY_CODE:
        return
    if (
        not strategy_config.enabled
        or strategy_config.mode == "observe_only"
        or not strategy_config.paper_execution.auto_execute_signals
    ):
        return
    if model_signal.action not in {"BUY", "EXIT", "REDUCE"}:
        return
    if model_signal.side not in {"YES", "NO"} or model_signal.executable_price is None:
        return
    side = "BUY" if model_signal.action == "BUY" else "SELL"
    outcome_index = 0 if model_signal.side == "YES" else 1
    limit_price = _auto_limit_price(model_signal.executable_price, side)
    quantity = _auto_order_quantity(
        model_signal=model_signal,
        side=side,
        limit_price=limit_price,
        current_position=current_position,
    )
    if quantity <= 0:
        _merge_signal_raw_json(model_signal, {"auto_order": {"status": "skipped", "reason": "no_quantity"}})
        return
    response = await create_paper_order(
        session,
        PaperOrderInput(
            account_id=account.id,
            market_id=model_signal.market_id,
            signal_id=model_signal.id,
            side=side,
            outcome_index=outcome_index,
            limit_price=limit_price,
            quantity=quantity,
            enforce_auto_gates=side == "BUY",
        ),
    )
    _merge_signal_raw_json(model_signal, {"auto_order": response})


def _auto_limit_price(executable_price: Decimal, side: str) -> Decimal:
    slippage = get_settings().config.strategies.crypto_threshold_v2.paper_execution.price_slippage_ct
    if side == "BUY":
        return min(executable_price + slippage, Decimal("0.99")).quantize(Decimal("0.000001"))
    return max(executable_price - slippage, Decimal("0.01")).quantize(Decimal("0.000001"))


def _auto_order_quantity(
    *,
    model_signal: ModelSignal,
    side: str,
    limit_price: Decimal,
    current_position: PositionState | None,
) -> Decimal:
    if side == "BUY":
        if model_signal.suggested_notional is None:
            return Decimal("0")
        return (model_signal.suggested_notional / limit_price).quantize(Decimal("0.000001"))
    if current_position is None:
        return Decimal("0")
    if model_signal.action == "REDUCE":
        return (current_position.quantity * Decimal("0.50")).quantize(Decimal("0.000001"))
    return current_position.quantity


def _merge_signal_raw_json(model_signal: ModelSignal, payload: dict[str, Any]) -> None:
    raw = dict(model_signal.raw_json or {})
    raw.update(payload)
    model_signal.raw_json = raw


async def compute_macro_signals(session: AsyncSession) -> int:
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
        if not _category_matches(event.categories, "economics"):
            continue
        if snapshot.market_quality_score is None:
            continue
        signal = await _position_adjusted_signal(
            session,
            macro_v1_observe_only_signal(
                market_id=market.id,
                quality_score=snapshot.market_quality_score,
                snapshot_id=snapshot.id,
                expires_at=utcnow() + SIGNAL_TTL,
            ),
            snapshot,
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


def _category_matches(categories: list | None, wanted: str) -> bool:
    aliases = CATEGORY_ALIASES.get(wanted.lower(), {wanted.lower()})
    return any(str(category).lower() in aliases for category in categories or [])


def _side_for_outcome(outcome_index: int) -> str:
    return "YES" if outcome_index == 0 else "NO"


def _exit_price(snapshot: MarketSnapshot, outcome_index: int) -> Decimal | None:
    return snapshot.outcome0_best_bid if outcome_index == 0 else snapshot.outcome1_best_bid


def _signal_item(signal: ModelSignal, market: PredictionMarket, event: PredictionEvent) -> dict[str, Any]:
    raw = signal.raw_json or {}
    market_spec = raw.get("market_spec") if isinstance(raw.get("market_spec"), dict) else {}
    probability = raw.get("probability") if isinstance(raw.get("probability"), dict) else {}
    edge = raw.get("edge") if isinstance(raw.get("edge"), dict) else {}
    decision = raw.get("decision") if isinstance(raw.get("decision"), dict) else {}
    freshness = {
        "spot_seconds": (raw.get("asset_market_data") or {}).get("age_seconds")
        if isinstance(raw.get("asset_market_data"), dict)
        else None,
        "orderbook_seconds": (raw.get("prediction_orderbook") or {}).get("age_seconds")
        if isinstance(raw.get("prediction_orderbook"), dict)
        else None,
    }
    return {
        "signal_id": signal.id,
        "market_id": signal.market_id,
        "strategy_code": signal.strategy_code,
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
        "asset": market_spec.get("asset"),
        "market_type": market_spec.get("market_type"),
        "threshold": market_spec.get("threshold"),
        "deadline": market_spec.get("window_end"),
        "probability_range": (
            [probability.get("p_low"), probability.get("p_high")]
            if "p_low" in probability and "p_high" in probability
            else None
        ),
        "edge_exec": edge.get("edge_exec"),
        "edge_stress": edge.get("edge_stress"),
        "required_edge": edge.get("required_edge"),
        "blocked_reason": decision.get("blocked_reason"),
        "data_freshness": freshness,
        "raw_signal_json": raw,
    }


def _decimal(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=utcnow().tzinfo)
    return value
