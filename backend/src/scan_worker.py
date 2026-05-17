from __future__ import annotations

import asyncio
import logging

from app import run_migrations
from config import settings
from scan_queue import ensure_upload_directories, process_next_queued_upload

logger = logging.getLogger(__name__)


async def run_scan_worker() -> None:
    run_migrations()
    ensure_upload_directories()

    while True:
        try:
            processed = await process_next_queued_upload()
        except Exception:
            logger.exception("Scan worker iteration failed")
            processed = False

        if not processed:
            await asyncio.sleep(settings.SCAN_QUEUE_POLL_SECONDS)


def main() -> None:
    asyncio.run(run_scan_worker())


if __name__ == "__main__":
    main()
