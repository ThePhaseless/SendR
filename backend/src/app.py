from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from hmac import compare_digest
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from db_migrations import run_migrations_for_url
from errors import http_exception_handler
from routers import admin, altcha, auth, dev, files, subscription

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response as StarletteResponse


def run_migrations() -> None:
    run_migrations_for_url(settings.DATABASE_URL)


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


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok"}


app.include_router(admin.router)
app.include_router(altcha.router)
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(subscription.router)

if settings.is_local and settings.DEV_LOGIN_ENABLED:
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
