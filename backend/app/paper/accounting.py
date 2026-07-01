from __future__ import annotations

from decimal import Decimal


def realized_pnl(avg_price: Decimal, fill_price: Decimal, quantity: Decimal, fee: Decimal) -> Decimal:
    return (fill_price - avg_price) * quantity - fee


def unrealized_pnl(avg_price: Decimal, mark_price: Decimal, quantity: Decimal) -> Decimal:
    return (mark_price - avg_price) * quantity

