from datetime import UTC, datetime, timedelta

import pytest
from altcha import ChallengeOptions, Payload, create_challenge, solve_challenge
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app import app
from config import settings
from routers.altcha import verify_altcha_payload
from tests.utils import get_error_message


def _create_altcha_payload(*, expires_at: datetime) -> str:
    challenge = create_challenge(
        ChallengeOptions(
            max_number=500,
            hmac_key=settings.ALTCHA_HMAC_KEY,
            expires=expires_at,
        )
    )
    solution = solve_challenge(challenge)
    assert solution is not None

    return Payload(
        algorithm=challenge.algorithm,
        challenge=challenge.challenge,
        number=solution.number,
        salt=challenge.salt,
        signature=challenge.signature,
    ).to_base64()


def test_verify_altcha_payload_rejects_invalid_payload():
    with pytest.raises(HTTPException, match="Invalid Altcha payload"):
        verify_altcha_payload("")


def test_verify_altcha_payload_allows_recently_expired_payload_within_upload_grace():
    payload = _create_altcha_payload(
        expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    verify_altcha_payload(payload)


@pytest.mark.asyncio
async def test_upload_accepts_recently_expired_altcha_while_within_grace(auth_headers):
    payload = _create_altcha_payload(
        expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            headers=auth_headers,
            data={"altcha": payload},
            files=[("file", ("grace.txt", b"hello", "text/plain"))],
        )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_upload_rejects_altcha_past_upload_grace(auth_headers):
    payload = _create_altcha_payload(
        expires_at=datetime.now(UTC)
        - timedelta(minutes=settings.ALTCHA_UPLOAD_GRACE_MINUTES + 1)
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/files/upload",
            headers=auth_headers,
            data={"altcha": payload},
            files=[("file", ("expired.txt", b"hello", "text/plain"))],
        )

    assert response.status_code == 400
    assert (
        get_error_message(response)
        == "Altcha verification failed: Altcha payload expired"
    )
