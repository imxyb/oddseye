from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import PaperAccount, Venue


async def ensure_default_venues(session: AsyncSession) -> None:
    for code, name in {"POLYMARKET": "Polymarket", "KALSHI": "Kalshi"}.items():
        existing = await session.scalar(select(Venue).where(Venue.code == code))
        if existing is None:
            session.add(Venue(code=code, name=name, supports_execution=False))


async def ensure_default_paper_account(session: AsyncSession) -> PaperAccount:
    existing = await session.scalar(select(PaperAccount).where(PaperAccount.name == "Default"))
    if existing is not None:
        return existing
    paper = get_settings().config.paper
    account = PaperAccount(
        name="Default",
        starting_cash=Decimal(str(paper.starting_cash)),
        cash=Decimal(str(paper.starting_cash)),
        currency=paper.currency,
    )
    session.add(account)
    await session.flush()
    return account

