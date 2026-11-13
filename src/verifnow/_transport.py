"""HTTP transport, built on the standard library so the package has no runtime dependency.

The client talks to a ``Transport``: a callable taking an ``HttpRequest`` and returning an
``HttpResponse``. The default one uses ``urllib``. Tests, or an application that wants its own
connection pooling or proxy handling, pass another.

A transport returns every HTTP response, error statuses included, and raises ``TransportError``
only when no response arrived at all.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None
    timeout: float


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)
    """Header names in lower case."""

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())


class TransportError(Exception):
    """No HTTP response: DNS, TLS, refused connection, or timeout."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


Transport = Callable[[HttpRequest], HttpResponse]


def _lower(headers: Mapping[str, str] | None) -> dict[str, str]:
    return {} if headers is None else {k.lower(): v for k, v in headers.items()}


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Default transport. One connection per request, certificate checks on."""
    # The client only builds http(s) URLs: it rejects any other base_url scheme.
    req = urllib.request.Request(  # noqa: S310
        request.url,
        data=request.body,
        headers=dict(request.headers),
        method=request.method,
    )
    try:
        with urllib.request.urlopen(req, timeout=request.timeout) as response:  # noqa: S310 - see above
            return HttpResponse(
                status=response.status,
                body=response.read(),
                headers=_lower(dict(response.headers.items())),
            )
    except urllib.error.HTTPError as error:
        # urllib raises on 4xx/5xx; to the client they are ordinary responses.
        try:
            body = error.read()
        except OSError:
            body = b""
        return HttpResponse(
            status=error.code,
            body=body,
            headers=_lower(dict(error.headers.items()) if error.headers else None),
        )
    except urllib.error.URLError as error:
        reason = error.reason
        timed_out = isinstance(reason, (socket.timeout, TimeoutError))
        raise TransportError(str(reason), timed_out=timed_out) from error
    except TimeoutError as error:
        # A timeout while reading the body comes through bare, not wrapped in URLError.
        raise TransportError("timed out", timed_out=True) from error
    except (ssl.SSLError, ConnectionError, OSError) as error:
        raise TransportError(str(error)) from error
