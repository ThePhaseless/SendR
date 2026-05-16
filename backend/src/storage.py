import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
import aioboto3
from botocore.client import Config
from fastapi import HTTPException
from config import settings

logger = logging.getLogger(__name__)

class StorageManager:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # S3 session setup
        self.session = aioboto3.Session()

    async def store_file(self, content: bytes, filename: Optional[str] = None) -> str:
        """Stores a file either in S3 or locally depending on config."""
        stored_filename = filename or str(uuid.uuid4())
        
        if settings.is_s3_configured:
            logger.info(f"STORAGE: Storing file {stored_filename} in S3 (Bucket: {settings.SPACES_BUCKET_NAME})")
            return await self._store_s3(content, stored_filename)
        else:
            logger.info(f"STORAGE: S3 not configured. Storing file {stored_filename} on LOCAL DISK.")
            return await self._store_local(content, stored_filename)

    async def _store_local(self, content: bytes, filename: str) -> str:
        async with aiofiles.open(self.upload_dir / filename, "wb") as f:
            await f.write(content)
        return filename

    async def _store_s3(self, content: bytes, filename: str) -> str:
        async with self.session.client(
            's3',
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.SPACES_ENDPOINT,
            aws_access_key_id=settings.SPACES_ACCESS_KEY,
            aws_secret_access_key=settings.SPACES_SECRET_KEY,
        ) as s3:
            try:
                await s3.put_object(
                    Bucket=settings.SPACES_BUCKET_NAME,
                    Key=filename,
                    Body=content,
                    ACL='private'
                )
                return filename
            except Exception as e:
                logger.error(f"Failed to upload to S3: {e}")
                raise HTTPException(status_code=500, detail="Cloud storage upload failed")

    async def get_download_url(self, filename: str) -> Optional[str]:
        """Returns a pre-signed URL for S3 or None if local."""
        if not settings.is_s3_configured:
            return None

        async with self.session.client(
            's3',
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.SPACES_ENDPOINT,
            aws_access_key_id=settings.SPACES_ACCESS_KEY,
            aws_secret_access_key=settings.SPACES_SECRET_KEY,
            config=Config(signature_version='s3v4')
        ) as s3:
            try:
                url = await s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': settings.SPACES_BUCKET_NAME, 'Key': filename},
                    ExpiresIn=3600  # 1 hour
                )
                return url
            except Exception as e:
                logger.error(f"Failed to generate pre-signed URL: {e}")
                return None

    async def delete_file(self, filename: str):
        """Deletes file from S3 or local storage."""
        if settings.is_s3_configured:
            async with self.session.client(
                's3',
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.SPACES_ENDPOINT,
                aws_access_key_id=settings.SPACES_ACCESS_KEY,
                aws_secret_access_key=settings.SPACES_SECRET_KEY,
            ) as s3:
                try:
                    await s3.delete_object(Bucket=settings.SPACES_BUCKET_NAME, Key=filename)
                except Exception as e:
                    logger.error(f"Failed to delete from S3: {e}")
        else:
            file_path = self.upload_dir / filename
            if file_path.exists():
                file_path.unlink()

    async def file_exists(self, filename: str) -> bool:
        if settings.is_s3_configured:
            async with self.session.client(
                's3',
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.SPACES_ENDPOINT,
                aws_access_key_id=settings.SPACES_ACCESS_KEY,
                aws_secret_access_key=settings.SPACES_SECRET_KEY,
            ) as s3:
                try:
                    await s3.head_object(Bucket=settings.SPACES_BUCKET_NAME, Key=filename)
                    return True
                except Exception:
                    return False
        else:
            return (self.upload_dir / filename).exists()

storage = StorageManager()
