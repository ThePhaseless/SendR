import sys
from pathlib import Path

# Add the src directory to the path so tests can import backend modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import database  # noqa: E402
from config import settings  # noqa: E402
from models import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    AuthToken,
    User,
    UserTier,
)
from security import create_access_token, hash_token  # noqa: E402

# Use a temp file for the test database (aiosqlite needs a file path or :memory:)
_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


async def _get_test_session():
    async with _test_session_factory() as session:
        yield session


@pytest.fixture(autouse=True, scope="session")
def _patch_db():
    """Replace the database engine/session with test versions for all tests."""
    database.engine = _test_engine
    database.async_session = _test_session_factory
    database.get_session = _get_test_session


@pytest.fixture(autouse=True)
async def _init_tables(tmp_path):
    """Create all tables before each test and drop them after."""
    import models  # noqa: F401

    async with _test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Use a temp upload dir per test
    original_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path / "uploads")
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    yield

    settings.UPLOAD_DIR = original_upload_dir
    async with _test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
async def auth_headers():
    """Create a test user and return auth headers with a valid token."""
    async with _test_session_factory() as session:
        user = User(email="test@sendr.local", tier=UserTier.temporary)
        session.add(user)
        await session.flush()

        raw_token, expires_at = create_access_token(user.id)
        auth_token = AuthToken(
            user_id=user.id,
            token=hash_token(raw_token),
            expires_at=expires_at,
        )
        session.add(auth_token)
        await session.commit()

    return {"Authorization": f"Bearer {raw_token}"}
