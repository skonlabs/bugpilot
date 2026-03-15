"""Tests for NLP classification service."""
from backend.services.nlp import classify_freeform_text


def test_extract_ticket_ref():
    result = classify_freeform_text("Investigate PROJ-1234 payments failure")
    assert result["ticket_ref"] == "PROJ-1234"


def test_extract_window_hours():
    result = classify_freeform_text("errors in the last 2 hours")
    assert result["window_hint"] == "2h"


def test_extract_window_minutes():
    result = classify_freeform_text("past 30m customers can't checkout")
    assert result["window_hint"] == "30m"


def test_extract_service():
    result = classify_freeform_text("payments service is broken")
    assert result["service_name"] == "payments"


def test_extract_keywords():
    result = classify_freeform_text("500 errors and timeouts on checkout")
    assert "500" in result["keywords"]
    assert "timeout" in result["keywords"] or "timeouts" in result["keywords"]


def test_no_match():
    result = classify_freeform_text("everything is fine")
    assert result["ticket_ref"] is None
    assert result["window_hint"] is None
