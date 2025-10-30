import asyncio
import json
import re
import urllib.error
import urllib.request

PROVIDER = "https://api.exchangerate-api.com"
TIMEOUT = 10


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
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"Unsupported scope type"})
        return

    method = scope.get("method", "GET")
    path = scope.get("path", "/")

    if method != "GET":
        body = b'{"error":"Method Not Allowed"}'
        await send(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"allow", b"GET"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
        return

    code = path.strip("/").upper()
    if not re.fullmatch(r"[A-Z]{3}", code or ""):
        body = b'{"error":"Use /<3-letter-currency>, e.g. /USD"}'
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
        return

    try:
        status, data = await asyncio.to_thread(fetch_upstream_bytes, code)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(data)).encode()),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": data})

    except urllib.error.URLError:
        body = b'{"error":"Bad Gateway: provider unreachable"}'
        await send(
            {
                "type": "http.response.start",
                "status": 502,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


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
