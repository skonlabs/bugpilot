"""Basic smoke tests for the bugpilot CLI package."""
from bugpilot import __version__


def test_version_is_string():
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_format():
    parts = __version__.split(".")
    assert len(parts) == 3, f"Expected semver x.y.z, got {__version__!r}"
    assert all(p.isdigit() for p in parts), f"Non-numeric version parts in {__version__!r}"
