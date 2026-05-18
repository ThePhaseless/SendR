import asyncio
import logging
import smtplib
from email.message import EmailMessage

import resend

from config import settings

logger = logging.getLogger("uvicorn.error")

if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY


def _should_log_email_delivery() -> bool:
    return settings.is_local or (
        settings.ENVIRONMENT == "test"
        and not settings.smtp_configured
        and not settings.RESEND_API_KEY
    )


def _log_missing_smtp_configuration(email_kind: str) -> None:
    logger.warning(
        "SMTP host is not configured in %s mode; logging %s instead.",
        settings.ENVIRONMENT,
        email_kind,
    )


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


def _send_email_via_resend(to: str, subject: str, body: str) -> bool:
    """Send email using Resend API. Returns True if successful."""
    if not settings.RESEND_API_KEY:
        return False
    try:
        resend.Emails.send(
            {
                "from": settings.SMTP_FROM,
                "to": to,
                "subject": subject,
                "text": body,
            }
        )
        logger.info("Email sent via Resend API to %s", to)
        return True
    except Exception as e:
        logger.error("Failed to send email via Resend API: %s", e)
        return False


def _send_verification_email_sync(email: str, code: str) -> None:
    subject = "Your SendR verification code"
    body = (
        "Use this verification code to sign in to SendR:\n\n"
        f"{code}\n\n"
        f"This code expires in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes."
    )

    # Try Resend API first
    if _send_email_via_resend(email, subject, body):
        return

    message = _build_verification_message(email, code)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)
        logger.info("Email sent via SMTP to %s", email)


async def send_verification_email(email: str, code: str) -> None:
    """Send verification email, or log the code when SMTP is unavailable."""
    if _should_log_email_delivery():
        if not settings.is_local:
            _log_missing_smtp_configuration("verification codes")
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
    subject = f"{sender_email} shared files with you on SendR"
    file_list = "\n".join(f"  - {name}" for name in file_names)
    body = (
        f"{sender_email} has shared files with you:\n\n"
        f"{file_list}\n\n"
        f"Download here:\n{download_url}\n"
    )
    if message:
        body += f"\nMessage from sender:\n{message}\n"

    # Try Resend API first
    if _send_email_via_resend(recipient_email, subject, body):
        return

    msg = _build_invite_message(
        recipient_email, sender_email, download_url, file_names, message
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)
        logger.info("Email sent via SMTP to %s", recipient_email)


async def send_file_invite_email(
    recipient_email: str,
    sender_email: str,
    download_url: str,
    file_names: list[str],
    message: str | None = None,
) -> None:
    """Send file share invitation email, or log it when SMTP is unavailable."""
    if _should_log_email_delivery():
        if not settings.is_local:
            _log_missing_smtp_configuration("file invites")
        logger.info("=" * 50)
        logger.info(
            "FILE INVITE for %s from %s: %s",
            recipient_email,
            sender_email,
            download_url,
        )
        logger.info("=" * 50)
        return

    await asyncio.to_thread(
        _send_invite_email_sync,
        recipient_email,
        sender_email,
        download_url,
        file_names,
        message,
    )


def _build_malware_detected_message(
    recipient_email: str,
    file_names: list[str],
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient_email
    msg["Subject"] = "SendR blocked an uploaded file"

    file_list = "\n".join(f"  - {name}" for name in file_names)
    msg.set_content(
        "SendR blocked one of your uploads because malware was detected.\n\n"
        f"Blocked file(s):\n{file_list}\n\n"
        "The infected payload was removed immediately and the download link now "
        "shows a blocked state to recipients."
    )
    return msg


def _send_malware_detected_email_sync(
    recipient_email: str,
    file_names: list[str],
) -> None:
    msg = _build_malware_detected_message(recipient_email, file_names)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USER or settings.SMTP_PASSWORD:
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_malware_detected_email(
    recipient_email: str,
    file_names: list[str],
) -> None:
    """Send a malware-detected email, or log it when SMTP is unavailable."""
    if _should_log_email_delivery():
        if not settings.is_local:
            _log_missing_smtp_configuration("malware notifications")
        logger.info("=" * 50)
        logger.info(
            "MALWARE BLOCKED for %s: %s",
            recipient_email,
            ", ".join(file_names),
        )
        logger.info("=" * 50)
        return

    await asyncio.to_thread(
        _send_malware_detected_email_sync,
        recipient_email,
        file_names,
    )
