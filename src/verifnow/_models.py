"""Typed results returned by the client.

The API speaks camelCase at the top level and snake_case inside the details objects; everything here
is snake_case, so a Python caller does not switch conventions mid-expression. Every result keeps the
untouched JSON body on ``raw``, for fields this SDK version does not model yet.

Enumerated values (``source``, ``line_type``…) are plain strings typed with ``Literal``. A value a
newer API adds is passed through as-is rather than failing the whole response.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ValidationRule = Literal["email", "phone", "iban", "vat", "nas", "ssn", "nif"]

VALIDATION_RULES: tuple[ValidationRule, ...] = (
    "email",
    "phone",
    "iban",
    "vat",
    "nas",
    "ssn",
    "nif",
)

ValidationLevel = Literal["BASIC", "STANDARD", "ADVANCED", "PREMIUM"]
"""Depth of checks applied, decided by the plan attached to the API key.

``STANDARD`` runs on the FREE and STARTER plans, ``ADVANCED`` on GROWTH, ``PREMIUM`` on PRO. Branch
on this rather than on the plan name: it is the only value that says which signals are present.
"""

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
Deliverability = Literal["DELIVERABLE", "RISKY", "UNDELIVERABLE", "UNKNOWN"]

VatSource = Literal["LIVE", "CACHE", "STALE", "UNVERIFIED", "NOT_APPLICABLE"]
"""Where a VAT registration verdict came from.

``LIVE``: confirmed against VIES during this request. ``CACHE``: a VIES answer less than 24 hours
old. ``STALE``: VIES was unreachable, so an older cached answer was used. ``UNVERIFIED``: VIES was
unreachable and nothing was cached. ``NOT_APPLICABLE``: the country is outside VIES.
"""

TraderNameMatch = Literal["MATCH", "MISMATCH", "NOT_AVAILABLE"]
TraderNameMatchSource = Literal["VIES", "VERIFNOW"]

PhoneLineType = Literal[
    "MOBILE",
    "FIXED_LINE",
    "FIXED_LINE_OR_MOBILE",
    "TOLL_FREE",
    "PREMIUM_RATE",
    "SHARED_COST",
    "VOIP",
    "PERSONAL_NUMBER",
    "PAGER",
    "UAN",
    "VOICEMAIL",
    "UNKNOWN",
]
"""Kind of line, from the country's numbering plan.

A ``PREMIUM_RATE`` or ``VOIP`` number is still ``valid``: it exists. This is how you decide to
exclude one, rather than the API deciding for you. The US and Canada are ``FIXED_LINE_OR_MOBILE``.
"""

NifType = Literal["DNI", "NIE", "NIF_K", "NIF_L", "NIF_M", "ENTITY"]


@dataclass(frozen=True, slots=True)
class EmailSignals:
    """Per-signal breakdown behind an email verdict.

    A field is ``None`` when the applied level does not compute it: ``free_provider``,
    ``domain_age_days``, ``mx_provider`` and ``mx_quality_score`` need ``ADVANCED`` or higher.
    """

    syntax_valid: bool | None = None
    mx_valid: bool | None = None
    typo_detected: bool | None = None
    suggested_domain: str | None = None
    """The correction proposed when ``typo_detected`` is true, e.g. ``gmail.com``."""
    disposable: bool | None = None
    role_based: bool | None = None
    """The local part is a shared mailbox: ``info@``, ``admin@``, ``noreply@``."""
    free_provider: bool | None = None
    domain_age_days: int | None = None
    mx_provider: str | None = None
    mx_quality_score: float | None = None


@dataclass(frozen=True, slots=True)
class EmailDetails:
    """Email diagnostics. Absent when the applied level is ``BASIC``."""

    signals: EmailSignals | None = None
    risk_score: float | None = None
    """Aggregated risk from 0 to 100, where 0 is the lowest risk. Available on every plan."""
    risk_level: RiskLevel | None = None
    """Requires ``ADVANCED`` or higher."""
    deliverability: Deliverability | None = None
    applied_level: ValidationLevel | None = None


@dataclass(frozen=True, slots=True)
class VatDetails:
    """VAT diagnostics. Present on ``vat`` validations."""

    registered: bool | None = None
    """Present in the member state's registry.

    **``None`` means unknown, never "not registered".** It is returned when VIES could not be
    consulted. Treating ``None`` as ``False`` rejects legitimate customers during someone else's
    outage.
    """
    format_valid: bool | None = None
    """The number matches its member state's structure. Decided locally, never depends on VIES."""
    country_code: str | None = None
    """Member state, e.g. ``IE``. Greece is ``EL``, Northern Ireland ``XI``."""
    source: VatSource | None = None
    checked_at: datetime | None = None
    """When the registration was last confirmed against VIES."""
    trader_name: str | None = None
    """Registered trading name, when the member state discloses it. Germany does not."""
    trader_address: str | None = None
    vies_available: bool | None = None
    consultation_number: str | None = None
    """The receipt VIES issues for this lookup, which tax authorities accept as proof of the check.

    Present only when your account has its own VAT number configured: VIES issues one only to an
    identified requester.
    """
    trader_name_match: TraderNameMatch | None = None
    """Present when a ``trader_name`` was sent. ``MISMATCH`` is a question for a human, not proof of
    fraud: trading names and group companies differ."""
    trader_name_match_source: TraderNameMatchSource | None = None


