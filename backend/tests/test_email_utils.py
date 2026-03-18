import logging
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from config import settings
from email_utils import send_verification_email


@pytest.mark.asyncio
async def test_send_verification_email_logs_code_in_local_env(caplog: pytest.LogCaptureFixture):
    original_dev_mode = settings.DEV_MODE
    settings.DEV_MODE = True

    try:
        with caplog.at_level(logging.INFO):
            await send_verification_email("user@example.com", "123456")
    finally:
        settings.DEV_MODE = original_dev_mode

    assert "VERIFICATION CODE for user@example.com: 123456" in caplog.text


@pytest.mark.asyncio
async def test_send_verification_email_uses_smtp_outside_local_env():
    original_dev_mode = settings.DEV_MODE
    settings.DEV_MODE = False

    smtp_instance = MagicMock()

    try:
        with patch("email_utils.smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__.return_value = smtp_instance

            await send_verification_email("user@example.com", "123456")
    finally:
        settings.DEV_MODE = original_dev_mode

    smtp_cls.assert_called_once_with(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30)
    smtp_instance.send_message.assert_called_once()
    message = smtp_instance.send_message.call_args.args[0]
    assert isinstance(message, EmailMessage)
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Your SendR verification code"
    assert "123456" in message.get_content()
