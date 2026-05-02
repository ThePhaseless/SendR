import logging
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import and_, func, or_, select

from config import settings
from models import FileUpload, _utcnow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def cleanup_expired_files(session: AsyncSession) -> int:
    """Delete files that are past the grace period. Returns number of files cleaned up."""
    now = _utcnow()
    cutoff = now - timedelta(days=settings.FILE_GRACE_PERIOD_DAYS)
    owned_cutoff = now - timedelta(days=max(settings.FILE_GRACE_PERIOD_DAYS, settings.PREMIUM_REFRESH_GRACE_DAYS))

    stmt = select(FileUpload).where(
        FileUpload.is_active == True,  # noqa: E712
        or_(
            and_(FileUpload.user_id.is_(None), FileUpload.expires_at < cutoff),
            and_(FileUpload.user_id.is_not(None), FileUpload.expires_at < owned_cutoff),
        ),
    )
    result = await session.exec(stmt)
    expired_files = result.all()

    cleaned = 0
    upload_dir = Path(settings.UPLOAD_DIR)
    cleaned_ids = {file_upload.id for file_upload in expired_files if file_upload.id is not None}
    stored_filenames_to_delete: set[str] = set()

    for file_upload in expired_files:
        # Mark as inactive
        file_upload.is_active = False
        session.add(file_upload)
        cleaned += 1

        result = await session.exec(
            select(func.count(FileUpload.id)).where(
                FileUpload.stored_filename == file_upload.stored_filename,
                FileUpload.is_active == True,  # noqa: E712
                FileUpload.id.notin_(cleaned_ids),
            )
        )
        if result.one() == 0:
            stored_filenames_to_delete.add(file_upload.stored_filename)

    if cleaned > 0:
        await session.commit()
        for stored_filename in stored_filenames_to_delete:
            file_path = upload_dir / stored_filename
            if file_path.exists():
                file_path.unlink()
                logger.info("Deleted expired file: %s", file_path)
        logger.info("Cleaned up %d expired files", cleaned)

    return cleaned
