import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger(__name__)


def _build_verification_message(email: str, code: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = email
    message["Subject"] = "Your SendR verification code"
    message.set_content(
        "Use this verification code to sign in to SendR:\n\n"
        f"{code}\n\n"
        f"This code expires in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes."
    )
    return message


def _send_verification_email_sync(email: str, code: str) -> None:
    message = _build_verification_message(email, code)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def send_verification_email(email: str, code: str) -> None:
    """Send verification email, or log the code in dev mode."""
    if settings.DEV_MODE:
        logger.info("=" * 50)
        logger.info("VERIFICATION CODE for %s: %s", email, code)
        logger.info("=" * 50)
        return

    await asyncio.to_thread(_send_verification_email_sync, email, code)