@dataclass(frozen=True, slots=True)
class PhoneDetails:
    """Phone diagnostics, present whenever the input parsed as an international number."""

    country_code: str | None = None
    """ISO 3166-1 alpha-2, e.g. ``FR``. Absent when the calling code is shared by several."""
    calling_code: int | None = None
    line_type: PhoneLineType | None = None
    international_format: str | None = None
    national_format: str | None = None


@dataclass(frozen=True, slots=True)
class IbanDetails:
    """IBAN diagnostics.

    ``structure_valid`` answers "could this be an account number in that country" (the SWIFT
    registry's length and layout); ``checksum_valid`` answers "was it typed correctly" (mod-97).
    """

    country_code: str | None = None
    sepa: bool | None = None
    """The country is inside the SEPA schemes' scope, so a bank there may collect a SEPA direct
    debit. Whether this particular bank does cannot be read from an IBAN."""
    structure_valid: bool | None = None
    checksum_valid: bool | None = None
    length: int | None = None
    expected_length: int | None = None
    formatted: str | None = None
    """Print format in groups of four. Present only for a valid IBAN."""


@dataclass(frozen=True, slots=True)
class NasDetails:
    """Canadian Social Insurance Number diagnostics."""

    checksum_valid: bool | None = None
    temporary_resident: bool | None = None
    """A 9-series number: it expires with the holder's permit, and the number does not say when."""
    individual_series: bool | None = None
    """``False`` for numbers starting with 0 or 8, which are not issued to individuals."""
    formatted: str | None = None


@dataclass(frozen=True, slots=True)
class NifDetails:
    """Spanish NIF diagnostics: a DNI, a NIE, the K/L/M series, or a company NIF."""

    type: NifType | None = None
    natural_person: bool | None = None
    checksum_valid: bool | None = None
    entity_letter: str | None = None
    entity_type: str | None = None


@dataclass(frozen=True, slots=True)
class SsnDetails:
    """US SSN diagnostics."""

    itin: bool | None = None
    """The number is an IRS ITIN, not an SSN. ``valid`` is ``False`` for the SSN, but an ITIN is an
    acceptable taxpayer number where one is accepted (a W-9, for instance)."""


@dataclass(frozen=True, slots=True)
class QuotaInfo:
    """Quota counters read from the ``X-RateLimit-*`` response headers."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None
    overage: bool = False
    """True once a paid plan is past its included quota and billed per unit."""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a single validation call."""

    valid: bool
    """Whether the value passed every check the applied level ran."""
    normalized_value: str | None
    """Canonical form of the input, ``None`` when the value is invalid."""
    raw: Mapping[str, Any] = field(repr=False)
    """The unmodified JSON body."""
    message: str | None = None
    original_value: str | None = None
    validation_level: ValidationLevel | None = None
    email_details: EmailDetails | None = None
    vat_details: VatDetails | None = None
    phone_details: PhoneDetails | None = None
    iban_details: IbanDetails | None = None
    nas_details: NasDetails | None = None
    nif_details: NifDetails | None = None
    ssn_details: SsnDetails | None = None
    quota: QuotaInfo | None = None


