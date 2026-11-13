"""Official Python SDK for the VerifNow validation API.

Email, phone, IBAN, VAT, SSN, SIN and NIF validation with one API key. https://www.verifnow.io
"""

from ._async import AsyncVerifNow
from ._client import RetryPolicy, VerifNow
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
    Deliverability,
    EmailDetails,
    EmailSignals,
    IbanDetails,
    NasDetails,
    NifDetails,
    NifType,
    PhoneDetails,
    PhoneLineType,
    QuotaInfo,
    RegionalVatRate,
    RiskLevel,
    SsnDetails,
    TraderNameMatch,
    TraderNameMatchSource,
    ValidationLevel,
    ValidationResult,
    ValidationRule,
    VatDetails,
    VatRates,
    VatSource,
)
from ._transport import HttpRequest, HttpResponse, Transport, TransportError
from ._version import __version__

__all__ = [
    "VALIDATION_RULES",
    "AsyncVerifNow",
    "CountryVatRates",
    "Deliverability",
    "EmailDetails",
    "EmailSignals",
    "HttpRequest",
    "HttpResponse",
    "IbanDetails",
    "NasDetails",
    "NifDetails",
    "NifType",
    "PhoneDetails",
    "PhoneLineType",
    "QuotaInfo",
    "RegionalVatRate",
    "RetryPolicy",
    "RiskLevel",
    "SsnDetails",
    "TraderNameMatch",
    "TraderNameMatchSource",
    "Transport",
    "TransportError",
    "ValidationLevel",
    "ValidationResult",
    "ValidationRule",
    "VatDetails",
    "VatRates",
    "VatSource",
    "VerifNow",
    "VerifNowAuthError",
    "VerifNowConnectionError",
    "VerifNowError",
    "VerifNowRateLimitError",
    "VerifNowRequestError",
    "VerifNowResponseError",
    "VerifNowServerError",
    "__version__",
]
