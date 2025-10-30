import json
import re
import urllib.error
import urllib.request

PROVIDER = "https://api.exchangerate-api.com"
TIMEOUT = 10


def simple_app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method != "GET":
        body = b'{"error":"Method Not Allowed"}'
        start_response(
            "405 Method Not Allowed",
            [
                ("Content-Type", "application/json"),
                ("Allow", "GET"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    code = path.strip("/").upper()
    if not re.fullmatch(r"[A-Z]{3}", code or ""):
        body = b'{"error":"Use /<3-letter-currency>, e.g. /USD"}'
        start_response(
            "400 Bad Request",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    url = f"{PROVIDER}/v4/latest/{code}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
            status_code = resp.getcode()
            reason = (
                getattr(resp, "reason", "") or "OK"
                if status_code == 200
                else (getattr(resp, "reason", "") or "")
            )
            start_response(
                f"{status_code} {reason}".strip(),
                [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(data))),
                    ("Cache-Control", "no-store"),
                ],
            )
            return [data]

    except urllib.error.HTTPError as e:
        err_body = e.read() or json.dumps({"error": f"Upstream HTTP {e.code}"}).encode()
        reason = (e.reason if isinstance(e.reason, str) else "") or ""
        start_response(
            f"{e.code} {reason}".strip() or str(e.code),
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(err_body))),
            ],
        )
        return [err_body]

    except urllib.error.URLError:
        body = b'{"error":"Bad Gateway: provider unreachable"}'
        start_response(
            "502 Bad Gateway",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]


def run_wsgi_app(app, environ):
    status_line = ""
    headers = []

    def start_response(status, response_headers):
        nonlocal status_line, headers
        status_line = status
        headers = response_headers

    response_body = app(environ, start_response)

    response = [f"HTTP/1.1 {status_line}".encode()]
    for header in headers:
        response.append(f"{header[0]}: {header[1]}".encode())
    response.append(b"")
    response.extend(response_body)

    return response


environ = {
    "REQUEST_METHOD": "GET",
    "PATH_INFO": "/USD",
    "SERVER_NAME": "localhost",
    "SERVER_PORT": "8000",
}

if __name__ == "__main__":
    resp = run_wsgi_app(simple_app, environ)
    print(b"\r\n".join(resp).decode())
