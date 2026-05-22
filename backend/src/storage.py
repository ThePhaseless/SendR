import logging
import uuid
from pathlib import Path

import aioboto3
import aiofiles
from botocore.client import Config
from botocore.exceptions import ClientError

from config import settings

logger = logging.getLogger(__name__)


class StorageManager:
    def __init__(self) -> None:
        self.session = aioboto3.Session()

    @property
    def upload_dir(self) -> Path:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    async def store_file(self, content: bytes, filename: str | None = None) -> str:
        """Stores a file either in S3 or locally depending on config."""
        stored_filename = filename or str(uuid.uuid4())

        if settings.is_s3_configured:
            logger.info("Storing file %s in S3", stored_filename)
            return await self._store_s3(content, stored_filename)

        logger.info("Storing file %s on local disk", stored_filename)
        return await self._store_local(content, stored_filename)

    async def _store_local(self, content: bytes, filename: str) -> str:
        async with aiofiles.open(self.upload_dir / filename, "wb") as f:
            await f.write(content)
        return filename

    async def _store_s3(self, content: bytes, filename: str) -> str:
        async with self.session.client(
            "s3",
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.spaces_endpoint,
            aws_access_key_id=settings.SPACES_ACCESS_KEY,
            aws_secret_access_key=settings.SPACES_SECRET_KEY,
        ) as s3:
            try:
                await s3.put_object(
                    Bucket=settings.SPACES_BUCKET_NAME,
                    Key=filename,
                    Body=content,
                    ACL="private",
                )
                return filename
            except Exception:
                logger.exception("Failed to upload file to S3")
                raise

    async def get_download_url(
        self, filename: str, original_filename: str | None = None
    ) -> str | None:
        """Returns a pre-signed URL for S3 or None if local."""
        if not settings.is_s3_configured:
            return None

        params: dict[str, str] = {
            "Bucket": settings.SPACES_BUCKET_NAME,
            "Key": filename,
        }
        if original_filename:
            from urllib.parse import quote

            params["ResponseContentDisposition"] = (
                f'attachment; filename="{original_filename.replace(chr(34), chr(39))}"'
                f"; filename*=UTF-8''{quote(original_filename)}"
            )

        async with self.session.client(
            "s3",
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.spaces_endpoint,
            aws_access_key_id=settings.SPACES_ACCESS_KEY,
            aws_secret_access_key=settings.SPACES_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        ) as s3:
            try:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params=params,
                    ExpiresIn=3600,
                )
            except Exception:
                logger.exception("Failed to generate pre-signed URL")
                return None

    async def delete_file(self, filename: str) -> None:
        """Deletes file from S3 or local storage."""
        if settings.is_s3_configured:
            async with self.session.client(
                "s3",
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.spaces_endpoint,
                aws_access_key_id=settings.SPACES_ACCESS_KEY,
                aws_secret_access_key=settings.SPACES_SECRET_KEY,
            ) as s3:
                try:
                    await s3.delete_object(
                        Bucket=settings.SPACES_BUCKET_NAME, Key=filename
                    )
                except Exception:
                    logger.exception("Failed to delete file from S3")
        else:
            file_path = self.upload_dir / filename
            if file_path.exists():
                file_path.unlink()

    async def file_exists(self, filename: str) -> bool:
        if settings.is_s3_configured:
            async with self.session.client(
                "s3",
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.spaces_endpoint,
                aws_access_key_id=settings.SPACES_ACCESS_KEY,
                aws_secret_access_key=settings.SPACES_SECRET_KEY,
            ) as s3:
                try:
                    await s3.head_object(
                        Bucket=settings.SPACES_BUCKET_NAME, Key=filename
                    )
                    return True
                except ClientError:
                    return False

        return (self.upload_dir / filename).exists()

    async def download_to_path(self, filename: str, destination: Path) -> None:
        if settings.is_s3_configured:
            async with self.session.client(
                "s3",
                region_name=settings.SPACES_REGION,
                endpoint_url=settings.spaces_endpoint,
                aws_access_key_id=settings.SPACES_ACCESS_KEY,
                aws_secret_access_key=settings.SPACES_SECRET_KEY,
            ) as s3:
                try:
                    await s3.download_file(
                        settings.SPACES_BUCKET_NAME, filename, str(destination)
                    )
                except ClientError as exc:
                    raise FileNotFoundError(filename) from exc
            return

        source = self.upload_dir / filename
        if not source.exists():
            raise FileNotFoundError(filename)

        async with (
            aiofiles.open(source, "rb") as source_file,
            aiofiles.open(destination, "wb") as destination_file,
        ):
            while chunk := await source_file.read(1024 * 1024):
                await destination_file.write(chunk)


storage = StorageManager()
