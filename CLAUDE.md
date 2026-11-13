# CLAUDE.md — VerifNow Python SDK

Guidance for Claude Code (claude.ai/code) when working in this repository.

Published as **`verifnow`** on PyPI, imported as `import verifnow`.

## What this package is for

It is an acquisition channel as much as a convenience. PyPI has its own search and package page,
and developers judge an API by how its SDK reads. A broken or unconvincing SDK costs more than no
SDK.

The surface covers all seven validators — email, phone, IBAN, VAT, SSN, SIN (NAS), NIF — plus the
VAT rates, because the positioning is "one key for every field your billing and onboarding forms
check". It mirrors the Node SDK (`verifnow-node`), which is the reference for behaviour.

## Non-negotiables

- **Zero runtime dependencies.** The transport is `urllib`. Anything added to `dependencies` is
  added to every user's install and audit. Dev tools go in `[dependency-groups]`.
- **Never fail open.** A failure raises; it never returns a result that looks valid. The Java SDK
  once shipped a default that failed open combined with a wrong default host: every call failed,
  then returned `valid=true`, and applications following its README validated nothing. A test pins
  this (`test_given_any_failure_then_it_never_comes_back_as_a_valid_result`).
- **`VatDetails.registered` is `None` when VIES could not answer, never `False`.** That
  distinction is the whole VAT design; do not coerce it.
- **`_version.py` is the single source of the version.** `pyproject.toml` reads it, the client
  sends it as `X-VerifNow-SDK: python/<version>`, and a test checks the CHANGELOG's first entry
  matches it.
- **Python >= 3.10.** No syntax or stdlib API newer than that (`datetime.fromisoformat` does not
  accept `Z` before 3.11, hence `parse_datetime`).
- The API key never appears in a `repr`, a message or an exception.

## Commands

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest mypy ruff build twine
.venv/bin/pytest -q            # no network: a fake transport, plus a loopback HTTP server
.venv/bin/mypy                 # strict
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m build && .venv/bin/twine check dist/*
```

## Conventions

- Tests are Given/When/Then names. A behaviour worth a comment is worth a test, and a new test
  must **fail against the previous code** before it is trusted.
- Retry policy lives in `_retry_delay`: 5xx and connection failures back off and retry; 400 and
  401 never do; a 429 is retried only when its reset is within `max_backoff`.
- Public API changes follow semver. Before 1.0.0 a minor version may break, but say so in the
  CHANGELOG.
- Parsing is lenient: a field of the wrong type becomes `None`, an unknown enum value passes
  through as a string, and `raw` keeps the body.

## Releasing

Publishing runs from GitHub Actions (`publish.yml`) through PyPI trusted publishing: no token is
stored anywhere.

1. Bump `src/verifnow/_version.py` and add the CHANGELOG entry. Commit, push, CI green.
2. Create a GitHub release whose tag is the bare version (`0.1.0`, **no `v`**, like the other
   VerifNow SDKs). Publishing the release builds, checks that the tag equals the package version,
   and uploads to PyPI after approval of the `pypi` environment.

## Related

- API: `validAPI` — the source of truth for response shapes
- Node equivalent: `verifnow-node` (`@verifnow/sdk`) — the reference implementation
- Java equivalent: `verifnow-spring`
- Docs site: `verifnow-doc` — Python snippets there must match this package's real API