@dataclass(frozen=True, slots=True)
class RegionalVatRate:
    """A VAT rate applying to part of a member state only: an overseas department, an island."""

    rate: float
    note: str | None = None
    eu_vat_area: bool | None = None
    """``False`` for the Canary Islands and the French overseas territories, which the VAT Directive
    excludes: goods shipped there from another member state are an export."""


@dataclass(frozen=True, slots=True)
class CountryVatRates:
    """One EU member state's VAT rates, from the European Commission's TEDB.

    These are the rates the member state has, not the rate a sale is charged. In B2B trade between
    member states the invoice is usually zero-rated under the reverse charge.
    """

    country_code: str
    """As TEDB and VIES name it: Greece is ``EL``."""
    standard_rate: float
    reduced_rates: tuple[float, ...] = ()
    regional_rates: tuple[RegionalVatRate, ...] = ()
    situation_on: str | None = None
    """The date the rates apply from, ``YYYY-MM-DD``. Kept as a string: it has no time zone."""
    fetched_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VatRates:
    """VAT rates of every EU member state."""

    source: str
    rates: tuple[CountryVatRates, ...]
    source_url: str | None = None


# ---------------------------------------------------------------------------------------------
# Parsing. Lenient by design: a field with an unexpected type becomes None rather than failing
# the whole response, and the raw body stays available.


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _int(value: Any) -> int | None:
    # bool is a subclass of int in Python; a JSON true is not a count.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    # fromisoformat only accepts a trailing Z from Python 3.11.
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # The API serialises instants in UTC; a naive value is read as UTC rather than local time.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _obj(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _email_details(raw: Any) -> EmailDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    s = _obj(d.get("signals"))
    signals = (
        None
        if s is None
        else EmailSignals(
            syntax_valid=_bool(s.get("syntax_valid")),
            mx_valid=_bool(s.get("mx_valid")),
            typo_detected=_bool(s.get("typo_detected")),
            suggested_domain=_str(s.get("suggested_domain")),
            disposable=_bool(s.get("disposable")),
            role_based=_bool(s.get("role_based")),
            free_provider=_bool(s.get("free_provider")),
            domain_age_days=_int(s.get("domain_age_days")),
            mx_provider=_str(s.get("mx_provider")),
            mx_quality_score=_float(s.get("mx_quality_score")),
        )
    )
    return EmailDetails(
        signals=signals,
        risk_score=_float(d.get("risk_score")),
        risk_level=_str(d.get("risk_level")),  # type: ignore[arg-type]
        deliverability=_str(d.get("deliverability")),  # type: ignore[arg-type]
        applied_level=_str(d.get("applied_level")),  # type: ignore[arg-type]
    )


def _vat_details(raw: Any) -> VatDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    return VatDetails(
        # A missing key is read as None too: unknown, not absent.
        registered=_bool(d.get("registered")),
        format_valid=_bool(d.get("format_valid")),
        country_code=_str(d.get("country_code")),
        source=_str(d.get("source")),  # type: ignore[arg-type]
        checked_at=parse_datetime(d.get("checked_at")),
        trader_name=_str(d.get("trader_name")),
        trader_address=_str(d.get("trader_address")),
        vies_available=_bool(d.get("vies_available")),
        consultation_number=_str(d.get("consultation_number")),
        trader_name_match=_str(d.get("trader_name_match")),  # type: ignore[arg-type]
        trader_name_match_source=_str(d.get("trader_name_match_source")),  # type: ignore[arg-type]
    )


