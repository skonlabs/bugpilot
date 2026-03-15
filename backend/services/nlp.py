"""
NLP classification for freeform text investigation requests.

classify_freeform_text() extracts:
  - service_name: detected service/component name
  - window_hint: ISO8601 or relative duration string if time window mentioned
  - ticket_ref: any ticket reference pattern (e.g. PROJ-123, #4567)
  - keywords: list of extracted symptom keywords
"""
from __future__ import annotations

import re
from typing import Optional

# Ticket reference patterns: JIRA-style, Linear-style, GitHub issue
_TICKET_RE = re.compile(
    r"\b([A-Z]{2,10}-\d{1,6})\b"          # PROJ-123
    r"|\b(#\d{2,6})\b"                       # #1234
    r"|\bissue[s]?\s*#?(\d{2,6})\b",         # issue 123
    re.IGNORECASE,
)

# Duration patterns: "last 2h", "past 30m", "in the last 1 hour"
_DURATION_RE = re.compile(
    r"\b(?:last|past|in\s+the\s+last)\s+(\d+)\s*(hour[s]?|hr[s]?|h|minute[s]?|min[s]?|m)\b",
    re.IGNORECASE,
)

# Common service/component patterns: "payments service", "auth module", "checkout api"
_SERVICE_RE = re.compile(
    r"\b(\w+)\s+(?:service|module|api|microservice|worker|job|pipeline|endpoint)\b",
    re.IGNORECASE,
)


def _extract_window(text: str) -> Optional[str]:
    m = _DURATION_RE.search(text)
    if not m:
        return None
    amount = m.group(1)
    unit = m.group(2).lower()
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return f"{amount}h"
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return f"{amount}m"
    return None


def _extract_ticket(text: str) -> Optional[str]:
    m = _TICKET_RE.search(text)
    if not m:
        return None
    return next(g for g in m.groups() if g is not None)


def _extract_service(text: str) -> Optional[str]:
    m = _SERVICE_RE.search(text)
    if m:
        return m.group(1).lower()
    return None


# Symptom keywords that suggest bug category
_SYMPTOM_WORDS = {
    "error", "errors", "exception", "exceptions", "fail", "failure", "failures",
    "timeout", "timeouts", "slow", "latency", "crash", "crashes", "broken",
    "wrong", "incorrect", "bad", "invalid", "missing", "null", "undefined",
    "500", "503", "404", "401", "403", "refused", "rejected",
    "payment", "charge", "refund", "order", "cart", "checkout",
    "login", "auth", "token", "session", "signup",
}


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"\b\w+\b", text.lower())
    return [w for w in words if w in _SYMPTOM_WORDS]


def classify_freeform_text(text: str) -> dict:
    """
    Extract structured fields from freeform bug description.

    Returns dict with:
      service_name: str | None
      window_hint:  str | None   (e.g. "2h", "30m")
      ticket_ref:   str | None
      keywords:     list[str]
    """
    return {
        "service_name": _extract_service(text),
        "window_hint": _extract_window(text),
        "ticket_ref": _extract_ticket(text),
        "keywords": _extract_keywords(text),
    }
