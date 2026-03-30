import pytest
from fastapi import HTTPException

from routers.altcha import verify_altcha_payload


def test_verify_altcha_payload_rejects_invalid_payload():
    with pytest.raises(HTTPException, match="Invalid Altcha payload"):
        verify_altcha_payload("")
