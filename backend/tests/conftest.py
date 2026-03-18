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

# Use a temp file for the test database (aiosqlite needs a file path or :memory:)
_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_test_session_factory = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


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
    # Import models so metadata is populated, rebuild schemas for Pydantic
    from datetime import datetime

    import models  # noqa: F401
    import schemas  # noqa: F401

    # datetime is imported under TYPE_CHECKING in schemas.py, so inject it
    schemas.datetime = datetime  # type: ignore[attr-defined]
    schemas.FileUploadResponse.model_rebuild()
    schemas.MultiFileUploadResponse.model_rebuild()
    schemas.UploadGroupInfoResponse.model_rebuild()
    schemas.TokenResponse.model_rebuild()

    async with _test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Use a temp upload dir per test
    original_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path / "uploads")
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    yield

    async with _test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    settings.UPLOAD_DIR = original_upload_dir
