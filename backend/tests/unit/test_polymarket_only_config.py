from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import RuntimeConfig
from app.db.models import Venue
from app.db.session import Base, create_sessionmaker
from app.services.bootstrap import ensure_default_venues


def test_default_radar_protocols_are_polymarket_only() -> None:
    assert RuntimeConfig().radar.protocols == ["POLYMARKET"]


@pytest.mark.asyncio
async def test_default_venues_create_polymarket_only(tmp_path) -> None:
    sessionmaker = create_sessionmaker(f"sqlite+aiosqlite:///{tmp_path / 'venues.db'}")
    async with sessionmaker.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with sessionmaker() as session:
            await ensure_default_venues(session)
            await session.commit()

            venues = list((await session.execute(select(Venue))).scalars())

        assert [venue.code for venue in venues] == ["POLYMARKET"]
    finally:
        await sessionmaker.bind.dispose()
