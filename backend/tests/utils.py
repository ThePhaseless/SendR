def get_error_message(response) -> str:
    detail = response.json()["detail"]
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str):
            return message
    return detail
