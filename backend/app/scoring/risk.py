from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal


def can_open_auto_paper_trade(
    quality_score: Decimal,
    spread: Decimal | None,
    closes_at: datetime | None,
    now: datetime,
) -> tuple[bool, list[str]]:
    flags: list[str] = []
    if quality_score < Decimal("65"):
        flags.append("QUALITY_BELOW_GATE")
    if spread is None or spread > Decimal("0.08"):
        flags.append("WIDE_SPREAD")
    if closes_at is None or closes_at <= now + timedelta(minutes=30):
        flags.append("CLOSES_TOO_SOON")
    return not flags, flags

