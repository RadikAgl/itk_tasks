import asyncio
import json
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

from src.asgi_wsgi_constants import ERROR_MESSAGES, PROVIDER, TIMEOUT
from src.asgi_wsgi_utils import make_error_message_body
from src.asgi_wsgi_validators import validate_currency_code


async def send_json_response(
    send,
    status: int,
    body: bytes,
    headers_in: Optional[List[Tuple]] = None,
    extra_headers: Optional[List[Tuple]] = None,
):
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]

    if extra_headers:
        headers.extend(extra_headers)

    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": headers_in if headers_in else headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


def fetch_upstream_bytes(code: str) -> tuple[int, bytes]:
    url = f"{PROVIDER}/v4/latest/{code}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        body = e.read() or json.dumps({"error": f"Upstream HTTP {e.code}"}).encode()
        return e.code, body


async def asgi_app(scope, receive, send):
    if scope.get("type") != "http":
        body = make_error_message_body(ERROR_MESSAGES["unsupported_scope_type"])
        await send_json_response(
            send=send,
            status=500,
            body=body,
            headers_in=[(b"content-type", b"text/plain")],
        )
        return

    method = scope.get("method", "GET")
    path = scope.get("path", "/")

    if method != "GET":
        body = make_error_message_body(ERROR_MESSAGES["method_not_allowed"])
        extra_headers = [(b"allow", b"GET")]
        await send_json_response(
            send=send, status=405, body=body, extra_headers=extra_headers
        )
        return

    code = path.strip("/").upper()
    if not validate_currency_code(code):
        body = make_error_message_body(ERROR_MESSAGES["invalid_path"])
        await send_json_response(send=send, status=400, body=body)
        return

    try:
        status, data = await asyncio.to_thread(fetch_upstream_bytes, code)
        extra_headers = [
            (b"cache-control", b"no-store"),
        ]

        await send_json_response(
            send=send, status=status, body=data, extra_headers=extra_headers
        )

    except urllib.error.URLError:
        body = make_error_message_body(ERROR_MESSAGES["bad_gateway"])
        await send_json_response(send=send, status=502, body=body)


async def run_asgi_app(app, method="GET", path="/USD"):
    status = None
    headers = []
    body_chunks = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal status, headers, body_chunks
        if message["type"] == "http.response.start":
            status = message["status"]
            headers = message.get("headers", [])
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("localhost", 8000),
        "client": ("127.0.0.1", 12345),
    }

    await app(scope, receive, send)

    body = b"".join(body_chunks)
    response_lines = [f"HTTP/1.1 {status}".encode()]
    for k, v in headers:
        response_lines.append(k + b": " + v)
    response_lines.append(b"")
    response_lines.append(body)
    return response_lines


if __name__ == "__main__":
    resp = asyncio.run(run_asgi_app(asgi_app, path="/USD"))
    print(b"\r\n".join(resp).decode())
