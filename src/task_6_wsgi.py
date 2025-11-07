import json
import urllib.error
import urllib.request

from src.asgi_wsgi_constants import ERROR_MESSAGES, PROVIDER, TIMEOUT
from src.asgi_wsgi_utils import make_error_message_body
from src.asgi_wsgi_validators import validate_currency_code


def get_response_headers(data, extra_headers=None):
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(data))),
    ]

    if extra_headers:
        headers.append(extra_headers)

    return headers


def simple_app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    if method != "GET":
        body = make_error_message_body(ERROR_MESSAGES["method_not_allowed"])
        response_headers = get_response_headers(body, ("Allow", "GET"))
        start_response(
            "405 Method Not Allowed",
            response_headers,
        )
        return [body]

    code = path.strip("/").upper()
    if not validate_currency_code(code):
        body = make_error_message_body(ERROR_MESSAGES["invalid_path"])
        response_headers = get_response_headers(body)
        start_response(
            "400 Bad Request",
            response_headers,
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
            response_headers = get_response_headers(data, ("Cache-Control", "no-store"))
            start_response(
                f"{status_code} {reason}".strip(),
                response_headers,
            )
            return [data]

    except urllib.error.HTTPError as e:
        err_body = e.read() or json.dumps({"error": f"Upstream HTTP {e.code}"}).encode()
        reason = (e.reason if isinstance(e.reason, str) else "") or ""
        response_headers = get_response_headers(err_body)
        start_response(
            f"{e.code} {reason}".strip() or str(e.code),
            response_headers,
        )
        return [err_body]

    except urllib.error.URLError:
        body = make_error_message_body(ERROR_MESSAGES["bad_gateway"])
        response_headers = get_response_headers(body)

        start_response(
            "502 Bad Gateway",
            response_headers,
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
