from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

logger = logging.getLogger(__name__)
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def sync_database_url(url: str) -> str:
    return url.replace("+aiosqlite", "").replace("+asyncpg", "")


def run_migrations_for_url(database_url: str) -> None:
    logger.info("Running database migrations...")
    cfg = Config(str(_ALEMBIC_INI))
    sync_url = sync_database_url(database_url)
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
