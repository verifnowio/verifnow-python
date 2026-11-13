"""The asyncio client.

It runs the synchronous client in a worker thread (``asyncio.to_thread``) rather than shipping its
own async HTTP stack: that keeps the package free of runtime dependencies, and a validation call
spends its time waiting on the network, which a thread does as well as a coroutine. Retries and
backoff happen in the worker thread, so they never block the event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from ._client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, RetryPolicy, VerifNow
from ._models import CountryVatRates, ValidationResult, ValidationRule, VatRates
from ._transport import Transport


class AsyncVerifNow:
    """Asyncio client for the VerifNow validation API. Same methods as ``VerifNow``, awaitable.

    >>> client = AsyncVerifNow()  # reads VERIFNOW_API_KEY
    >>> result = await client.validate_vat("IE6388047V")
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retry: RetryPolicy | None = RetryPolicy(),  # noqa: B008 - frozen, safe to share
        headers: Mapping[str, str] | None = None,
        transport: Transport | None = None,
    ) -> None:
        self._sync = VerifNow(
            api_key,
            base_url=base_url,
            timeout=timeout,
            retry=retry,
            headers=headers,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"Async{self._sync!r}"

    async def validate_email(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_email, value, timeout=timeout)

    async def validate_phone(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_phone, value, timeout=timeout)

    async def validate_iban(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_iban, value, timeout=timeout)

    async def validate_vat(
        self,
        value: str,
        *,
        trader_name: str | None = None,
        timeout: float | None = None,
    ) -> ValidationResult:
        return await asyncio.to_thread(
            self._sync.validate_vat, value, trader_name=trader_name, timeout=timeout
        )

    async def validate_nas(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_nas, value, timeout=timeout)

    async def validate_ssn(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_ssn, value, timeout=timeout)

    async def validate_nif(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate_nif, value, timeout=timeout)

    async def validate(
        self, rule: ValidationRule, value: str, *, timeout: float | None = None
    ) -> ValidationResult:
        return await asyncio.to_thread(self._sync.validate, rule, value, timeout=timeout)

    async def vat_rates(self, *, timeout: float | None = None) -> VatRates:
        return await asyncio.to_thread(self._sync.vat_rates, timeout=timeout)

    async def vat_rate(self, country_code: str, *, timeout: float | None = None) -> CountryVatRates:
        return await asyncio.to_thread(self._sync.vat_rate, country_code, timeout=timeout)
