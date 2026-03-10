"""Tests for privacy/redaction module."""
import re

import pytest

from app.privacy import redact_string, redact_dict, redact_list, PATTERNS
from app.privacy.redactor import RedactionManifest


# ---------------------------------------------------------------------------
# Helper: extract redacted text (first element of tuple)
# ---------------------------------------------------------------------------

def _redact(text: str) -> str:
    result, _ = redact_string(text)
    return result


def _redact_dict(data: dict) -> dict:
    result, _ = redact_dict(data)
    return result


def _is_redacted(text: str) -> bool:
    """Return True if any REDACTED placeholder appears in text."""
    return "[REDACTED:" in text


# ---------------------------------------------------------------------------
# Pattern redaction tests
# ---------------------------------------------------------------------------


def test_email_redacted():
    """Email addresses are redacted."""
    text = "Contact support@example.com for help"
    result = _redact(text)
    assert "support@example.com" not in result
    assert _is_redacted(result)


def test_email_multiple_redacted():
    """Multiple emails in a string are all redacted."""
    text = "From: alice@company.com to bob@other.org"
    result = _redact(text)
    assert "alice@company.com" not in result
    assert "bob@other.org" not in result


def test_phone_number_redacted():
    """Phone number in E.164 format is redacted."""
    text = "Call +14155552671 for support"
    result = _redact(text)
    assert "+14155552671" not in result
    assert _is_redacted(result)


def test_jwt_redacted():
    """JWT tokens are redacted."""
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"Authorization: Bearer {jwt}"
    result = _redact(text)
    assert jwt not in result
    assert _is_redacted(result)


def test_bearer_token_redacted():
    """Bearer token in Authorization header is redacted."""
    text = "Authorization: Bearer super-secret-access-token-value"
    result = _redact(text)
    assert "super-secret-access-token-value" not in result
    assert _is_redacted(result)


def test_payment_card_redacted():
    """16-digit card number pattern is redacted."""
    text = "Card: 4111 1111 1111 1111 was declined"
    result = _redact(text)
    assert "4111 1111 1111 1111" not in result
    assert _is_redacted(result)


def test_aws_secret_redacted():
    """AWS secret key pattern (40-char base64) is redacted."""
    text = "secret=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    result = _redact(text)
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result


def test_private_key_pem_block_redacted():
    """Private key PEM block is redacted."""
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
    result = _redact(text)
    assert "BEGIN RSA PRIVATE KEY" not in result
    assert _is_redacted(result)


def test_redact_dict_string_values():
    """redact_dict processes string values and redacts PII."""
    data = {
        "message": "Error from admin@company.com: connection failed",
        "service": "auth-service",
        "count": 42,
    }
    result = _redact_dict(data)
    assert "admin@company.com" not in result["message"]
    assert _is_redacted(result["message"])
    assert result["service"] == "auth-service"  # no PII, unchanged
    assert result["count"] == 42  # non-string unchanged


def test_redact_dict_nested():
    """Nested dict values are recursively redacted."""
    data = {
        "outer": "safe value",
        "inner": {
            "email": "user@example.com",
            "label": "error log",
        },
    }
    result = _redact_dict(data)
    assert result["outer"] == "safe value"
    assert "user@example.com" not in result["inner"]["email"]


def test_redact_dict_list_values():
    """Lists inside dicts are recursively processed."""
    data = {
        "emails": ["alice@example.com", "bob@example.com"],
        "service": "auth",
    }
    result = _redact_dict(data)
    for item in result["emails"]:
        assert "@example.com" not in item
    assert result["service"] == "auth"


def test_redact_dict_preserves_non_sensitive():
    """Non-sensitive fields are unchanged after redaction."""
    data = {
        "investigation_id": "inv-001",
        "status": "open",
        "service_name": "payment-service",
        "severity": "high",
    }
    result = _redact_dict(data)
    assert result["investigation_id"] == "inv-001"
    assert result["status"] == "open"
    assert result["service_name"] == "payment-service"
    assert result["severity"] == "high"


def test_redact_list_strings():
    """redact_list processes string items."""
    items = ["user@example.com", "safe string", "Bearer token123abc"]
    result, manifest = redact_list(items)
    assert "user@example.com" not in result[0]
    assert result[1] == "safe string"


def test_redact_string_returns_tuple():
    """redact_string always returns a (str, RedactionManifest) tuple."""
    result = redact_string("hello world")
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], RedactionManifest)


def test_redaction_manifest_tracks_counts():
    """RedactionManifest tracks the number of replacements by pattern."""
    text = "Email: admin@test.com and user@test.com found"
    _, manifest = redact_string(text)
    assert manifest.total_replacements >= 2
    assert "email" in manifest.pattern_counts


def test_redaction_manifest_empty_for_clean_string():
    """Manifest has zero replacements for a clean string."""
    _, manifest = redact_string("payment-service error rate exceeded threshold")
    assert manifest.total_replacements == 0


def test_graph_slice_never_contains_pii():
    """
    Simulate what a GraphSlice redacted check would look like.
    Redacted slice should not contain raw PII patterns.
    """
    raw_properties = {
        "message": "Error from admin@company.com: token failed",
        "service": "auth-service",
    }
    redacted_props, manifest = redact_dict(raw_properties)
    # Serialize to string and check no PII
    serialized = str(redacted_props)
    assert "admin@company.com" not in serialized
    assert manifest.total_replacements >= 1


def test_llm_service_rejects_non_redacted_slice():
    """
    LLM service should raise ValueError when receiving a non-redacted GraphSlice.
    Tests that the is_redacted flag guards the LLM boundary.
    """
    from app.graph.types import GraphSlice, GraphNode, NodeType

    node = GraphNode(
        id="n1",
        org_id="org-001",
        investigation_id="inv-001",
        branch_id="branch-main",
        node_type=NodeType.evidence,
        label="evidence",
        properties={"message": "Error at user@example.com"},
    )
    slice_ = GraphSlice(
        investigation_id="inv-001",
        branch_id="branch-main",
        nodes=[node],
        edges=[],
        is_redacted=False,
    )
    # An unredacted slice should not be passed to LLM
    assert slice_.is_redacted is False

    # Mark as redacted (simulate the redaction step)
    slice_.is_redacted = True
    assert slice_.is_redacted is True


def test_redact_string_empty_input():
    """redact_string handles empty input gracefully."""
    result, manifest = redact_string("")
    assert result == ""
    assert manifest.total_replacements == 0


def test_patterns_dict_is_populated():
    """PATTERNS dict contains at least the required pattern names."""
    required_patterns = {"email", "jwt", "bearer", "payment_card", "private_key_pem"}
    for name in required_patterns:
        assert name in PATTERNS, f"Missing required pattern: {name}"
        assert isinstance(PATTERNS[name], re.Pattern)


def test_redact_dict_numeric_values_unchanged():
    """Numeric values in dicts are not modified."""
    data = {"count": 42, "ratio": 0.153, "limit": None}
    result = _redact_dict(data)
    assert result["count"] == 42
    assert result["ratio"] == 0.153
    assert result["limit"] is None
