import io
import logging

import clamd
from fastapi import HTTPException, status

from config import settings

logger = logging.getLogger(__name__)


def _get_client() -> clamd.ClamdNetworkSocket | clamd.ClamdUnixSocket:
    if settings.CLAMAV_UNIX_SOCKET:
        return clamd.ClamdUnixSocket(path=settings.CLAMAV_UNIX_SOCKET)
    return clamd.ClamdNetworkSocket(
        host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT
    )


def scan_upload_content(content: bytes) -> None:
    """Scan upload bytes with ClamAV when scanning is enabled."""
    if not settings.VIRUS_SCANNING_ENABLED:
        return

    try:
        response = _get_client().instream(io.BytesIO(content))
    except clamd.BufferTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the configured virus scanner stream limit.",
        ) from exc
    except clamd.ClamdError as exc:
        logger.warning("Virus scanner unavailable", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Virus scanner unavailable. Try again later.",
        ) from exc

    if not response:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Virus scanner unavailable. Try again later.",
        )

    scan_status, signature = next(iter(response.values()))
    if scan_status == "FOUND":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload blocked: malware detected ({signature}).",
        )

    if scan_status != "OK":
        logger.warning("Unexpected ClamAV response: %s", response)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Virus scanner unavailable. Try again later.",
        )
