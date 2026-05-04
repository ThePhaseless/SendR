from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine, inspect

from app import run_migrations
from config import settings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_migrations_create_current_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migration-schema.db"
    sync_url = f"sqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    monkeypatch.setattr(settings, "DATABASE_URL", async_url)
    run_migrations()

    sync_engine = create_engine(sync_url)
    try:
        inspector = inspect(sync_engine)
        tables = set(inspector.get_table_names())
        assert {
            "downloadlog",
            "fileupload",
            "transfer",
            "uploadgroupsettings",
            "user",
        } <= tables

        file_columns = {
            column["name"] for column in inspector.get_columns("fileupload")
        }
        assert {
            "content_hash",
            "public_download_count",
            "restricted_download_count",
            "upload_group",
        } <= file_columns
    finally:
        sync_engine.dispose()
