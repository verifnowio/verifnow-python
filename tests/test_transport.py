"""The default urllib transport, against a local HTTP server. Loopback only, no internet."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from verifnow import (
    HttpRequest,
    TransportError,
    VerifNow,
    VerifNowAuthError,
    VerifNowConnectionError,
    __version__,
)
from verifnow._transport import urllib_transport

received: list[dict[str, object]] = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        # Keep the Message itself: header names are case-insensitive, and urllib re-cases them.
        received.append(
            {"path": self.path, "headers": self.headers, "body": self.rfile.read(length)}
        )
        if self.path.endswith("/slow"):
            time.sleep(1)
        if self.headers.get("X-API-KEY") != "vn_good":
            self._send(401, {"status": 401, "message": "Invalid API key"})
            return
        self._send(
            200,
            {"valid": True, "normalizedValue": "user@example.com"},
            {"X-RateLimit-Remaining": "41"},
        )

    def _send(self, status: int, body: object, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Request-Id", "req-123")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_given_a_real_http_exchange_then_request_and_response_round_trip(server: str) -> None:
    received.clear()
    client = VerifNow("vn_good", base_url=server)

    result = client.validate_email("user@example.com")

    assert result.valid is True
    assert result.quota is not None and result.quota.remaining == 41
    sent = received[-1]
    assert sent["path"] == "/api/v1/validate/email"
    assert json.loads(sent["body"]) == {"value": "user@example.com"}  # type: ignore[arg-type]
    headers = sent["headers"]
    assert isinstance(headers, Message)
    assert headers["X-VerifNow-SDK"] == f"python/{__version__}"
    assert headers["Content-Type"] == "application/json"


def test_given_an_error_status_then_urllib_does_not_raise_and_the_client_maps_it(
    server: str,
) -> None:
    response = urllib_transport(
        HttpRequest("POST", f"{server}/api/v1/validate/email", {"X-API-KEY": "bad"}, b"{}", 5)
    )
    assert response.status == 401
    assert response.header("x-request-id") == "req-123"

    with pytest.raises(VerifNowAuthError) as caught:
        VerifNow("vn_bad", base_url=server).validate_email("a@b.co")
    assert caught.value.request_id == "req-123"


def test_given_a_slow_server_then_the_timeout_is_reported(server: str) -> None:
    with pytest.raises(TransportError) as caught:
        urllib_transport(
            HttpRequest("POST", f"{server}/slow", {"X-API-KEY": "vn_good"}, b"{}", 0.2)
        )
    assert caught.value.timed_out is True


def test_given_nothing_listening_then_connection_error() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    client = VerifNow("vn_good", base_url=f"http://127.0.0.1:{port}", retry=None)
    with pytest.raises(VerifNowConnectionError) as caught:
        client.validate_email("a@b.co")
    assert f"127.0.0.1:{port}" in str(caught.value)
    assert caught.value.timed_out is False
