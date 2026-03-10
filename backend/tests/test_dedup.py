"""Tests for investigation deduplication logic."""
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Minimal dedup implementation to test against
# ---------------------------------------------------------------------------
# These types and functions model the dedup contract as described in the spec.
# Replace with actual imports when the dedup module is implemented.

@dataclass
class DedupScore:
    """Weighted similarity score between two investigations."""
    service_score: float      # weight: 0.40
    symptom_score: float      # weight: 0.30
    timewindow_score: float   # weight: 0.20
    description_score: float  # weight: 0.10
    total: float = field(init=False)

    def __post_init__(self):
        self.total = (
            self.service_score * 0.40
            + self.symptom_score * 0.30
            + self.timewindow_score * 0.20
            + self.description_score * 0.10
        )


@dataclass
class InvestigationSummary:
    """Minimal investigation summary for dedup comparison."""
    id: str
    service_name: str
    symptoms: List[str]
    description: str
    occurred_at: datetime
    org_id: str = "org-001"


@dataclass
class DedupResult:
    """Result of a dedup check."""
    is_duplicate: bool
    score: DedupScore
    canonical_id: Optional[str] = None  # ID of the existing (canonical) investigation
    duplicate_id: Optional[str] = None  # ID of the new (duplicate) investigation


DEDUP_THRESHOLD = 0.75


def _jaccard_similarity(a: List[str], b: List[str]) -> float:
    """Jaccard similarity coefficient between two lists treated as sets."""
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _token_overlap(a: str, b: str) -> float:
    """Simple token overlap similarity between two strings."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _time_window_score(a: datetime, b: datetime, window_seconds: int = 3600) -> float:
    """Score 1.0 if within window, declining linearly to 0.0 at 2x window."""
    diff = abs((a - b).total_seconds())
    if diff <= window_seconds:
        return 1.0
    if diff >= window_seconds * 2:
        return 0.0
    return 1.0 - (diff - window_seconds) / window_seconds


def compute_dedup_score(a: InvestigationSummary, b: InvestigationSummary) -> DedupScore:
    """Compute weighted dedup score between two investigations."""
    service_score = 1.0 if a.service_name == b.service_name else 0.0
    symptom_score = _jaccard_similarity(a.symptoms, b.symptoms)
    timewindow_score = _time_window_score(a.occurred_at, b.occurred_at)
    description_score = _token_overlap(a.description, b.description)

    return DedupScore(
        service_score=service_score,
        symptom_score=symptom_score,
        timewindow_score=timewindow_score,
        description_score=description_score,
    )


def check_duplicate(
    candidate: InvestigationSummary,
    existing: InvestigationSummary,
    threshold: float = DEDUP_THRESHOLD,
) -> DedupResult:
    """Return a DedupResult indicating if candidate duplicates existing."""
    score = compute_dedup_score(candidate, existing)
    is_dup = score.total >= threshold
    return DedupResult(
        is_duplicate=is_dup,
        score=score,
        canonical_id=existing.id if is_dup else None,
        duplicate_id=candidate.id if is_dup else None,
    )


def merge_investigations(
    canonical: InvestigationSummary,
    duplicate: InvestigationSummary,
) -> Dict:
    """Merge duplicate into canonical, preserving both IDs."""
    return {
        "canonical_id": canonical.id,
        "merged_ids": [canonical.id, duplicate.id],
        "service_name": canonical.service_name,
        "description": canonical.description,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


NOW = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)


def test_score_calculation_weighted_correctly():
    """Score is computed with exact 40/30/20/10 weights."""
    score = DedupScore(
        service_score=1.0,
        symptom_score=1.0,
        timewindow_score=1.0,
        description_score=1.0,
    )
    assert score.total == pytest.approx(1.0)


def test_score_weights_40_30_20_10():
    """Verify each component's weight contribution."""
    # Only service matches (weight 0.40)
    s1 = DedupScore(service_score=1.0, symptom_score=0.0, timewindow_score=0.0, description_score=0.0)
    assert s1.total == pytest.approx(0.40)

    # Only symptom matches (weight 0.30)
    s2 = DedupScore(service_score=0.0, symptom_score=1.0, timewindow_score=0.0, description_score=0.0)
    assert s2.total == pytest.approx(0.30)

    # Only time window matches (weight 0.20)
    s3 = DedupScore(service_score=0.0, symptom_score=0.0, timewindow_score=1.0, description_score=0.0)
    assert s3.total == pytest.approx(0.20)

    # Only description matches (weight 0.10)
    s4 = DedupScore(service_score=0.0, symptom_score=0.0, timewindow_score=0.0, description_score=1.0)
    assert s4.total == pytest.approx(0.10)


