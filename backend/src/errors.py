import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.exceptions import HTTPException as StarletteHTTPException


_ERROR_CODE_MAP = {
    "Account is banned": "ACCOUNT_BANNED",
    "Access token required": "ACCESS_TOKEN_REQUIRED",
    "Admin access required": "ADMIN_ACCESS_REQUIRED",
    "Current password is incorrect": "CURRENT_PASSWORD_INCORRECT",
    "File not found": "FILE_NOT_FOUND",
    "File not found on disk": "FILE_NOT_FOUND_ON_DISK",
    "Invalid access token": "INVALID_ACCESS_TOKEN",
    "Invalid email or password": "INVALID_CREDENTIALS",
    "Invalid or expired token": "SESSION_EXPIRED",
    "Invalid password": "INVALID_PASSWORD",
    "Not authenticated": "NOT_AUTHENTICATED",
    "Password already set": "PASSWORD_ALREADY_SET",
    "Too many requests. Please try again later.": "RATE_LIMITED",
    "Upload group not found": "UPLOAD_GROUP_NOT_FOUND",
    "User not found": "USER_NOT_FOUND",
}


def _derive_error_code(message: str) -> str:
    mapped = _ERROR_CODE_MAP.get(message)
    if mapped:
        return mapped

    normalized = re.sub(r"[^A-Z0-9]+", "_", message.upper()).strip("_")
    return normalized or "HTTP_ERROR"


def normalize_http_exception_detail(detail: object) -> dict[str, str]:
    if isinstance(detail, Mapping):
        detail_mapping = cast("Mapping[str, object]", detail)
        code = detail_mapping.get("code")
        message = detail_mapping.get("message")
        if isinstance(code, str) and isinstance(message, str):
            return {"code": code, "message": message}

    if isinstance(detail, str):
        return {"code": _derive_error_code(detail), "message": detail}

    return {"code": "HTTP_ERROR", "message": "Request failed."}


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": normalize_http_exception_detail(exc.detail)},
        headers=exc.headers,
    )
