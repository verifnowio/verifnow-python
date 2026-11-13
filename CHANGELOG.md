# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the package follows
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-13

### Added
- First release, at parity with the Node.js SDK 1.9.0.
- `VerifNow` and `AsyncVerifNow` clients: `validate_email`, `validate_phone`, `validate_iban`,
  `validate_vat` (with `trader_name`), `validate_nas`, `validate_ssn`, `validate_nif`, the generic
  `validate`, and `vat_rates` / `vat_rate` for the EU VAT rates from TEDB.
- Frozen, fully typed results (`py.typed`), with the untouched body on `raw`.
- Typed exceptions per failure class. The SDK never reports an unverified value as valid.
- Retries with exponential backoff for connection failures, timeouts and 5xx. A 429 is retried
  only when its reset is close; 400 and 401 never are.
- No runtime dependencies: the default transport is `urllib`, replaceable through `transport`.
- Every request sends `X-VerifNow-SDK: python/<version>`.
