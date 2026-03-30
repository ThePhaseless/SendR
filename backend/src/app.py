import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from alembic import command
from config import settings
from routers import admin, altcha, auth, dev, files, subscription

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _run_migrations() -> None:
    logger.info("Running database migrations...")
    cfg = Config(str(_ALEMBIC_INI))
    sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    cfg.attributes["skip_logging_config"] = True

    # If the DB has tables but no alembic_version (created by old init_db),
    # stamp it at head so alembic doesn't try to re-create everything.
    from sqlalchemy import create_engine, inspect

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        has_alembic = "alembic_version" in tables
        has_app_tables = "user" in tables

        if has_app_tables and not has_alembic:
            logger.info("Existing database without alembic tracking detected, stamping at head...")
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
    engine.dispose()

    logger.info("Database migrations complete.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _run_migrations()
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
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type", "authorization"],
)

app.include_router(admin.router)
app.include_router(altcha.router)
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(subscription.router)

if settings.DEV_MODE:
    app.include_router(dev.router)

if STATIC_DIR.is_dir():
    _resolved_static = STATIC_DIR.resolve()
    app.mount("/assets", StaticFiles(directory=str(_resolved_static / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(_request: Request, full_path: str):  # noqa: ARG001
        file_path = (STATIC_DIR / full_path).resolve()
        if not str(file_path).startswith(str(_resolved_static)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_resolved_static / "index.html"))
