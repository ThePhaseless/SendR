import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger("uvicorn.error")


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
    if settings.is_local:
        logger.info("=" * 50)
        logger.info("VERIFICATION CODE for %s: %s", email, code)
        logger.info("=" * 50)
        return

    await asyncio.to_thread(_send_verification_email_sync, email, code)


def _build_invite_message(
    recipient_email: str,
    sender_email: str,
    download_url: str,
    file_names: list[str],
    message: str | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient_email
    msg["Subject"] = f"{sender_email} shared files with you on SendR"

    file_list = "\n".join(f"  - {name}" for name in file_names)
    body = (
        f"{sender_email} has shared files with you:\n\n"
        f"{file_list}\n\n"
        f"Download here:\n{download_url}\n"
    )
    if message:
        body += f"\nMessage from sender:\n{message}\n"

    msg.set_content(body)
    return msg


def _send_invite_email_sync(
    recipient_email: str,
    sender_email: str,
    download_url: str,
    file_names: list[str],
    message: str | None = None,
) -> None:
    msg = _build_invite_message(recipient_email, sender_email, download_url, file_names, message)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_file_invite_email(
    recipient_email: str,
    sender_email: str,
    download_url: str,
    file_names: list[str],
    message: str | None = None,
) -> None:
    """Send file share invitation email, or log in dev mode."""
    if settings.is_local:
        logger.info("=" * 50)
        logger.info("FILE INVITE for %s from %s: %s", recipient_email, sender_email, download_url)
        logger.info("=" * 50)
        return

    await asyncio.to_thread(
        _send_invite_email_sync, recipient_email, sender_email, download_url, file_names, message
    )
