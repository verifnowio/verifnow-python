"""The synchronous client."""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Final, TypeVar
from urllib.parse import quote

from ._errors import (
    VerifNowAuthError,
    VerifNowConnectionError,
    VerifNowError,
    VerifNowRateLimitError,
    VerifNowRequestError,
    VerifNowResponseError,
    VerifNowServerError,
)
from ._models import (
    VALIDATION_RULES,
    CountryVatRates,
    QuotaInfo,
    ValidationResult,
    ValidationRule,
    VatRates,
    parse_country_vat_rates,
    parse_validation_result,
    parse_vat_rates,
)
from ._transport import HttpRequest, HttpResponse, Transport, TransportError, urllib_transport
from ._version import __version__

DEFAULT_BASE_URL: Final = "https://api.verifnow.io"
DEFAULT_TIMEOUT: Final = 5.0
API_KEY_ENV: Final = "VERIFNOW_API_KEY"

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retries for connection failures, timeouts, 5xx and short 429s.

    ``attempts`` is the number of retries after the first failure, so the default makes up to three
    requests. Delays are in seconds and double each attempt, capped at ``max_backoff``.
    """

    attempts: int = 2
    backoff: float = 0.2
    max_backoff: float = 2.0


class VerifNow:
    """Client for the VerifNow validation API.

    >>> from verifnow import VerifNow
    >>> client = VerifNow()  # reads VERIFNOW_API_KEY
    >>> result = client.validate_email("user@exmaple.com")
    >>> result.valid, result.email_details.signals.suggested_domain
    (False, 'example.com')

    The client holds no per-request state: create one and share it across threads.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retry: RetryPolicy | None = RetryPolicy(),
        headers: Mapping[str, str] | None = None,
        transport: Transport | None = None,
    ) -> None:
        """Create a client.

        ``api_key`` defaults to the ``VERIFNOW_API_KEY`` environment variable.
        ``timeout`` applies to each attempt, in seconds. Pass ``retry=None`` to disable retries.
        ``headers`` are added to every request. ``transport`` replaces the ``urllib`` one, for
        tests or custom networking.
        """
        key = api_key if api_key is not None else os.environ.get(API_KEY_ENV)
        if key is None or not key.strip():
            raise VerifNowError(
                "A VerifNow API key is required. Create one at https://app.verifnow.io and pass it "
                f"as `api_key`, or set the {API_KEY_ENV} environment variable."
            )
        if timeout <= 0:
            raise ValueError("timeout must be a positive number of seconds")

        if not base_url.lower().startswith(("https://", "http://")):
            # urllib also opens file:// and ftp:// URLs; a validation client has no business there.
            raise ValueError(f"base_url must be an http(s) URL, got {base_url!r}")

        self._api_key = key.strip()
        # Trailing slashes would produce `//api/v1/...`, which some proxies reject.
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retry = retry
        self._headers = dict(headers or {})
        self._transport: Transport = transport or urllib_transport
        self._sleep: Callable[[float], None] = time.sleep

    def __repr__(self) -> str:
        # Never the key: a repr ends up in logs and tracebacks.
        return f"VerifNow(base_url={self._base_url!r})"

    # -- validators -------------------------------------------------------------------------------

    def validate_email(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate an email address: syntax, DNS/MX, typo, disposable, role-based, risk score."""
        return self.validate("email", value, timeout=timeout)

    def validate_phone(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate a phone number against its country's numbering plan.

        The number must include its country code (``+33…`` or ``0033…``). A valid number comes back
        in E.164 as ``normalized_value``, with country and line type in ``phone_details``.
        """
        return self.validate("phone", value, timeout=timeout)

    def validate_iban(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate an IBAN: the SWIFT registry entry for its country, then its check digits."""
        return self.validate("iban", value, timeout=timeout)

    def validate_vat(
        self,
        value: str,
        *,
        trader_name: str | None = None,
        timeout: float | None = None,
    ) -> ValidationResult:
        """Validate an EU VAT number against VIES.

        Pass ``trader_name`` to ask whether the number belongs to that company:
        ``vat_details.trader_name_match`` answers ``MATCH``, ``MISMATCH`` or ``NOT_AVAILABLE``.

        ``vat_details.registered`` is ``None`` when VIES could not be consulted. That means unknown,
        never "not registered".
        """
        extra = {"traderName": trader_name} if trader_name and trader_name.strip() else None
        return self._validate("vat", value, timeout, extra)

    def validate_nas(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate a Canadian Social Insurance Number: format and Luhn check digit."""
        return self.validate("nas", value, timeout=timeout)

    def validate_ssn(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate a US Social Security Number against the numbers the SSA never issues."""
        return self.validate("ssn", value, timeout=timeout)

    def validate_nif(self, value: str, *, timeout: float | None = None) -> ValidationResult:
        """Validate a Spanish NIF: a DNI, a NIE, the K/L/M series, or a company NIF."""
        return self.validate("nif", value, timeout=timeout)

    def validate(
        self, rule: ValidationRule, value: str, *, timeout: float | None = None
    ) -> ValidationResult:
        """Validate a value against any rule. Use it when the rule is chosen at runtime."""
        return self._validate(rule, value, timeout, None)

    # -- VAT rates --------------------------------------------------------------------------------

    def vat_rates(self, *, timeout: float | None = None) -> VatRates:
        """EU VAT rates of every member state, from the Commission's TEDB. Spends no quota."""
        url = f"{self._base_url}/api/v1/vat/rates"
        return self._with_retry(
            lambda: self._request_once("GET", url, None, timeout, lambda p, _q: parse_vat_rates(p))
        )

    def vat_rate(self, country_code: str, *, timeout: float | None = None) -> CountryVatRates:
        """One member state's VAT rates. Accepts ``GR`` for Greece as well as ``EL``.

        A code outside the 27 member states raises ``VerifNowRequestError`` (HTTP 404).
        """
        if not isinstance(country_code, str) or not country_code.strip():
            raise VerifNowRequestError('A member state code is required, e.g. "FR".')
        url = f"{self._base_url}/api/v1/vat/rates/{quote(country_code.strip(), safe='')}"
        return self._with_retry(
            lambda: self._request_once(
                "GET", url, None, timeout, lambda p, _q: parse_country_vat_rates(p)
            )
        )

    # -- internals --------------------------------------------------------------------------------

    def _validate(
        self,
        rule: str,
        value: str,
        timeout: float | None,
        extra: Mapping[str, str] | None,
    ) -> ValidationResult:
        if rule not in VALIDATION_RULES:
            raise VerifNowRequestError(
                f'Unknown rule "{rule}". Expected one of: {", ".join(VALIDATION_RULES)}.'
            )
        if not isinstance(value, str) or not value.strip():
            # Caught here rather than server-side: an empty value spends quota and can only fail.
            raise VerifNowRequestError(f'Cannot validate an empty value for rule "{rule}".')

        url = f"{self._base_url}/api/v1/validate/{rule}"
        body = json.dumps({"value": value, **(extra or {})}).encode()
        return self._with_retry(
            lambda: self._request_once("POST", url, body, timeout, parse_validation_result)
        )

    def _with_retry(self, attempt_once: Callable[[], T]) -> T:
        max_attempts = 1 + (self._retry.attempts if self._retry else 0)
        for attempt in range(max_attempts):
            try:
                return attempt_once()
            except VerifNowError as error:
                if attempt == max_attempts - 1:
                    raise
                delay = self._retry_delay(error, attempt)
                if delay is None:
                    raise
                self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    def _retry_delay(self, error: VerifNowError, attempt: int) -> float | None:
        """Seconds to wait before retrying, or ``None`` when the error should surface now.

        A 429 is retried only when its reset is close: the concurrency limit clears in
        milliseconds, a spent monthly quota does not, and sleeping on it helps nobody.
        """
        retry = self._retry
        if retry is None:  # pragma: no cover - max_attempts is 1 then
            return None
        backoff = min(retry.backoff * math.pow(2, attempt), retry.max_backoff)

        if isinstance(error, VerifNowRateLimitError):
            wait = error.retry_after or 0.0
            if wait > retry.max_backoff:
                return None
            return max(wait, backoff)
        # A timeout is retried too: the deadline is ours, and the next attempt gets a fresh one.
        if isinstance(error, (VerifNowServerError, VerifNowConnectionError)):
            return backoff
        # 400, 401 and unparseable bodies fail identically on a second attempt.
        return None

    def _request_once(
        self,
        method: str,
        url: str,
        body: bytes | None,
        timeout: float | None,
        parse: Callable[[Mapping[str, Any], QuotaInfo | None], T],
    ) -> T:
        effective_timeout = self._timeout if timeout is None else timeout
        headers = {
            "User-Agent": f"verifnow-python/{__version__}",
            **self._headers,
            "Accept": "application/json",
            "X-API-KEY": self._api_key,
            "X-VerifNow-SDK": f"python/{__version__}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = self._transport(
                HttpRequest(
                    method=method, url=url, headers=headers, body=body, timeout=effective_timeout
                )
            )
        except TransportError as error:
            if error.timed_out:
                message = f"VerifNow request to {url} timed out after {effective_timeout:g}s."
            else:
                message = (
                    f"Could not reach the VerifNow API at {url}: {error}. "
                    "Check `base_url` and network access."
                )
            raise VerifNowConnectionError(message, timed_out=error.timed_out) from error

        return _handle_response(response, parse)


def _handle_response(
    response: HttpResponse,
    parse: Callable[[Mapping[str, Any], QuotaInfo | None], T],
) -> T:
    request_id = response.header("X-Request-Id")
    quota = _parse_quota(response)
    status = response.status

    if 200 <= status < 300:
        try:
            payload = json.loads(response.body)
        except (ValueError, UnicodeDecodeError) as error:
            raise VerifNowResponseError(
                "VerifNow returned a success status with a body that is not valid JSON.",
                status=status,
                request_id=request_id,
            ) from error
        if not isinstance(payload, dict):
            raise VerifNowResponseError(
                "VerifNow returned an unexpected response shape.",
                status=status,
                request_id=request_id,
            )
        return parse(payload, quota)

    message = _error_message(response)

    if status in (401, 403):
        raise VerifNowAuthError(
            f"VerifNow rejected the API key ({status}): {message}",
            status=status,
            request_id=request_id,
        )
    if status == 429:
        raise VerifNowRateLimitError(
            f"VerifNow rate limit reached: {message}",
            status=status,
            request_id=request_id,
            quota=quota,
            retry_after=_parse_retry_after(response, quota),
        )
    if status >= 500:
        raise VerifNowServerError(
            f"VerifNow returned {status}: {message}", status=status, request_id=request_id
        )
    raise VerifNowRequestError(
        f"VerifNow rejected the request ({status}): {message}",
        status=status,
        request_id=request_id,
    )


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_quota(response: HttpResponse) -> QuotaInfo | None:
    limit = _to_int(response.header("X-RateLimit-Limit"))
    remaining = _to_int(response.header("X-RateLimit-Remaining"))
    reset = _to_int(response.header("X-RateLimit-Reset"))
    overage = (response.header("X-Quota-Overage") or "").strip().lower() == "true"
    if limit is None and remaining is None and reset is None and not overage:
        return None
    return QuotaInfo(
        limit=limit,
        remaining=remaining,
        reset_at=None if reset is None else datetime.fromtimestamp(reset, tz=timezone.utc),
        overage=overage,
    )


def _parse_retry_after(response: HttpResponse, quota: QuotaInfo | None) -> float | None:
    now = datetime.now(timezone.utc)
    header = response.header("Retry-After")
    if header is not None:
        try:
            seconds = float(header)
            if math.isfinite(seconds):
                return max(0.0, seconds)
        except ValueError:
            pass
        # RFC 9110 also allows an HTTP-date.
        try:
            when = parsedate_to_datetime(header)
        except (TypeError, ValueError):
            when = None
        if when is not None:
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return float(max(0, math.ceil((when - now).total_seconds())))

    if quota is not None and quota.reset_at is not None:
        return float(max(0, math.ceil((quota.reset_at - now).total_seconds())))
    return None


def _error_message(response: HttpResponse) -> str:
    text = response.body.decode("utf-8", errors="replace").strip()
    if not text:
        return "no details"
    try:
        parsed = json.loads(text)
    except ValueError:
        # Not JSON: a proxy or the servlet container's default error page.
        return text[:500]
    if isinstance(parsed, dict):
        for key in ("message", "error"):
            value = parsed.get(key)
            if isinstance(value, str) and value:
                return value
    return text[:500]
