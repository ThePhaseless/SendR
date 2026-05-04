from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


def get_session_context() -> AsyncSession:
    """Context manager for use outside of FastAPI dependency injection."""
    return async_session()
