from __future__ import annotations

import asyncio
import threading

import pytest
from conftest import FakeTransport

from verifnow import AsyncVerifNow, HttpRequest, HttpResponse, VerifNowAuthError


def test_given_the_async_client_then_calls_run_off_the_event_loop_thread() -> None:
    threads: list[int] = []
    transport = FakeTransport()
    transport.reply(body={"valid": True, "normalizedValue": "IE6388047V"})

    def recording(request: HttpRequest) -> HttpResponse:
        threads.append(threading.get_ident())
        return transport(request)

    async def main() -> tuple[bool, int]:
        client = AsyncVerifNow("vn_test_key", transport=recording)
        result = await client.validate_vat("IE6388047V", trader_name="Google")
        return result.valid, threading.get_ident()

    valid, loop_thread = asyncio.run(main())

    assert valid is True
    assert threads and threads[0] != loop_thread
    assert transport.last_json() == {"value": "IE6388047V", "traderName": "Google"}


def test_given_an_error_then_the_async_client_raises_the_same_type() -> None:
    transport = FakeTransport().reply(401, {"message": "Invalid API key"})

    async def main() -> None:
        await AsyncVerifNow("vn_test_key", transport=transport).validate_email("a@b.co")

    with pytest.raises(VerifNowAuthError):
        asyncio.run(main())


def test_given_the_async_client_then_it_exposes_every_sync_method() -> None:
    from verifnow import VerifNow

    public = {name for name in dir(VerifNow) if not name.startswith("_")}
    assert public <= set(dir(AsyncVerifNow))


def test_given_the_async_client_when_printed_then_the_key_does_not_appear() -> None:
    assert "vn_secret" not in repr(AsyncVerifNow("vn_secret"))
