from __future__ import annotations

from decimal import Decimal


def buy_fill_price(executable_ask: Decimal, slippage_bps: int) -> Decimal:
    return executable_ask * (Decimal("1") + Decimal(slippage_bps) / Decimal("10000"))


def sell_fill_price(executable_bid: Decimal, slippage_bps: int) -> Decimal:
    return executable_bid * (Decimal("1") - Decimal(slippage_bps) / Decimal("10000"))

