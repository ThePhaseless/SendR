from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, inspect

from app import app, run_migrations
from config import settings
from security import clear_session_cookie, set_session_cookie

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


def test_cors_middleware_allows_password_protected_download_header() -> None:
    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )

    assert cors_middleware.kwargs["allow_credentials"] is True
    assert "X-Access-Token" in cors_middleware.kwargs["allow_headers"]


def test_set_session_cookie_uses_configured_cookie_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    response = Response()

    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "sendr.email")
    set_session_cookie(response, "raw-token", expires_at)

    cookie_headers = response.headers.getlist("set-cookie")

    assert len(cookie_headers) == 2
    assert all("Domain=sendr.email" in header for header in cookie_headers)


def test_clear_session_cookie_uses_configured_cookie_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Response()

    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "sendr.email")
    clear_session_cookie(response)

    cookie_headers = response.headers.getlist("set-cookie")

    assert len(cookie_headers) == 2
    assert all("Domain=sendr.email" in header for header in cookie_headers)
