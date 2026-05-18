from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import clamd
from fastapi import HTTPException, status

from config import settings
from models import ScanStatus

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _get_client() -> clamd.ClamdNetworkSocket | clamd.ClamdUnixSocket:
    if settings.CLAMAV_UNIX_SOCKET:
        return clamd.ClamdUnixSocket(path=settings.CLAMAV_UNIX_SOCKET)
    return clamd.ClamdNetworkSocket(
        host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT
    )


def scan_upload_result(target: bytes | str | Path) -> tuple[ScanStatus, str | None]:
    """Scan upload bytes or a file path and return the malware verdict."""
    if not settings.VIRUS_SCANNING_ENABLED:
        return ScanStatus.clean, None

    try:
        client = _get_client()
        if isinstance(target, bytes):
            response = client.instream(io.BytesIO(target))
        else:
            response = client.scan(str(target))
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
        return ScanStatus.infected, signature

    if scan_status != "OK":
        logger.warning("Unexpected ClamAV response: %s", response)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Virus scanner unavailable. Try again later.",
        )

    return ScanStatus.clean, None


def scan_upload_content(target: bytes | str | Path) -> None:
    """Scan upload bytes or a file path with ClamAV when scanning is enabled."""
    scan_status, signature = scan_upload_result(target)
    if scan_status == ScanStatus.infected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload blocked: malware detected ({signature}).",
        )
