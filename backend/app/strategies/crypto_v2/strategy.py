from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.core.time import utcnow
from app.db.models import MarketSnapshot, PredictionEvent, PredictionMarket
from app.strategies.base import StrategySignal
from app.strategies.crypto_v2.execution_gate import evaluate_execution_gate
from app.strategies.crypto_v2.lifecycle import PositionState, decide_lifecycle_action
from app.strategies.crypto_v2.probability import estimate_probability
from app.strategies.crypto_v2.sizing import SizingConfig, suggested_notional
from app.strategies.crypto_v2.spec import (
    CryptoAssetSnapshot,
    CryptoMarketSpec,
    ExecutionDecision,
    PredictionOrderBookSnapshot,
    ProbabilityEstimate,
)
from app.strategies.crypto_v2.spec_parser import CryptoMarketSpecParserV2

SIGNAL_TTL = timedelta(minutes=15)
STRATEGY_CODE = "crypto_threshold_v2"
STRATEGY_VERSION = "2.0.0"


@dataclass(frozen=True)
class V2StrategyResult:
    signal: StrategySignal
    raw_json: dict[str, Any]


class CryptoThresholdV2Strategy:
    strategy_code = STRATEGY_CODE

    def __init__(self, parser: CryptoMarketSpecParserV2 | None = None):
        self.parser = parser or CryptoMarketSpecParserV2()

    def blocked_from_parse(
        self,
        market: PredictionMarket,
        event: PredictionEvent | None,
        snapshot: MarketSnapshot,
    ) -> V2StrategyResult:
        now = utcnow()
        parsed = self.parser.parse(market, event)
        flags = parsed.ambiguity_flags or ["PARSER_FAILED"]
        signal = StrategySignal(
            market_id=market.id,
            strategy_code=self.strategy_code,
            action="BLOCKED",
            side=None,
            model_probability=None,
            executable_price=None,
            edge=None,
            confidence=Decimal("0"),
            suggested_notional=None,
            market_quality_score=snapshot.market_quality_score or Decimal("0"),
            reason_codes=["PARSER_FAILED"],
            risk_flags=flags,
            expires_at=now + SIGNAL_TTL,
            snapshot_id=snapshot.id,
        )
        return V2StrategyResult(
            signal=signal,
            raw_json={
                "strategy_code": self.strategy_code,
                "strategy_version": STRATEGY_VERSION,
                "snapshot_id": snapshot.id,
                "decision": {
                    "action": "BLOCKED",
                    "side": None,
                    "blocked_reason": "PARSER_FAILED",
                    "risk_flags": flags,
                },
                "decision_trace": ["PARSER_FAILED"],
                "parse": parsed.raw_parse,
            },
        )

    def evaluate(
        self,
        *,
        market: PredictionMarket,
        event: PredictionEvent | None,
        snapshot: MarketSnapshot,
        spec: CryptoMarketSpec,
        asset_snapshot: CryptoAssetSnapshot,
        yes_orderbook: PredictionOrderBookSnapshot,
        no_orderbook: PredictionOrderBookSnapshot,
        current_position: PositionState | None,
        equity: Decimal,
    ) -> V2StrategyResult:
        now = utcnow()
        market_quality = snapshot.market_quality_score or Decimal("0")
        estimate = estimate_probability(
            spec,
            asset_snapshot,
            now=now,
            market_mid=_float_or_none(yes_orderbook.mid),
            spread=_float_or_none(yes_orderbook.spread),
        )
        yes_gate = evaluate_execution_gate(
            spec=spec,
            asset_snapshot=asset_snapshot,
            orderbook=yes_orderbook,
            estimate=estimate,
            side="YES",
            market_quality_score=market_quality,
            now=now,
        )
        no_gate = evaluate_execution_gate(
            spec=spec,
            asset_snapshot=asset_snapshot,
            orderbook=no_orderbook,
            estimate=estimate,
            side="NO",
            market_quality_score=market_quality,
            now=now,
        )
        candidate = _best_gate(yes_gate, no_gate)
        if candidate is None:
            if current_position is not None:
                return self._manage_existing_position(
                    market=market,
                    snapshot=snapshot,
                    spec=spec,
                    asset_snapshot=asset_snapshot,
                    yes_orderbook=yes_orderbook,
                    no_orderbook=no_orderbook,
                    estimate=estimate,
                    yes_gate=yes_gate,
                    no_gate=no_gate,
                    current_position=current_position,
                    equity=equity,
                )
            return self._non_buy_result(
                market=market,
                snapshot=snapshot,
                spec=spec,
                asset_snapshot=asset_snapshot,
                yes_orderbook=yes_orderbook,
                no_orderbook=no_orderbook,
                estimate=estimate,
                yes_gate=yes_gate,
                no_gate=no_gate,
                action="OBSERVE",
                risk_flags=_dedupe([*yes_gate.risk_flags, *no_gate.risk_flags]),
                reason_codes=["NO_EXECUTABLE_EDGE"],
            )

        notional = suggested_notional(
            equity=equity,
            p=candidate.p_trade,
            price=float(candidate.executable_price or 0),
            edge_stress=candidate.edge_stress,
            market_quality_score=float(market_quality),
            parser_confidence=spec.parser_confidence,
            liquidity_multiplier=1.0,
            existing_exposure_multiplier=1.0,
            market_type=spec.market_type,
            config=SizingConfig(),
        )
        selected_book = yes_orderbook if candidate.side == "YES" else no_orderbook
        final_gate = evaluate_execution_gate(
            spec=spec,
            asset_snapshot=asset_snapshot,
            orderbook=selected_book,
            estimate=estimate,
            side=candidate.side,
            market_quality_score=market_quality,
            intended_notional=notional,
            now=now,
        )
        if not final_gate.allowed or notional <= 0:
            if current_position is not None:
                return self._manage_existing_position(
                    market=market,
                    snapshot=snapshot,
                    spec=spec,
                    asset_snapshot=asset_snapshot,
                    yes_orderbook=yes_orderbook,
                    no_orderbook=no_orderbook,
                    estimate=estimate,
                    yes_gate=yes_gate,
                    no_gate=no_gate,
                    current_position=current_position,
                    equity=equity,
                )
            risk_flags = final_gate.risk_flags or ["SIZE_BELOW_MIN_NOTIONAL"]
            return self._non_buy_result(
                market=market,
                snapshot=snapshot,
                spec=spec,
                asset_snapshot=asset_snapshot,
                yes_orderbook=yes_orderbook,
                no_orderbook=no_orderbook,
                estimate=estimate,
                yes_gate=yes_gate,
                no_gate=no_gate,
                action="BLOCKED",
                risk_flags=risk_flags,
                reason_codes=final_gate.reason_codes,
                selected_gate=final_gate,
            )

        exit_bid = selected_book.best_bid
        lifecycle = decide_lifecycle_action(
            current_position=current_position,
            target_side=candidate.side,
            edge_exec=final_gate.edge_exec,
            edge_stress=final_gate.edge_stress,
            required_edge=final_gate.required_edge,
            p_trade=final_gate.p_trade,
            p_entry=current_position.opened_probability if current_position else None,
            executable_buy_price=final_gate.executable_price,
            exit_bid=exit_bid,
            now=now,
            window_end=spec.window_end,
        )
        executable_price = (
            final_gate.executable_price
            if lifecycle.action == "BUY"
            else _exit_price(lifecycle.side, yes_orderbook, no_orderbook)
        )
        suggested = _suggested_notional_for_action(
            lifecycle.action,
            notional,
            current_position,
            executable_price,
            lifecycle.reduce_fraction,
        )
        signal = StrategySignal(
            market_id=market.id,
            strategy_code=self.strategy_code,
            action=lifecycle.action,
            side=lifecycle.side,
            model_probability=Decimal(str(round(estimate.p_calibrated, 8))),
            executable_price=executable_price,
            edge=Decimal(str(round(final_gate.edge_exec, 8))),
            confidence=Decimal(str(round(estimate.confidence, 8))),
            suggested_notional=suggested,
            market_quality_score=market_quality,
            reason_codes=[*final_gate.reason_codes, *lifecycle.reason_codes],
            risk_flags=lifecycle.risk_flags,
            expires_at=now + SIGNAL_TTL,
            snapshot_id=snapshot.id,
        )
        return V2StrategyResult(
            signal=signal,
            raw_json=self._trace(
                snapshot=snapshot,
                spec=spec,
                asset_snapshot=asset_snapshot,
                yes_orderbook=yes_orderbook,
                no_orderbook=no_orderbook,
                estimate=estimate,
                gate=final_gate,
                action=lifecycle.action,
                side=lifecycle.side,
                suggested_notional=suggested,
                equity=equity,
                risk_flags=lifecycle.risk_flags,
                blocked_reason=None,
            ),
        )

    def _manage_existing_position(
        self,
        *,
        market: PredictionMarket,
        snapshot: MarketSnapshot,
        spec: CryptoMarketSpec,
        asset_snapshot: CryptoAssetSnapshot,
        yes_orderbook: PredictionOrderBookSnapshot,
        no_orderbook: PredictionOrderBookSnapshot,
        estimate: ProbabilityEstimate,
        yes_gate: ExecutionDecision,
        no_gate: ExecutionDecision,
        current_position: PositionState,
        equity: Decimal,
    ) -> V2StrategyResult:
        now = utcnow()
        held_book = yes_orderbook if current_position.side == "YES" else no_orderbook
        held_probability = (
            estimate.p_calibrated
            if current_position.side == "YES"
            else 1.0 - estimate.p_calibrated
        )
        stress_probability = (
            min(estimate.p_low, estimate.p_calibrated, estimate.p_high)
            if current_position.side == "YES"
            else min(1.0 - estimate.p_low, 1.0 - estimate.p_calibrated, 1.0 - estimate.p_high)
        )
        exit_bid = held_book.best_bid
        edge_exec = held_probability - float(held_book.best_ask or Decimal("1"))
        edge_stress = stress_probability - float(exit_bid or Decimal("1"))
        lifecycle = decide_lifecycle_action(
            current_position=current_position,
            target_side=current_position.side,
            edge_exec=edge_exec,
            edge_stress=edge_stress,
            required_edge=0.0,
            p_trade=held_probability,
            p_entry=current_position.opened_probability,
            executable_buy_price=None,
            exit_bid=exit_bid,
            now=now,
            window_end=spec.window_end,
        )
        selected_gate = yes_gate if current_position.side == "YES" else no_gate
        executable_price = _exit_price(lifecycle.side, yes_orderbook, no_orderbook)
        suggested = _suggested_notional_for_action(
            lifecycle.action,
            Decimal("0"),
            current_position,
            executable_price,
            lifecycle.reduce_fraction,
        )
        signal = StrategySignal(
            market_id=market.id,
            strategy_code=self.strategy_code,
            action=lifecycle.action,
            side=lifecycle.side,
            model_probability=Decimal(str(round(estimate.p_calibrated, 8))),
            executable_price=executable_price,
            edge=Decimal(str(round(edge_exec, 8))),
            confidence=Decimal(str(round(estimate.confidence, 8))),
            suggested_notional=suggested,
            market_quality_score=snapshot.market_quality_score or Decimal("0"),
            reason_codes=[*selected_gate.reason_codes, *lifecycle.reason_codes],
            risk_flags=lifecycle.risk_flags,
            expires_at=now + SIGNAL_TTL,
            snapshot_id=snapshot.id,
        )
        trace_gate = ExecutionDecision(
            allowed=selected_gate.allowed,
            side=current_position.side,  # type: ignore[arg-type]
            executable_price=executable_price,
            market_mid=selected_gate.market_mid,
            edge_mid=selected_gate.edge_mid,
            edge_exec=edge_exec,
            edge_stress=edge_stress,
            required_edge=selected_gate.required_edge,
            p_trade=held_probability,
            p_stress=stress_probability,
            reason_codes=selected_gate.reason_codes,
            risk_flags=selected_gate.risk_flags,
        )
        return V2StrategyResult(
            signal=signal,
            raw_json=self._trace(
                snapshot=snapshot,
                spec=spec,
                asset_snapshot=asset_snapshot,
                yes_orderbook=yes_orderbook,
                no_orderbook=no_orderbook,
                estimate=estimate,
                gate=trace_gate,
                action=lifecycle.action,
                side=lifecycle.side,
                suggested_notional=suggested,
                equity=equity,
                risk_flags=lifecycle.risk_flags,
                blocked_reason=None,
            ),
        )

    def _non_buy_result(
        self,
        *,
        market: PredictionMarket,
        snapshot: MarketSnapshot,
        spec: CryptoMarketSpec,
        asset_snapshot: CryptoAssetSnapshot,
        yes_orderbook: PredictionOrderBookSnapshot,
        no_orderbook: PredictionOrderBookSnapshot,
        estimate: ProbabilityEstimate,
        yes_gate: ExecutionDecision,
        no_gate: ExecutionDecision,
        action: str,
        risk_flags: list[str],
        reason_codes: list[str],
        selected_gate: ExecutionDecision | None = None,
    ) -> V2StrategyResult:
        now = utcnow()
        gate = selected_gate or yes_gate
        signal = StrategySignal(
            market_id=market.id,
            strategy_code=self.strategy_code,
            action=action,
            side=None,
            model_probability=Decimal(str(round(estimate.p_calibrated, 8))),
            executable_price=None,
            edge=Decimal(str(round(max(yes_gate.edge_exec, no_gate.edge_exec), 8))),
            confidence=Decimal(str(round(estimate.confidence, 8))),
            suggested_notional=None,
            market_quality_score=snapshot.market_quality_score or Decimal("0"),
            reason_codes=reason_codes,
            risk_flags=risk_flags,
            expires_at=now + SIGNAL_TTL,
            snapshot_id=snapshot.id,
        )
        return V2StrategyResult(
            signal=signal,
            raw_json=self._trace(
                snapshot=snapshot,
                spec=spec,
                asset_snapshot=asset_snapshot,
                yes_orderbook=yes_orderbook,
                no_orderbook=no_orderbook,
                estimate=estimate,
                gate=gate,
                action=action,
                side=None,
                suggested_notional=None,
                risk_flags=risk_flags,
                blocked_reason="EXECUTION_GATE_BLOCKED" if action == "BLOCKED" else None,
            ),
        )

    def _trace(
        self,
        *,
        snapshot: MarketSnapshot,
        spec: CryptoMarketSpec,
        asset_snapshot: CryptoAssetSnapshot,
        yes_orderbook: PredictionOrderBookSnapshot,
        no_orderbook: PredictionOrderBookSnapshot,
        estimate: ProbabilityEstimate,
        gate: ExecutionDecision,
        action: str,
        side: str | None,
        suggested_notional: Decimal | None,
        equity: Decimal | None = None,
        risk_flags: list[str],
        blocked_reason: str | None,
    ) -> dict[str, Any]:
        return {
            "strategy_code": self.strategy_code,
            "strategy_version": STRATEGY_VERSION,
            "snapshot_id": snapshot.id,
            "market_spec": {
                "asset": spec.asset,
                "market_type": spec.market_type,
                "threshold": str(spec.threshold) if spec.threshold is not None else None,
                "lower_threshold": str(spec.lower_threshold) if spec.lower_threshold is not None else None,
                "upper_threshold": str(spec.upper_threshold) if spec.upper_threshold is not None else None,
                "window_end": spec.window_end.isoformat(),
                "parser_confidence": spec.parser_confidence,
                "ambiguity_flags": spec.ambiguity_flags,
            },
            "asset_market_data": {
                "source": asset_snapshot.source,
                "spot_mid": str(asset_snapshot.spot_mid),
                "realized_vol_7d": asset_snapshot.realized_vol_7d,
                "realized_vol_30d": asset_snapshot.realized_vol_30d,
                "realized_vol_90d": asset_snapshot.realized_vol_90d,
                "selected_vol": estimate.diagnostics.get("selected_vol"),
                "momentum_24h": asset_snapshot.momentum_24h,
                "age_seconds": _age_seconds(asset_snapshot.ts),
            },
            "prediction_orderbook": {
                "yes_best_bid": _str_or_none(yes_orderbook.best_bid),
                "yes_best_ask": _str_or_none(yes_orderbook.best_ask),
                "no_best_bid": _str_or_none(no_orderbook.best_bid),
                "no_best_ask": _str_or_none(no_orderbook.best_ask),
                "spread": _str_or_none(yes_orderbook.spread),
                "age_seconds": _age_seconds(yes_orderbook.ts),
                "depth_to_100_usd": _str_or_none(yes_orderbook.depth_to_100_usd),
            },
            "probability": {
                "model_family": estimate.model_family,
                "p_raw": estimate.p_raw,
                "p_after_trend": estimate.diagnostics.get("p_after_trend"),
                "p_calibrated": estimate.p_calibrated,
                "p_low": estimate.p_low,
                "p_high": estimate.p_high,
                "p_stress": gate.p_stress,
                "uncertainty_penalty": estimate.uncertainty_penalty,
            },
            "edge": {
                "market_mid": gate.market_mid,
                "executable_price": float(gate.executable_price) if gate.executable_price is not None else None,
                "edge_mid": gate.edge_mid,
                "edge_exec": gate.edge_exec,
                "edge_stress": gate.edge_stress,
                "required_edge": gate.required_edge,
            },
            "sizing": {
                "equity": str(equity) if equity is not None else None,
                "kelly_fraction": 0.20,
                "final_notional": str(suggested_notional) if suggested_notional is not None else None,
            },
            "decision": {
                "action": action,
                "side": side,
                "limit_price": float(gate.executable_price) if gate.executable_price is not None else None,
                "risk_flags": risk_flags,
                "blocked_reason": blocked_reason,
            },
            "decision_trace": [*gate.reason_codes, action],
        }


