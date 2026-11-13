# VerifNow Python SDK

[![PyPI](https://img.shields.io/pypi/v/verifnow.svg)](https://pypi.org/project/verifnow/)
[![Python](https://img.shields.io/pypi/pyversions/verifnow.svg)](https://pypi.org/project/verifnow/)
[![CI](https://github.com/verifnowio/verifnow-python/actions/workflows/ci.yml/badge.svg)](https://github.com/verifnowio/verifnow-python/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

Official Python SDK for the [VerifNow](https://www.verifnow.io) validation API. One API key for
email, phone, IBAN, VAT (VIES), SSN, SIN and NIF validation.

Fully typed, no runtime dependencies, sync and asyncio clients.

## Install

```bash
pip install verifnow
```

Requires Python 3.10 or later.

## Getting an API key

1. Create an account at [app.verifnow.io](https://app.verifnow.io).
2. Create an API key from the dashboard.
3. Keep it server-side. It authorises calls against your quota — never ship it to a browser.

The Free plan gives you 250 validations a month with the full `STANDARD` check set, no credit card.

## Quick start

```python
from verifnow import VerifNow

client = VerifNow()  # reads the VERIFNOW_API_KEY environment variable

result = client.validate_email("user@exmaple.com")

result.valid             # False
result.message           # "Email address is unlikely to be deliverable"
result.normalized_value  # None when invalid

# Turn a typo into a correction prompt instead of a rejection
signals = result.email_details.signals if result.email_details else None
if signals and signals.typo_detected:
    print(f"Did you mean {signals.suggested_domain}?")  # "example.com"
```

Pass the key explicitly with `VerifNow("vn_...")` if you do not use the environment variable.
Create one client and share it: it holds no per-request state and is safe across threads.

## VAT and VIES

VAT is the one validator whose answer can be *unknown* rather than yes or no. Registration is
checked against VIES, the European Commission's registry, which publishes no SLA and drops member
states several times a month.

```python
result = client.validate_vat("IE6388047V")
vat = result.vat_details

vat.format_valid  # True — structural, decided locally, never depends on VIES
vat.registered    # True | False | None
vat.source        # "LIVE" | "CACHE" | "STALE" | "UNVERIFIED" | "NOT_APPLICABLE"
vat.trader_name   # "GOOGLE IRELAND LIMITED" — when the member state discloses it
```

**`registered is None` means unknown, never "not registered."** It is what you get when VIES could
not be consulted. Treating it as `False` rejects legitimate businesses during someone else's outage:

```python
if not vat.format_valid:
    return reject("That VAT number is not correctly formed.")
if vat.registered is False:
    return reject("That VAT number is not registered.")

if vat.registered is None:
    # Accept, record that it is unconfirmed, and re-check later.
    queue_for_recheck(vat_number)
    return accept(verified=False)

return accept(verified=True, stale=vat.source == "STALE")
```

Use `is False` and `is None`, not `not vat.registered`: the latter lumps the two together.

### Does the number belong to this company?

Pass the name you expect — from a supplier form, for instance — and the response says whether it
matches the registered holder:

```python
result = client.validate_vat("ESA28015865", trader_name="Telefonica")

result.vat_details.trader_name_match         # "MATCH" | "MISMATCH" | "NOT_AVAILABLE"
result.vat_details.trader_name_match_source  # "VERIFNOW" | "VIES"
```

Who compares depends on the member state. Where VIES publishes the holder's name (most of them),
VerifNow compares, ignoring case, accents, punctuation and legal forms. Spain publishes no name but
has VIES check one. Germany does neither, and the answer is `NOT_AVAILABLE` rather than a guess. A
`MISMATCH` is a question for a human, not proof of fraud.

When your account has its own VAT number configured, `vat_details.consultation_number` carries the
receipt VIES issues for the lookup: the evidence a tax authority accepts that you checked.

Per-country VIES availability is public and needs no API key:
[`GET /api/v1/status/vies`](https://www.verifnow.io/en/status).

### VAT rates

The rates of the 27 member states, retrieved daily from the Commission's
[TEDB](https://ec.europa.eu/taxation_customs/tedb/). Public reference data: these calls spend no
quota.

```python
france = client.vat_rate("FR")  # GR is accepted for Greece (EL)

france.standard_rate   # 20.0
france.reduced_rates   # (2.1, 5.5, 10.0) — which one applies depends on the product
france.regional_rates  # (RegionalVatRate(rate=8.5, note='…Martinique…', eu_vat_area=False), …)
france.situation_on    # "2026-07-01" — the date TEDB says these rates apply from
france.fetched_at      # datetime — when VerifNow last retrieved them

every_state = client.vat_rates().rates
```

`eu_vat_area=False` marks the Canary Islands and the French overseas territories, which the VAT
Directive excludes: goods shipped there from another member state are an export.

**These are the rates a member state has, not the rate an invoice carries.** In B2B trade between
member states the invoice is usually zero-rated under the reverse charge, whatever the buyer's
country rate is. Multiplying an amount by the buyer's standard rate is wrong in exactly the case a
VAT number is collected for.

## Validators

```python
client.validate_email("user@example.com")
client.validate_phone("+33612345678")           # country code required
client.validate_iban("FR7630006000011234567890189")
client.validate_vat("FR12345678901")
client.validate_nas("046454286")                # Canadian Social Insurance Number
client.validate_ssn(form["ssn"])                # US Social Security Number — never commit a real one
client.validate_nif("B12345674")                # Spanish NIF — DNI, NIE or company

# When the rule is only known at runtime
client.validate("iban", value)
```

Every call returns the same frozen `ValidationResult`:

| Field | |
|---|---|
| `valid` | `bool` |
| `message` | human-readable explanation |
| `normalized_value` | canonical form (E.164 for a phone), `None` when invalid |
| `original_value` | the value as submitted |
| `validation_level` | `"BASIC"`, `"STANDARD"`, `"ADVANCED"` or `"PREMIUM"` |
| `email_details` | email only — risk score, deliverability, signals |
| `vat_details` | VAT only — registration, source, trader name and match |
| `phone_details` | phone only — country, line type, formats |
| `iban_details` | IBAN only — structure, checksum and SEPA scope |
| `nas_details` | Canadian SIN only — temporary resident, series |
| `nif_details` | Spanish NIF only — DNI, NIE or company, legal form |
| `ssn_details` | US SSN only — whether the number is an ITIN |
| `quota` | counters from the `X-RateLimit-*` headers |
| `raw` | the untouched response body |

Enumerated values are plain strings typed with `Literal`, so your type checker knows them and a
value a newer API adds does not break parsing.

## Email signals and your plan

Email validation returns a per-signal breakdown. **Which signals are present depends on your
plan**, so branch on `applied_level` rather than assuming a field is set:

| Signal | STANDARD (Free, Starter) | ADVANCED (Growth) | PREMIUM (Pro) |
|--------|:------------------------:|:-----------------:|:-------------:|
| `syntax_valid`, `mx_valid` | ✅ | ✅ | ✅ |
| `typo_detected`, `suggested_domain` | ✅ | ✅ | ✅ |
| `role_based`, `disposable` | ✅ | ✅ | ✅ |
| `risk_score` (0–100), `deliverability` | ✅ | ✅ | ✅ |
| `free_provider`, `domain_age_days` | ❌ | ✅ | ✅ |
| `mx_provider`, `mx_quality_score` | ❌ | ✅ | ✅ |
| `risk_level` (LOW/MEDIUM/HIGH) | ❌ | ✅ | ✅ |

A signal the applied level does not compute is `None`, never `False`.

## Error handling

**This SDK raises when it cannot reach the API. It never reports an unverified value as valid.**
A validation client that swallows an outage and answers `valid=True` turns downtime into silently
accepted bad data, and you find out months later. Deciding to accept input during an outage is
reasonable — it should just be your decision, written down:

```python
from verifnow import (
    VerifNowAuthError,
    VerifNowConnectionError,
    VerifNowRateLimitError,
)

try:
    return client.validate_email(email).valid
except VerifNowAuthError:
    raise                           # misconfiguration — fix it, do not degrade
except VerifNowRateLimitError as error:
    log.warning("VerifNow quota exhausted until %s", error.quota and error.quota.reset_at)
    return True                     # deliberate: accept rather than block signups
except VerifNowConnectionError:
    log.exception("VerifNow unreachable, accepting unverified")
    return True
```

| Exception | Raised on | Retried |
|-----------|-----------|:-------:|
| `VerifNowRequestError` | 400 / 404 — malformed payload, empty value, unknown country | no |
| `VerifNowAuthError` | 401 / 403 — key missing, invalid or revoked | no |
| `VerifNowRateLimitError` | 429 — monthly quota or concurrency limit | only if the reset is imminent |
| `VerifNowServerError` | 5xx | yes |
| `VerifNowConnectionError` | DNS, TLS, refused connection, timeout | yes |
| `VerifNowResponseError` | 2xx with an unparseable body | no |

All inherit from `VerifNowError` and carry `status` and `request_id` where available — quote the
request id in a support request. `VerifNowRateLimitError` adds `quota` and `retry_after` (seconds).

## Quota

Every successful response carries the quota counters:

```python
quota = client.validate_email(email).quota

quota.remaining  # 187
quota.limit      # 250
quota.reset_at   # datetime (UTC) — start of the next billing period
quota.overage    # True once you are billed per unit
```

Paid plans are never cut off: past the included quota, extra requests are billed per unit and
`overage` flips to `True`. The Free plan blocks at its limit with a 429.

## asyncio

`AsyncVerifNow` has the same methods, awaitable:

```python
from verifnow import AsyncVerifNow

client = AsyncVerifNow()

result = await client.validate_vat("IE6388047V", trader_name="Google Ireland")
```

Each call runs in a worker thread (`asyncio.to_thread`), which keeps the SDK free of an async HTTP
dependency and never blocks your event loop, retries included.

## Configuration

```python
from verifnow import RetryPolicy, VerifNow

client = VerifNow(
    "vn_...",                              # default: the VERIFNOW_API_KEY environment variable
    base_url="https://api.verifnow.io",    # default
    timeout=5.0,                           # default, seconds, per attempt
    retry=RetryPolicy(
        attempts=2,                        # default — up to 3 requests in total
        backoff=0.2,                       # default, seconds, doubles each attempt
        max_backoff=2.0,                   # default
    ),
    headers={"X-Trace-Id": trace_id},      # added to every request
)

client.validate_email(email, timeout=1.0)  # per-call override
```

Pass `retry=None` to disable retries. The `transport` argument replaces the built-in `urllib`
transport — a callable taking an `HttpRequest` and returning an `HttpResponse` — for tests, or to
route calls through your own HTTP client.

## Validating at the edge of your app

Validate on the server, where data enters — not in the browser, which would expose your API key
and can be bypassed:

```python
# FastAPI
from fastapi import FastAPI, HTTPException
from verifnow import AsyncVerifNow, VerifNowError

app = FastAPI()
verifnow = AsyncVerifNow()

@app.post("/signup")
async def signup(email: str) -> dict[str, bool]:
    try:
        result = await verifnow.validate_email(email)
    except VerifNowError:
        await create_account(email, verified=False)  # accept rather than block the signup
        return {"ok": True}

    if not result.valid:
        signals = result.email_details.signals if result.email_details else None
        raise HTTPException(422, {
            "error": result.message,
            "suggestion": signals.suggested_domain if signals else None,
        })

    await create_account(result.normalized_value, verified=True)  # store the canonical form
    return {"ok": True}
```

## Other SDKs

- **Node.js / TypeScript**: [`@verifnow/sdk`](https://www.npmjs.com/package/@verifnow/sdk)
- **Java / Spring**: [`io.verifnow:verifnow-spring-boot-starter`](https://central.sonatype.com/artifact/io.verifnow/verifnow-spring-boot-starter)

## Documentation

- API reference and guides: [docs.verifnow.io](https://docs.verifnow.io)
- Pricing and plans: [verifnow.io/pricing](https://www.verifnow.io/en/pricing)

## License

Apache-2.0
