from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from httpx import Response


def get_error_message(response: Response) -> str:
    payload = cast("object", response.json())
    if not isinstance(payload, Mapping):
        return str(payload)

    typed_payload = cast("Mapping[str, object]", payload)
    detail = typed_payload.get("detail")
    if isinstance(detail, Mapping):
        typed_detail = cast("Mapping[str, object]", detail)
        message = typed_detail.get("message")
        if isinstance(message, str):
            return message
    if isinstance(detail, str):
        return detail
    return str(cast("object", detail))
