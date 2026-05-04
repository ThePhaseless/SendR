import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from config import settings


class RateLimiter:
    """Simple in-memory rate limiter based on client IP."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._cleanup(key, now)
            if len(self._requests[key]) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )
            self._requests[key].append(now)

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


auth_rate_limiter = RateLimiter(
    max_requests=settings.AUTH_RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxy headers."""
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and client_ip in settings.TRUSTED_PROXY_IPS:
        forwarded_ip = forwarded.split(",")[0].strip()
        if forwarded_ip:
            return forwarded_ip
    return client_ip
