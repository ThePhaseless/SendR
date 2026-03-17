import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from config import settings
from models import FileUpload, _utcnow

logger = logging.getLogger(__name__)


async def cleanup_expired_files(session: AsyncSession) -> int:
    """Delete files that are past the grace period. Returns number of files cleaned up."""
    cutoff = _utcnow() - timedelta(days=settings.FILE_GRACE_PERIOD_DAYS)

    stmt = select(FileUpload).where(
        FileUpload.expires_at < cutoff,
        FileUpload.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    expired_files = result.scalars().all()

    cleaned = 0
    upload_dir = Path(settings.UPLOAD_DIR)

    for file_upload in expired_files:
        # Delete from disk
        file_path = upload_dir / file_upload.stored_filename
        if file_path.exists():
            file_path.unlink()
            logger.info("Deleted expired file: %s", file_path)

        # Mark as inactive
        file_upload.is_active = False
        session.add(file_upload)
        cleaned += 1

    if cleaned > 0:
        await session.commit()
        logger.info("Cleaned up %d expired files", cleaned)

    return cleaned
