from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
from conftest import FakeTransport

from verifnow import (
    RetryPolicy,
    VerifNow,
    VerifNowAuthError,
    VerifNowConnectionError,
    VerifNowError,
    VerifNowRateLimitError,
    VerifNowRequestError,
    VerifNowResponseError,
    VerifNowServerError,
    __version__,
)

VALID = {"valid": True, "normalizedValue": "x", "message": "ok"}


# -- configuration ---------------------------------------------------------------------------------


def test_given_no_key_anywhere_when_creating_then_it_fails_with_how_to_get_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VERIFNOW_API_KEY", raising=False)
    with pytest.raises(VerifNowError, match="VERIFNOW_API_KEY"):
        VerifNow()


def test_given_a_blank_key_when_creating_then_it_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERIFNOW_API_KEY", raising=False)
    with pytest.raises(VerifNowError):
        VerifNow("   ")


def test_given_the_env_variable_when_creating_without_key_then_it_is_sent(
    monkeypatch: pytest.MonkeyPatch, transport: FakeTransport
) -> None:
    monkeypatch.setenv("VERIFNOW_API_KEY", " vn_from_env ")
    transport.reply(body=VALID)

    VerifNow(transport=transport).validate_email("a@b.co")

    assert transport.last.headers["X-API-KEY"] == "vn_from_env"


@pytest.mark.parametrize(
    "base_url", ["file:///etc/passwd", "ftp://api.verifnow.io", "api.verifnow.io"]
)
def test_given_a_non_http_base_url_when_creating_then_it_is_refused(base_url: str) -> None:
    with pytest.raises(ValueError, match="http"):
        VerifNow("vn_test_key", base_url=base_url)


def test_given_a_client_when_printed_then_the_key_does_not_appear() -> None:
    client = VerifNow("vn_secret_value")
    assert "vn_secret_value" not in repr(client)


def test_given_a_trailing_slash_in_base_url_when_calling_then_the_path_is_clean(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(body=VALID)

    make_client(base_url="https://api-dev.verifnow.io//").validate_iban("FR76")

    assert transport.last.url == "https://api-dev.verifnow.io/api/v1/validate/iban"


# -- wire contract ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "rule"),
    [
        ("validate_email", "email"),
        ("validate_phone", "phone"),
        ("validate_iban", "iban"),
        ("validate_vat", "vat"),
        ("validate_nas", "nas"),
        ("validate_ssn", "ssn"),
        ("validate_nif", "nif"),
    ],
)
def test_given_each_validator_when_called_then_it_posts_the_value_to_its_rule(
    client: VerifNow, transport: FakeTransport, method: str, rule: str
) -> None:
    transport.reply(body=VALID)

    getattr(client, method)("some value")

    assert transport.last.method == "POST"
    assert transport.last.url == f"https://api.verifnow.io/api/v1/validate/{rule}"
    assert transport.last_json() == {"value": "some value"}


