from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


class SessionFactory:
    def __init__(self, engine: AsyncEngine):
        self.bind = engine
        self._maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    def __call__(self) -> AsyncSession:
        return self._maker()


def create_sessionmaker(database_url: str | None = None) -> SessionFactory:
    url = database_url or get_settings().database_url
    kwargs: dict[str, Any] = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_async_engine(url, **kwargs)
    return SessionFactory(engine)


@lru_cache(maxsize=1)
def get_session_factory() -> SessionFactory:
    return create_sessionmaker()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    import app.db.models  # noqa: F401

    async with get_session_factory().bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

