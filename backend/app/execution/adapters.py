from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LiveOrderRequest(BaseModel):
    market_id: str
    side: str
    outcome_index: int
    limit_price: float
    quantity: float


class LiveOrderResult(BaseModel):
    external_order_id: str
    status: str


class LiveOrder(BaseModel):
    external_order_id: str
    status: str


class VenueBalance(BaseModel):
    currency: str
    available: float


class ExecutionAdapter(Protocol):
    venue_code: str

    async def place_limit_order(self, order: LiveOrderRequest) -> LiveOrderResult:
        ...

    async def cancel_order(self, external_order_id: str) -> None:
        ...

    async def get_open_orders(self) -> list[LiveOrder]:
        ...

    async def get_balances(self) -> list[VenueBalance]:
        ...

