"""Package version.

Sent to the API as ``X-VerifNow-SDK: python/<version>`` so calls made through an official SDK can be
told apart from hand-rolled integrations. ``pyproject.toml`` reads it from here, so this is the only
place to bump it.
"""

__version__ = "0.1.0"
