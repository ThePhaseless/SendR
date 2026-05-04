from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from hmac import compare_digest
from pathlib import Path
from typing import TYPE_CHECKING, cast

from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, inspect
from starlette.exceptions import HTTPException as StarletteHTTPException

from alembic import command
from config import settings
from errors import http_exception_handler
from routers import admin, altcha, auth, dev, files, subscription

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response as StarletteResponse


def _sync_database_url(url: str) -> str:
    return url.replace("+aiosqlite", "").replace("+asyncpg", "")


def run_migrations() -> None:
    logger.info("Running database migrations...")
    cfg = Config(str(_ALEMBIC_INI))
    sync_url = _sync_database_url(settings.DATABASE_URL)
    cfg.set_main_option("sqlalchemy.url", sync_url)
    cfg.attributes["skip_logging_config"] = True

    engine = create_engine(sync_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            if "user" in tables and "alembic_version" not in tables:
                logger.info(
                    "Existing schema without Alembic tracking detected; "
                    "stamping at head."
                )
                command.stamp(cfg, "head")
            else:
                command.upgrade(cfg, "head")
    finally:
        engine.dispose()

    logger.info("Database migrations complete.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    yield


app = FastAPI(
    title="SendR API",
    description="WeTransfer-like file sharing service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type", "authorization", settings.CSRF_HEADER_NAME],
)


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return await http_exception_handler(request, cast("StarletteHTTPException", exc))


app.add_exception_handler(StarletteHTTPException, _http_exception_handler)


@app.middleware("http")
async def enforce_cookie_csrf(
    request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]
) -> StarletteResponse:
    if (
        request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and request.url.path.startswith("/api/")
        and settings.SESSION_COOKIE_NAME in request.cookies
    ):
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(settings.CSRF_HEADER_NAME)
        if (
            not csrf_cookie
            or not csrf_header
            or not compare_digest(csrf_cookie, csrf_header)
        ):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": {
                        "code": "CSRF_FAILED",
                        "message": "Invalid CSRF token.",
                    }
                },
            )

    return await call_next(request)


app.include_router(admin.router)
app.include_router(altcha.router)
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(subscription.router)

if settings.is_local:
    app.include_router(dev.router)

if STATIC_DIR.is_dir():
    _resolved_static = STATIC_DIR.resolve()
    app.mount(
        "/assets",
        StaticFiles(directory=str(_resolved_static / "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(_request: Request, full_path: str):  # noqa: ARG001
        file_path = (STATIC_DIR / full_path).resolve()
        if not str(file_path).startswith(str(_resolved_static)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
            )
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_resolved_static / "index.html"))
