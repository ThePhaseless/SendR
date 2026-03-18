import json
from datetime import UTC, datetime, timedelta

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


def verify_altcha_payload(payload: str = Form("", alias="altcha")) -> None:
    """FastAPI dependency that verifies an Altcha solution from form data."""
    if settings.DEV_MODE:
        return

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Altcha payload.",
        ) from exc

    ok, err = verify_solution(data, settings.ALTCHA_HMAC_KEY, check_expires=True)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Altcha verification failed: {err or 'invalid solution'}",
        )