def test_given_any_call_then_it_identifies_the_sdk_and_its_version(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(body=VALID)

    make_client(headers={"X-Trace-Id": "t-1"}).validate_email("a@b.co")

    headers = transport.last.headers
    assert headers["X-VerifNow-SDK"] == f"python/{__version__}"
    assert headers["User-Agent"] == f"verifnow-python/{__version__}"
    assert headers["X-API-KEY"] == "vn_test_key"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert headers["X-Trace-Id"] == "t-1"


def test_given_custom_headers_when_they_collide_then_the_key_and_sdk_header_win(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(body=VALID)

    make_client(headers={"X-API-KEY": "other", "X-VerifNow-SDK": "custom"}).validate_email("a@b.co")

    assert transport.last.headers["X-API-KEY"] == "vn_test_key"
    assert transport.last.headers["X-VerifNow-SDK"] == f"python/{__version__}"


def test_given_a_trader_name_when_validating_vat_then_it_is_sent(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(body=VALID)

    client.validate_vat("ESA28015865", trader_name="Telefonica")

    assert transport.last_json() == {"value": "ESA28015865", "traderName": "Telefonica"}


def test_given_a_blank_trader_name_when_validating_vat_then_it_is_left_out(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(body=VALID)

    client.validate_vat("IE6388047V", trader_name="  ")

    assert transport.last_json() == {"value": "IE6388047V"}


def test_given_a_per_call_timeout_then_it_overrides_the_client_one(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(body=VALID).reply(body=VALID)
    client = make_client(timeout=7)

    client.validate_email("a@b.co")
    client.validate_email("a@b.co", timeout=1.5)

    assert [r.timeout for r in transport.requests] == [7, 1.5]


@pytest.mark.parametrize("value", ["", "   "])
def test_given_an_empty_value_then_no_request_is_sent(
    client: VerifNow, transport: FakeTransport, value: str
) -> None:
    with pytest.raises(VerifNowRequestError, match="empty"):
        client.validate_email(value)
    assert transport.requests == []


def test_given_an_unknown_rule_then_no_request_is_sent(
    client: VerifNow, transport: FakeTransport
) -> None:
    with pytest.raises(VerifNowRequestError, match="Unknown rule"):
        client.validate("passport", "X123")  # type: ignore[arg-type]
    assert transport.requests == []


# -- errors ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_given_a_rejected_key_then_auth_error_without_retry(
    client: VerifNow, transport: FakeTransport, status: int
) -> None:
    transport.reply(
        status, {"status": status, "message": "Invalid API key"}, {"X-Request-Id": "r-9"}
    )

    with pytest.raises(VerifNowAuthError) as caught:
        client.validate_email("a@b.co")

    assert caught.value.status == status
    assert caught.value.request_id == "r-9"
    assert "Invalid API key" in str(caught.value)
    assert len(transport.requests) == 1


def test_given_a_bad_request_then_request_error_without_retry(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(400, {"error": "Phone number must include a country code"})

    with pytest.raises(VerifNowRequestError, match="country code"):
        client.validate_phone("0612345678")
    assert len(transport.requests) == 1


def test_given_a_non_json_error_page_then_its_text_is_kept_short(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(502, raw=b"<html>" + b"x" * 2000 + b"</html>")

    with pytest.raises(VerifNowServerError) as caught:
        make_client(retry=None).validate_email("a@b.co")

    assert len(str(caught.value)) < 600


def test_given_a_5xx_then_it_retries_with_backoff_and_succeeds(
    client: VerifNow, transport: FakeTransport, sleeps: list[float]
) -> None:
    transport.reply(503, {"message": "down"}).reply(500).reply(body=VALID)

    result = client.validate_email("a@b.co")

    assert result.valid is True
    assert sleeps == [0.2, 0.4]


def test_given_5xx_on_every_attempt_then_server_error_after_three_requests(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(500).reply(500).reply(500)

    with pytest.raises(VerifNowServerError):
        client.validate_email("a@b.co")
    assert len(transport.requests) == 3


def test_given_retry_disabled_then_a_single_attempt(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    transport.reply(500)

    with pytest.raises(VerifNowServerError):
        make_client(retry=None).validate_email("a@b.co")
    assert len(transport.requests) == 1


def test_given_backoff_then_it_is_capped(
    make_client: Callable[..., VerifNow], transport: FakeTransport, sleeps: list[float]
) -> None:
    for _ in range(5):
        transport.reply(500)

    with pytest.raises(VerifNowServerError):
        make_client(retry=RetryPolicy(attempts=4, backoff=1, max_backoff=3)).validate_email(
            "a@b.co"
        )
    assert sleeps == [1, 2, 3, 3]


def test_given_an_unreachable_api_then_connection_error_naming_the_url(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.fail().fail().fail("Name or service not known")

    with pytest.raises(VerifNowConnectionError) as caught:
        client.validate_email("a@b.co")

    assert "https://api.verifnow.io/api/v1/validate/email" in str(caught.value)
    assert "Name or service not known" in str(caught.value)
    assert caught.value.timed_out is False
    assert len(transport.requests) == 3


def test_given_a_timeout_then_it_is_retried_and_reported_as_such(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.fail(timed_out=True).reply(body=VALID)
    assert client.validate_email("a@b.co").valid is True

    transport.fail(timed_out=True).fail(timed_out=True).fail(timed_out=True)
    with pytest.raises(VerifNowConnectionError, match="timed out after 5s") as caught:
        client.validate_email("a@b.co")
    assert caught.value.timed_out is True


def test_given_a_concurrency_429_then_it_waits_retry_after_and_retries(
    client: VerifNow, transport: FakeTransport, sleeps: list[float]
) -> None:
    transport.reply(429, {"message": "Too many requests in flight"}, {"Retry-After": "1"})
    transport.reply(body=VALID)

    assert client.validate_email("a@b.co").valid is True
    assert sleeps == [1.0]


def test_given_a_spent_monthly_quota_then_it_surfaces_at_once_with_the_quota(
    client: VerifNow, transport: FakeTransport, sleeps: list[float]
) -> None:
    reset = int((datetime.now(timezone.utc) + timedelta(days=12)).timestamp())
    transport.reply(
        429,
        {"message": "Monthly quota exceeded"},
        {"X-RateLimit-Limit": "250", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
    )

    with pytest.raises(VerifNowRateLimitError) as caught:
        client.validate_email("a@b.co")

    error = caught.value
    assert sleeps == []
    assert len(transport.requests) == 1
    assert error.quota is not None and error.quota.limit == 250 and error.quota.remaining == 0
    assert error.retry_after is not None and error.retry_after > 11 * 86400


def test_given_retry_after_as_an_http_date_then_it_is_read(
    client: VerifNow, transport: FakeTransport
) -> None:
    when = datetime.now(timezone.utc) + timedelta(hours=1)
    transport.reply(
        429, {"message": "slow down"}, {"Retry-After": format_datetime(when, usegmt=True)}
    )

    with pytest.raises(VerifNowRateLimitError) as caught:
        client.validate_email("a@b.co")

    assert caught.value.retry_after is not None
    assert 3500 < caught.value.retry_after <= 3601


def test_given_a_success_status_with_a_broken_body_then_response_error_without_retry(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(200, raw=b"<html>maintenance</html>")

    with pytest.raises(VerifNowResponseError):
        client.validate_email("a@b.co")
    assert len(transport.requests) == 1


def test_given_a_json_array_body_then_response_error(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(200, raw=b"[]")

    with pytest.raises(VerifNowResponseError, match="unexpected"):
        client.validate_email("a@b.co")


def test_given_any_failure_then_it_never_comes_back_as_a_valid_result(
    make_client: Callable[..., VerifNow], transport: FakeTransport
) -> None:
    """The Java SDK once turned every failed call into valid=true. Pin the opposite here."""
    client = make_client(retry=None)
    setups: tuple[Callable[[], object], ...] = (
        lambda: transport.fail(),
        lambda: transport.reply(500),
        lambda: transport.reply(401),
        lambda: transport.reply(429),
        lambda: transport.reply(200, raw=b""),
    )
    for setup in setups:
        setup()
        with pytest.raises(VerifNowError):
            client.validate_email("a@b.co")


# -- quota -----------------------------------------------------------------------------------------


def test_given_quota_headers_then_they_are_on_the_result(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(
        body=VALID,
        headers={
            "X-RateLimit-Limit": "10000",
            "X-RateLimit-Remaining": "9876",
            "X-RateLimit-Reset": "1798761600",
            "X-Quota-Overage": "true",
        },
    )

    quota = client.validate_email("a@b.co").quota

    assert quota is not None
    assert (quota.limit, quota.remaining, quota.overage) == (10000, 9876, True)
    assert quota.reset_at == datetime(2027, 1, 1, tzinfo=timezone.utc)


def test_given_no_quota_headers_then_quota_is_none(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(body=VALID)
    assert client.validate_email("a@b.co").quota is None


# -- VAT rates -------------------------------------------------------------------------------------

FRANCE = {
    "countryCode": "FR",
    "standardRate": 20,
    "reducedRates": [2.1, 5.5, 10],
    "regionalRates": [
        {"rate": 8.5, "note": "Martinique, Guadeloupe, Réunion", "euVatArea": False},
        {"rate": 0, "note": "Guyane", "euVatArea": False},
    ],
    "situationOn": "2026-07-01",
    "fetchedAt": "2026-11-13T03:00:00Z",
}


def test_given_vat_rates_then_every_country_is_parsed_without_spending_a_post(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(
        body={"source": "TEDB", "sourceUrl": "https://ec.europa.eu/tedb", "rates": [FRANCE]}
    )

    rates = client.vat_rates()

    assert transport.last.method == "GET"
    assert transport.last.body is None
    assert "Content-Type" not in transport.last.headers
    assert transport.last.url == "https://api.verifnow.io/api/v1/vat/rates"
    assert rates.source == "TEDB"
    assert [r.country_code for r in rates.rates] == ["FR"]


def test_given_one_country_then_its_rates_are_typed(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(body=FRANCE)

    france = client.vat_rate(" fr ")

    assert transport.last.url == "https://api.verifnow.io/api/v1/vat/rates/fr"
    assert france.standard_rate == 20.0
    assert france.reduced_rates == (2.1, 5.5, 10.0)
    assert france.regional_rates[0].eu_vat_area is False
    assert france.regional_rates[1].rate == 0.0  # zero-rated, not missing
    assert france.situation_on == "2026-07-01"
    assert france.fetched_at == datetime(2026, 11, 13, 3, tzinfo=timezone.utc)


def test_given_a_code_with_a_slash_then_it_cannot_change_the_path(
    client: VerifNow, transport: FakeTransport
) -> None:
    transport.reply(404, {"message": "Unknown member state"})

    with pytest.raises(VerifNowRequestError):
        client.vat_rate("../admin")
    assert transport.last.url == "https://api.verifnow.io/api/v1/vat/rates/..%2Fadmin"


def test_given_no_country_code_then_no_request(client: VerifNow, transport: FakeTransport) -> None:
    with pytest.raises(VerifNowRequestError):
        client.vat_rate("")
    assert transport.requests == []
