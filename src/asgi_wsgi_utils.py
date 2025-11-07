import json


def make_error_message_body(message: str) -> bytes:
    return json.dumps({"error": f"{message}"}, ensure_ascii=False).encode()
