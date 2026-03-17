import logging

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, code: str) -> None:
    """Send verification email. In development, logs the code to console."""
    logger.info("=" * 50)
    logger.info("VERIFICATION CODE for %s: %s", email, code)
    logger.info("=" * 50)
