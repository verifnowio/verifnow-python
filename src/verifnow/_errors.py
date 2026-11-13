"""Exceptions raised by the SDK.

The SDK fails loudly on purpose. A validation client that swallows a network failure and reports
``valid=True`` turns an outage into silently accepted bad data, and the outage stays invisible until
someone audits the database. Catch these and decide explicitly: accepting the input on failure is a
reasonable choice, but it should be a choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._models import QuotaInfo


class VerifNowError(Exception):
    """Base class for every error this SDK raises.

    ``status`` is the HTTP status when the failure came back from the API rather than the network.
    ``request_id`` is the ``X-Request-Id`` response header, useful in a support request.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id


class VerifNowAuthError(VerifNowError):
    """The API key is missing, malformed, revoked, or not authorised for this endpoint (401/403)."""


class VerifNowRequestError(VerifNowError):
    """The request was rejected as malformed (400, 404, 422).

    Retrying is pointless: the payload itself needs to change.
    """


class VerifNowRateLimitError(VerifNowError):
    """The monthly quota or the concurrency limit was exceeded (429).

    ``retry_after`` is the number of seconds to wait, from ``Retry-After`` or ``X-RateLimit-Reset``.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        request_id: str | None = None,
        quota: QuotaInfo | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status=status, request_id=request_id)
        self.quota = quota
        self.retry_after = retry_after


class VerifNowServerError(VerifNowError):
    """The API failed to process the request (5xx). Retried automatically before surfacing."""


class VerifNowConnectionError(VerifNowError):
    """The API could not be reached: DNS failure, refused connection, TLS error, or timeout.

    A wrong ``base_url`` surfaces here, which is why the message names the URL it tried.
    ``timed_out`` is true when the failure was the client-side timeout.
    """

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


class VerifNowResponseError(VerifNowError):
    """The API returned a success status with a body this SDK could not parse."""
