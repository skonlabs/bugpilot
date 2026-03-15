"""
PII Scrubber — single source of truth for all PII and secret detection.

Imported by every connector's normaliser and by the worker pipeline.
DO NOT duplicate this file anywhere else in the codebase.

Usage:
    from backend.connectors._base.pii_scrubber import scrub
    clean_data = scrub(raw_data)  # works on str, dict, list — recursive
"""
from __future__ import annotations

import re

# ── Pattern definitions ────────────────────────────────────────────────────────

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL]",
    ),
    # Phone numbers (US format variants)
    (
        re.compile(
            r"\+?1?\s*[\(\-\.]?\s*\d{3}\s*[\)\-\.]?\s*\d{3}\s*[\-\.]\s*\d{4}"
        ),
        "[PHONE]",
    ),
    # Social Security Numbers
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    # JWT tokens (eyJ... three-part structure)
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
        ),
        "[JWT]",
    ),
    # AWS access key IDs
    (
        re.compile(r"\b(AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}\b"),
        "[AWS_KEY]",
    ),
    # GitHub tokens
    (
        re.compile(
            r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{36,}\b"
        ),
        "[GITHUB_TOKEN]",
    ),
    # OpenAI API keys
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "[OPENAI_KEY]"),
    # Anthropic API keys
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-]{32,}\b"), "[ANTHROPIC_KEY]"),
    # Bearer tokens in Authorization headers
    (
        re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b"),
        "Bearer [TOKEN]",
    ),
    # Database connection strings
    (
        re.compile(
            r"\b(postgresql|postgres|mysql|mongodb)://[^\s\"\']+\b"
        ),
        "[DB_URL]",
    ),
    # PEM private key blocks
    (
        re.compile(
            r"-----BEGIN[A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END[A-Z ]+ PRIVATE KEY-----"
        ),
        "[PRIVATE_KEY]",
    ),
    # Credit card candidates — validated with Luhn check below
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "__CC_CANDIDATE__"),
]


def _luhn(s: str) -> bool:
    """Validate a string of digits with the Luhn algorithm."""
    digits = [int(c) for c in s if c.isdigit()]
    if len(digits) < 13:
        return False
    total = sum(
        d * 2 - 9 if d * 2 > 9 else d * 2 if i % 2 else d
        for i, d in enumerate(reversed(digits))
    )
    return total % 10 == 0


def scrub(obj: object) -> object:
    """
    Recursively scrub PII and secrets from any string, dict, or list.
    Returns a scrubbed copy. Input is never modified.

    Covers:
    - Email addresses         → [EMAIL]
    - US phone numbers        → [PHONE]
    - SSNs                    → [SSN]
    - JWT tokens              → [JWT]
    - AWS access key IDs      → [AWS_KEY]
    - GitHub tokens           → [GITHUB_TOKEN]
    - OpenAI API keys         → [OPENAI_KEY]
    - Anthropic API keys      → [ANTHROPIC_KEY]
    - Bearer tokens           → Bearer [TOKEN]
    - Database URLs           → [DB_URL]
    - PEM private keys        → [PRIVATE_KEY]
    - Luhn-valid credit cards → [CREDIT_CARD]
    """
    if isinstance(obj, str):
        for pat, rep in _PATTERNS:
            if rep == "__CC_CANDIDATE__":
                obj = pat.sub(
                    lambda m: "[CREDIT_CARD]" if _luhn(m.group()) else m.group(),
                    obj,
                )
            else:
                obj = pat.sub(rep, obj)
        return obj
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(i) for i in obj]
    return obj