def _best_gate(yes_gate: ExecutionDecision, no_gate: ExecutionDecision) -> ExecutionDecision | None:
    candidates = [gate for gate in (yes_gate, no_gate) if gate.allowed]
    if not candidates:
        return None
    return max(candidates, key=lambda gate: gate.edge_exec)


def _suggested_notional_for_action(
    action: str,
    notional: Decimal,
    current_position: PositionState | None,
    executable_price: Decimal | None,
    reduce_fraction: float | None,
) -> Decimal | None:
    if action == "BUY":
        return notional
    if action == "EXIT" and current_position is not None and executable_price is not None:
        return (current_position.quantity * executable_price).quantize(Decimal("0.000001"))
    if action == "REDUCE" and current_position is not None and executable_price is not None:
        fraction = Decimal(str(reduce_fraction or 0.50))
        return (current_position.quantity * fraction * executable_price).quantize(Decimal("0.000001"))
    return None


def _exit_price(
    side: str | None,
    yes_orderbook: PredictionOrderBookSnapshot,
    no_orderbook: PredictionOrderBookSnapshot,
) -> Decimal | None:
    if side == "YES":
        return yes_orderbook.best_bid
    if side == "NO":
        return no_orderbook.best_bid
    return None


def _str_or_none(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _float_or_none(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _age_seconds(ts) -> float:
    now = utcnow()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=now.tzinfo)
    return max((now - ts).total_seconds(), 0.0)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