def _phone_details(raw: Any) -> PhoneDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    return PhoneDetails(
        country_code=_str(d.get("country_code")),
        calling_code=_int(d.get("calling_code")),
        line_type=_str(d.get("line_type")),  # type: ignore[arg-type]
        international_format=_str(d.get("international_format")),
        national_format=_str(d.get("national_format")),
    )


def _iban_details(raw: Any) -> IbanDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    return IbanDetails(
        country_code=_str(d.get("country_code")),
        sepa=_bool(d.get("sepa")),
        structure_valid=_bool(d.get("structure_valid")),
        checksum_valid=_bool(d.get("checksum_valid")),
        length=_int(d.get("length")),
        expected_length=_int(d.get("expected_length")),
        formatted=_str(d.get("formatted")),
    )


def _nas_details(raw: Any) -> NasDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    return NasDetails(
        checksum_valid=_bool(d.get("checksum_valid")),
        temporary_resident=_bool(d.get("temporary_resident")),
        individual_series=_bool(d.get("individual_series")),
        formatted=_str(d.get("formatted")),
    )


def _nif_details(raw: Any) -> NifDetails | None:
    d = _obj(raw)
    if d is None:
        return None
    return NifDetails(
        type=_str(d.get("type")),  # type: ignore[arg-type]
        natural_person=_bool(d.get("natural_person")),
        checksum_valid=_bool(d.get("checksum_valid")),
        entity_letter=_str(d.get("entity_letter")),
        entity_type=_str(d.get("entity_type")),
    )


def _ssn_details(raw: Any) -> SsnDetails | None:
    d = _obj(raw)
    return None if d is None else SsnDetails(itin=_bool(d.get("itin")))


def parse_validation_result(
    payload: Mapping[str, Any], quota: QuotaInfo | None
) -> ValidationResult:
    return ValidationResult(
        valid=payload.get("valid") is True,
        normalized_value=_str(payload.get("normalizedValue")),
        raw=payload,
        message=_str(payload.get("message")),
        original_value=_str(payload.get("originalValue")),
        validation_level=_str(payload.get("validationLevel")),  # type: ignore[arg-type]
        email_details=_email_details(payload.get("emailDetails")),
        vat_details=_vat_details(payload.get("vatDetails")),
        phone_details=_phone_details(payload.get("phoneDetails")),
        iban_details=_iban_details(payload.get("ibanDetails")),
        nas_details=_nas_details(payload.get("nasDetails")),
        nif_details=_nif_details(payload.get("nifDetails")),
        ssn_details=_ssn_details(payload.get("ssnDetails")),
        quota=quota,
    )


def _regional_rate(raw: Mapping[str, Any]) -> RegionalVatRate:
    rate = _float(raw.get("rate"))
    return RegionalVatRate(
        # 0 is a real rate (zero-rated territories); only a missing one is NaN.
        rate=float("nan") if rate is None else rate,
        note=_str(raw.get("note")),
        eu_vat_area=_bool(raw.get("euVatArea")),
    )


def parse_country_vat_rates(raw: Mapping[str, Any]) -> CountryVatRates:
    reduced = raw.get("reducedRates")
    regional = raw.get("regionalRates")
    standard = _float(raw.get("standardRate"))
    return CountryVatRates(
        country_code=_str(raw.get("countryCode")) or "",
        standard_rate=float("nan") if standard is None else standard,
        reduced_rates=tuple(
            r
            for r in (_float(v) for v in (reduced if isinstance(reduced, list) else []))
            if r is not None
        ),
        regional_rates=tuple(
            _regional_rate(r)
            for r in (regional if isinstance(regional, list) else [])
            if isinstance(r, Mapping)
        ),
        situation_on=_str(raw.get("situationOn")),
        fetched_at=parse_datetime(raw.get("fetchedAt")),
    )


def parse_vat_rates(raw: Mapping[str, Any]) -> VatRates:
    rates = raw.get("rates")
    return VatRates(
        source=_str(raw.get("source")) or "TEDB",
        source_url=_str(raw.get("sourceUrl")),
        rates=tuple(
            parse_country_vat_rates(r)
            for r in (rates if isinstance(rates, list) else [])
            if isinstance(r, Mapping)
        ),
    )
