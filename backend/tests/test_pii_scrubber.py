"""Tests for PII scrubber."""
from backend.connectors._base.pii_scrubber import scrub


def test_email_scrubbed():
    assert scrub("contact user@example.com please") == "contact [EMAIL] please"


def test_github_token_scrubbed():
    text = "token ghp_abcdefghijklmnopqrstuvwxyz1234"
    result = scrub(text)
    assert "ghp_" not in result


def test_jwt_scrubbed():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.SflKxwR"
    result = scrub(f"Authorization: Bearer {jwt}")
    assert jwt not in result


def test_no_false_positives():
    text = "The quick brown fox jumps over the lazy dog"
    assert scrub(text) == text


def test_nested_dict():
    data = {"email": "user@test.com", "nested": {"token": "secret123"}}
    result = scrub(data)
    assert result["email"] == "[EMAIL]"
    # Original unchanged
    assert data["email"] == "user@test.com"


def test_list_scrubbed():
    data = ["user@example.com", "normal text"]
    result = scrub(data)
    assert result[0] == "[EMAIL]"
    assert result[1] == "normal text"
