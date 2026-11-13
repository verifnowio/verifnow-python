from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from verifnow import HttpRequest, HttpResponse, RetryPolicy, TransportError, VerifNow

Reply = HttpResponse | TransportError


class FakeTransport:
    """Replays queued responses and records every request. Nothing touches the network."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []
        self._replies: list[Reply] = []

    def reply(
        self,
        status: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
        raw: bytes | None = None,
    ) -> FakeTransport:
        payload = raw if raw is not None else json.dumps(body if body is not None else {}).encode()
        self._replies.append(
            HttpResponse(
                status=status,
                body=payload,
                headers={k.lower(): v for k, v in (headers or {}).items()},
            )
        )
        return self

    def fail(self, message: str = "connection refused", timed_out: bool = False) -> FakeTransport:
        self._replies.append(TransportError(message, timed_out=timed_out))
        return self

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if not self._replies:
            raise AssertionError(f"unexpected request: {request.method} {request.url}")
        reply = self._replies.pop(0)
        if isinstance(reply, TransportError):
            raise reply
        return reply

    @property
    def last(self) -> HttpRequest:
        return self.requests[-1]

    def last_json(self) -> Any:
        assert self.last.body is not None
        return json.loads(self.last.body)


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_client(transport: FakeTransport, sleeps: list[float]) -> Iterator[Callable[..., VerifNow]]:
    def factory(**kwargs: Any) -> VerifNow:
        kwargs.setdefault("api_key", "vn_test_key")
        kwargs.setdefault("retry", RetryPolicy())
        client = VerifNow(transport=transport, **kwargs)
        client._sleep = sleeps.append  # retries record their delay instead of sleeping
        return client

    yield factory


@pytest.fixture
def client(make_client: Callable[..., VerifNow]) -> VerifNow:
    return make_client()
