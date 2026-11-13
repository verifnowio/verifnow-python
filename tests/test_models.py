"""Response parsing: what each validator's details look like once typed."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from conftest import FakeTransport

from verifnow import ValidationResult, VerifNow


def validate(
    client: VerifNow, transport: FakeTransport, body: dict[str, object]
) -> ValidationResult:
    transport.reply(body=body)
    return client.validate("email", "value")


def test_given_an_email_response_then_signals_are_typed(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": False,
            "message": "Email address is unlikely to be deliverable",
            "normalizedValue": None,
            "originalValue": "user@exmaple.com",
            "validationLevel": "ADVANCED",
            "emailDetails": {
                "signals": {
                    "syntax_valid": True,
                    "mx_valid": False,
                    "typo_detected": True,
                    "suggested_domain": "example.com",
                    "disposable": False,
                    "role_based": False,
                    "free_provider": False,
                    "domain_age_days": 10950,
                    "mx_provider": "google",
                    "mx_quality_score": 0.9,
                },
                "risk_score": 85,
                "risk_level": "HIGH",
                "deliverability": "UNDELIVERABLE",
                "applied_level": "ADVANCED",
            },
        },
    )

    assert result.valid is False
    assert result.normalized_value is None
    assert result.original_value == "user@exmaple.com"
    assert result.validation_level == "ADVANCED"
    details = result.email_details
    assert details is not None and details.signals is not None
    assert details.signals.suggested_domain == "example.com"
    assert details.signals.domain_age_days == 10950
    assert details.signals.mx_quality_score == 0.9
    assert (details.risk_score, details.risk_level, details.deliverability) == (
        85.0,
        "HIGH",
        "UNDELIVERABLE",
    )
    assert result.vat_details is None


def test_given_standard_depth_then_advanced_signals_are_none_not_false(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": True,
            "emailDetails": {"signals": {"syntax_valid": True}, "applied_level": "STANDARD"},
        },
    )

    signals = result.email_details.signals  # type: ignore[union-attr]
    assert signals is not None
    assert signals.free_provider is None
    assert signals.domain_age_days is None


@pytest.mark.parametrize(
    ("registered", "expected"),
    [(True, True), (False, False), (None, None)],
)
def test_given_vat_registration_then_unknown_stays_distinct_from_not_registered(
    client: VerifNow, transport: FakeTransport, registered: bool | None, expected: bool | None
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": True,
            "vatDetails": {"format_valid": True, "registered": registered, "source": "UNVERIFIED"},
        },
    )

    assert result.vat_details is not None
    assert result.vat_details.registered is expected


def test_given_vat_registration_missing_then_it_reads_as_unknown(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(client, transport, {"valid": True, "vatDetails": {"format_valid": True}})

    assert result.vat_details is not None
    assert result.vat_details.registered is None


def test_given_a_full_vat_response_then_every_field_is_typed(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": True,
            "normalizedValue": "IE6388047V",
            "vatDetails": {
                "format_valid": True,
                "registered": True,
                "country_code": "IE",
                "source": "CACHE",
                "checked_at": "2026-11-13T10:15:30.123Z",
                "trader_name": "GOOGLE IRELAND LIMITED",
                "trader_address": "3RD FLOOR, GORDON HOUSE, DUBLIN 4",
                "vies_available": True,
                "consultation_number": "WAPIAAAAZ123",
                "trader_name_match": "MATCH",
                "trader_name_match_source": "VERIFNOW",
            },
        },
    )

    vat = result.vat_details
    assert vat is not None
    assert vat.checked_at == datetime(2026, 11, 13, 10, 15, 30, 123000, tzinfo=timezone.utc)
    assert vat.source == "CACHE"
    assert vat.trader_name == "GOOGLE IRELAND LIMITED"
    assert vat.consultation_number == "WAPIAAAAZ123"
    assert (vat.trader_name_match, vat.trader_name_match_source) == ("MATCH", "VERIFNOW")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-13T10:15:30Z", datetime(2026, 11, 13, 10, 15, 30, tzinfo=timezone.utc)),
        ("2026-11-13T10:15:30+00:00", datetime(2026, 11, 13, 10, 15, 30, tzinfo=timezone.utc)),
        ("2026-11-13T10:15:30", datetime(2026, 11, 13, 10, 15, 30, tzinfo=timezone.utc)),
        ("not a date", None),
        (1731492930, None),
    ],
)
def test_given_checked_at_formats_then_instants_are_aware(
    client: VerifNow, transport: FakeTransport, value: object, expected: datetime | None
) -> None:
    result = validate(client, transport, {"valid": True, "vatDetails": {"checked_at": value}})

    assert result.vat_details is not None
    assert result.vat_details.checked_at == expected


def test_given_a_value_a_newer_api_added_then_it_passes_through(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": True,
            "vatDetails": {"source": "MIRROR"},
            "phoneDetails": {"line_type": "SATELLITE"},
        },
    )

    assert result.vat_details is not None and result.vat_details.source == "MIRROR"  # type: ignore[comparison-overlap]
    assert result.phone_details is not None and result.phone_details.line_type == "SATELLITE"


def test_given_fields_of_the_wrong_type_then_they_read_as_none(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": "true",
            "normalizedValue": 42,
            "ibanDetails": {"length": True, "sepa": "yes", "expected_length": 27.0},
        },
    )

    assert result.valid is False  # only a JSON true is valid
    assert result.normalized_value is None
    iban = result.iban_details
    assert iban is not None
    assert iban.length is None  # a JSON true is not a count
    assert iban.sepa is None
    assert iban.expected_length == 27


def test_given_phone_iban_nas_nif_ssn_details_then_they_are_typed(
    client: VerifNow, transport: FakeTransport
) -> None:
    result = validate(
        client,
        transport,
        {
            "valid": True,
            "phoneDetails": {
                "country_code": "FR",
                "calling_code": 33,
                "line_type": "MOBILE",
                "international_format": "+33 6 12 34 56 78",
                "national_format": "06 12 34 56 78",
            },
            "ibanDetails": {
                "country_code": "FR",
                "sepa": True,
                "structure_valid": True,
                "checksum_valid": True,
                "length": 27,
                "expected_length": 27,
                "formatted": "FR76 3000 6000 0112 3456 7890 189",
            },
            "nasDetails": {
                "checksum_valid": True,
                "temporary_resident": False,
                "individual_series": False,
                "formatted": "046 454 286",
            },
            "nifDetails": {
                "type": "ENTITY",
                "natural_person": False,
                "checksum_valid": True,
                "entity_letter": "B",
                "entity_type": "Private limited company",
            },
            "ssnDetails": {"itin": True},
        },
    )

    assert result.phone_details is not None and result.phone_details.calling_code == 33
    assert result.iban_details is not None and result.iban_details.sepa is True
    assert result.nas_details is not None and result.nas_details.formatted == "046 454 286"
    assert result.nif_details is not None and result.nif_details.entity_letter == "B"
    assert result.ssn_details is not None and result.ssn_details.itin is True


def test_given_any_response_then_the_raw_body_is_kept(
    client: VerifNow, transport: FakeTransport
) -> None:
    body = {"valid": True, "futureField": {"a": 1}}
    assert validate(client, transport, body).raw == body


def test_given_results_then_they_are_immutable(client: VerifNow, transport: FakeTransport) -> None:
    result = validate(client, transport, {"valid": True})
    with pytest.raises(AttributeError):
        result.valid = False  # type: ignore[misc]
