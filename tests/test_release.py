"""Release hygiene: the version the API sees must be the version on PyPI, and documented."""

from __future__ import annotations

import re
from pathlib import Path

from verifnow import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_given_the_version_then_it_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_given_the_version_then_the_changelog_documents_it_first() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert first is not None
    assert first.group(1) == __version__


def test_given_the_package_then_it_ships_the_typed_marker() -> None:
    assert (ROOT / "src" / "verifnow" / "py.typed").exists()
