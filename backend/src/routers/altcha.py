import base64
import binascii
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

from altcha import ChallengeOptions, create_challenge, verify_solution
from fastapi import APIRouter, Form, HTTPException, status

from config import settings

router = APIRouter(prefix="/api/altcha", tags=["altcha"])


@router.get("/challenge")
async def get_challenge() -> dict:
    """Generate a new Altcha proof-of-work challenge."""
    options = ChallengeOptions(
        max_number=settings.ALTCHA_MAX_NUMBER,
        hmac_key=settings.ALTCHA_HMAC_KEY,
        expires=datetime.now(UTC) + timedelta(minutes=settings.ALTCHA_EXPIRE_MINUTES),
    )
    challenge = create_challenge(options)
    return challenge.to_dict()


def _decode_altcha_payload(payload: str) -> dict[str, object]:
    try:
        payload_data = json.loads(base64.b64decode(payload, validate=True).decode())
    except binascii.Error, json.JSONDecodeError, UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Altcha payload.",
        ) from None

    if not isinstance(payload_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Altcha payload.",
        )

    return payload_data


def _ensure_altcha_within_upload_grace(payload_data: dict[str, object]) -> None:
    salt = payload_data.get("salt")
    if not isinstance(salt, str):
        return

    query = salt.partition("?")[2]
    if not query:
        return

    expires = parse_qs(query).get("expires")
    if not expires:
        return

    try:
        expires_at = int(expires[0])
    except TypeError, ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Altcha verification failed: Altcha payload expired",
        ) from None

    grace_seconds = settings.ALTCHA_UPLOAD_GRACE_MINUTES * 60
    if expires_at + grace_seconds < time.time():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Altcha verification failed: Altcha payload expired",
        )


def verify_altcha_payload(payload: str = Form("", alias="altcha")) -> None:
    """FastAPI dependency that verifies an Altcha solution from form data."""
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Altcha payload.",
        )

    payload_data = _decode_altcha_payload(payload)

    ok, err = verify_solution(
        payload_data, settings.ALTCHA_HMAC_KEY, check_expires=False
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Altcha verification failed: {err or 'invalid solution'}",
        )

    _ensure_altcha_within_upload_grace(payload_data)