def test_above_threshold_flagged_as_duplicate():
    """Investigations that score above threshold are flagged as duplicates."""
    inv_a = InvestigationSummary(
        id="inv-001",
        service_name="payment-service",
        symptoms=["high_error_rate", "slow_response"],
        description="Payment service returning 500 errors",
        occurred_at=NOW,
    )
    inv_b = InvestigationSummary(
        id="inv-002",
        service_name="payment-service",
        symptoms=["high_error_rate", "slow_response"],
        description="Payment service 500 errors detected",
        occurred_at=NOW,
    )
    result = check_duplicate(inv_b, inv_a)
    assert result.is_duplicate is True
    assert result.score.total >= DEDUP_THRESHOLD
    assert result.canonical_id == "inv-001"
    assert result.duplicate_id == "inv-002"


def test_below_threshold_not_flagged():
    """Investigations that score below threshold are not flagged as duplicates."""
    inv_a = InvestigationSummary(
        id="inv-001",
        service_name="payment-service",
        symptoms=["high_error_rate"],
        description="Payment service errors",
        occurred_at=NOW,
    )
    inv_b = InvestigationSummary(
        id="inv-003",
        service_name="auth-service",  # different service
        symptoms=["login_failures"],  # different symptoms
        description="Users unable to log in",  # different description
        occurred_at=NOW,
    )
    result = check_duplicate(inv_b, inv_a)
    assert result.is_duplicate is False
    assert result.score.total < DEDUP_THRESHOLD
    assert result.canonical_id is None
    assert result.duplicate_id is None


def test_merge_preserves_both_investigation_ids():
    """Merge operation includes both canonical and duplicate IDs."""
    canonical = InvestigationSummary(
        id="inv-canonical",
        service_name="payment-service",
        symptoms=["error"],
        description="Original investigation",
        occurred_at=NOW,
    )
    duplicate = InvestigationSummary(
        id="inv-duplicate",
        service_name="payment-service",
        symptoms=["error"],
        description="Duplicate investigation",
        occurred_at=NOW,
    )
    merged = merge_investigations(canonical, duplicate)
    assert merged["canonical_id"] == "inv-canonical"
    assert "inv-canonical" in merged["merged_ids"]
    assert "inv-duplicate" in merged["merged_ids"]
    assert len(merged["merged_ids"]) == 2


def test_different_service_reduces_score():
    """Different service names reduce the score significantly."""
    inv_a = InvestigationSummary(
        id="inv-001",
        service_name="payment-service",
        symptoms=["high_error_rate"],
        description="High error rate",
        occurred_at=NOW,
    )
    inv_b = InvestigationSummary(
        id="inv-002",
        service_name="auth-service",
        symptoms=["high_error_rate"],
        description="High error rate",
        occurred_at=NOW,
    )
    score = compute_dedup_score(inv_a, inv_b)
    assert score.service_score == 0.0
    # Even with matching symptoms/description/time, total should be < threshold
    assert score.total < DEDUP_THRESHOLD


def test_time_window_score_within_window():
    """Events within 1 hour window get max time score."""
    from datetime import timedelta
    a = NOW
    b = NOW + timedelta(minutes=30)
    score = _time_window_score(a, b)
    assert score == pytest.approx(1.0)


def test_time_window_score_outside_window():
    """Events far outside window get zero time score."""
    from datetime import timedelta
    a = NOW
    b = NOW + timedelta(hours=3)
    score = _time_window_score(a, b)
    assert score == pytest.approx(0.0)


def test_jaccard_empty_symptoms():
    """Both empty symptom lists produce similarity of 1.0."""
    assert _jaccard_similarity([], []) == pytest.approx(1.0)


def test_jaccard_no_overlap():
    """No common symptoms produce similarity of 0.0."""
    assert _jaccard_similarity(["a", "b"], ["c", "d"]) == pytest.approx(0.0)


def test_jaccard_full_overlap():
    """Identical symptom sets produce similarity of 1.0."""
    assert _jaccard_similarity(["a", "b"], ["a", "b"]) == pytest.approx(1.0)


def test_partial_symptom_overlap():
    """Partial symptom overlap produces a score between 0 and 1."""
    score = _jaccard_similarity(["high_error_rate", "slow_response", "timeout"],
                                 ["high_error_rate", "timeout"])
    assert 0.0 < score < 1.0
