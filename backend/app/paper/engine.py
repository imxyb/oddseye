from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

PRICE_Q = Decimal("0.000001")
MONEY_Q = Decimal("0.000001")


@dataclass
class SnapshotQuote:
    id: int
    market_id: UUID | str
    ts: datetime
    outcome0_best_bid: Decimal | None
    outcome0_best_ask: Decimal | None
    outcome1_best_bid: Decimal | None
    outcome1_best_ask: Decimal | None


@dataclass
class PaperAccountState:
    id: UUID | str
    cash: Decimal
    starting_cash: Decimal


@dataclass
class PaperOrderRequest:
    account_id: UUID | str
    market_id: UUID | str
    side: str
    outcome_index: int
    limit_price: Decimal
    quantity: Decimal
    signal_id: UUID | str | None = None


@dataclass
class PaperFillState:
    price: Decimal
    quantity: Decimal
    notional: Decimal
    fee: Decimal
    snapshot_id: int


@dataclass
class PaperPositionState:
    account_id: UUID | str
    market_id: UUID | str
    outcome_index: int
    quantity: Decimal
    avg_price: Decimal
    mark_price: Decimal | None = None
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    status: str = "open"


@dataclass
class FillResult:
    fill: PaperFillState
    account: PaperAccountState
    position: PaperPositionState


class PaperTradingEngine:
    def __init__(self, slippage_bps: int = 25, fee_bps: int = 0):
        self.slippage = Decimal(slippage_bps) / Decimal("10000")
        self.fee_rate = Decimal(fee_bps) / Decimal("10000")
        self._positions: dict[tuple[str, str, int], PaperPositionState] = {}

    def open_position(
        self,
        account_id: UUID | str,
        market_id: UUID | str,
        outcome_index: int,
        quantity: Decimal,
        avg_price: Decimal,
        realized_pnl: Decimal = Decimal("0"),
        unrealized_pnl: Decimal = Decimal("0"),
    ) -> PaperPositionState:
        position = PaperPositionState(
            account_id=account_id,
            market_id=market_id,
            outcome_index=outcome_index,
            quantity=quantity,
            avg_price=avg_price,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
        )
        self._positions[self._key(account_id, market_id, outcome_index)] = position
        return position

    def try_fill(
        self,
        account: PaperAccountState,
        order: PaperOrderRequest,
        snapshot: SnapshotQuote,
    ) -> FillResult | None:
        executable = self._executable_price(order, snapshot)
        if executable is None:
            return None
        if order.side.upper() == "BUY" and executable > order.limit_price:
            return None
        if order.side.upper() == "SELL" and executable < order.limit_price:
            return None
        if order.side.upper() == "SELL" and not self._has_inventory(order):
            return None

        fill_price = self._apply_slippage(executable, order.side)
        notional = (fill_price * order.quantity).quantize(MONEY_Q)
        fee = (notional * self.fee_rate).quantize(MONEY_Q)
        if order.side.upper() == "BUY":
            if account.cash < notional + fee:
                return None
            account.cash = (account.cash - notional - fee).quantize(MONEY_Q)
        else:
            account.cash = (account.cash + notional - fee).quantize(MONEY_Q)

        position = self._apply_position(account, order, fill_price, snapshot, fee)
        return FillResult(
            fill=PaperFillState(
                price=fill_price,
                quantity=order.quantity,
                notional=notional,
                fee=fee,
                snapshot_id=snapshot.id,
            ),
            account=account,
            position=position,
        )

    def mark_position(
        self,
        position: PaperPositionState,
        snapshot: SnapshotQuote,
        conservative: bool = True,
    ) -> PaperPositionState:
        mark = self._mark_price(position.outcome_index, snapshot, conservative)
        position.mark_price = mark
        if mark is not None:
            position.unrealized_pnl = ((mark - position.avg_price) * position.quantity).quantize(
                MONEY_Q
            )
        return position

    def _apply_position(
        self,
        account: PaperAccountState,
        order: PaperOrderRequest,
        fill_price: Decimal,
        snapshot: SnapshotQuote,
        fee: Decimal,
    ) -> PaperPositionState:
        key = self._key(order.account_id, order.market_id, order.outcome_index)
        position = self._positions.get(
            key,
            PaperPositionState(
                account_id=order.account_id,
                market_id=order.market_id,
                outcome_index=order.outcome_index,
                quantity=Decimal("0"),
                avg_price=Decimal("0"),
            ),
        )
        if order.side.upper() == "BUY":
            previous_cost = position.avg_price * position.quantity
            new_quantity = position.quantity + order.quantity
            position.avg_price = ((previous_cost + fill_price * order.quantity) / new_quantity).quantize(
                PRICE_Q
            )
            position.quantity = new_quantity
            position.status = "open"
        else:
            sell_quantity = min(order.quantity, position.quantity)
            position.realized_pnl = (
                position.realized_pnl + (fill_price - position.avg_price) * sell_quantity - fee
            ).quantize(MONEY_Q)
            position.quantity = position.quantity - sell_quantity
            if position.quantity == 0:
                position.status = "closed"
        self.mark_position(position, snapshot)
        self._positions[key] = position
        return position

    def _executable_price(
        self, order: PaperOrderRequest, snapshot: SnapshotQuote
    ) -> Decimal | None:
        side = order.side.upper()
        if side == "BUY" and order.outcome_index == 0:
            return snapshot.outcome0_best_ask
        if side == "SELL" and order.outcome_index == 0:
            return snapshot.outcome0_best_bid
        if side == "BUY" and order.outcome_index == 1:
            return snapshot.outcome1_best_ask
        if side == "SELL" and order.outcome_index == 1:
            return snapshot.outcome1_best_bid
        return None

    def _has_inventory(self, order: PaperOrderRequest) -> bool:
        position = self._positions.get(self._key(order.account_id, order.market_id, order.outcome_index))
        return position is not None and position.quantity >= order.quantity

    def _apply_slippage(self, price: Decimal, side: str) -> Decimal:
        multiplier = Decimal("1") + self.slippage if side.upper() == "BUY" else Decimal("1") - self.slippage
        return (price * multiplier).quantize(PRICE_Q)

    def _mark_price(
        self, outcome_index: int, snapshot: SnapshotQuote, conservative: bool
    ) -> Decimal | None:
        bid = snapshot.outcome0_best_bid if outcome_index == 0 else snapshot.outcome1_best_bid
        ask = snapshot.outcome0_best_ask if outcome_index == 0 else snapshot.outcome1_best_ask
        if conservative:
            return bid
        if bid is not None and ask is not None:
            return ((bid + ask) / Decimal("2")).quantize(PRICE_Q)
        return bid or ask

    def _key(self, account_id: UUID | str, market_id: UUID | str, outcome_index: int) -> tuple[str, str, int]:
        return (str(account_id), str(market_id), outcome_index)
