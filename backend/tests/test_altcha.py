import pytest
from fastapi import HTTPException

from config import settings
from routers.altcha import verify_altcha_payload


def test_verify_altcha_payload_is_noop_in_local_environment():
    original_dev_mode = settings.DEV_MODE
    original_environment = settings.ENVIRONMENT
    settings.DEV_MODE = False
    settings.ENVIRONMENT = "local"

    try:
        verify_altcha_payload("")
    finally:
        settings.DEV_MODE = original_dev_mode
        settings.ENVIRONMENT = original_environment


def test_verify_altcha_payload_rejects_invalid_payload_outside_local_environment():
    original_dev_mode = settings.DEV_MODE
    original_environment = settings.ENVIRONMENT
    settings.DEV_MODE = False
    settings.ENVIRONMENT = "production"

    try:
        with pytest.raises(HTTPException, match="Invalid Altcha payload"):
            verify_altcha_payload("")
    finally:
        settings.DEV_MODE = original_dev_mode
        settings.ENVIRONMENT = original_environment
