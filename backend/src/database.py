from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _make_async_url(url: str) -> str:
    """Ensure the URL uses an async driver and compatible parameters for PostgreSQL."""
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if url.startswith("postgresql+asyncpg://") and "sslmode=" in url:
        url = url.replace("sslmode=", "ssl=", 1)

    return url


def build_async_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(_make_async_url(database_url), echo=echo)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


engine = build_async_engine(settings.DATABASE_URL, echo=False)
async_session: async_sessionmaker[AsyncSession] = create_session_factory(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


def get_session_context() -> AsyncSession:
    """Context manager for use outside of FastAPI dependency injection."""
    return async_session()
