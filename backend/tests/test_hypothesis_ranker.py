"""Tests for hypothesis ranker feature computation."""
from datetime import datetime, timezone, timedelta

from worker.app.hypothesis_ranker import (
    _recency_score,
    _line_overlap_jaccard,
    _ci_failure_signal,
    _coverage_delta,
    _multiplicative_score,
    FEATURE_NAMES,
)


def test_recency_score_during_window():
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    window_end = now
    # Merged during window → score = 1.0
    merged_at = (now - timedelta(minutes=30)).isoformat()
    score = _recency_score(merged_at, window_start, window_end)
    assert score == 1.0


def test_recency_score_recent():
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    window_end = now
    # Merged 2h before window start
    merged_at = (now - timedelta(hours=3)).isoformat()
    score = _recency_score(merged_at, window_start, window_end)
    assert 0 < score < 1.0


def test_recency_score_very_old():
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    window_end = now
    # Merged 30 days ago
    merged_at = (now - timedelta(days=30)).isoformat()
    score = _recency_score(merged_at, window_start, window_end)
    assert score < 0.01


def test_line_overlap_perfect():
    files = [{"filename": "payments/checkout.py"}]
    frames = ["checkout.py"]
    score = _line_overlap_jaccard(files, frames)
    assert score == 1.0


def test_line_overlap_none():
    files = [{"filename": "auth/login.py"}]
    frames = ["checkout.py"]
    score = _line_overlap_jaccard(files, frames)
    assert score == 0.0


def test_ci_failure_hotfix():
    score = _ci_failure_signal(["hotfix"], "fix payment bug")
    assert score == 1.0


def test_ci_failure_none():
    score = _ci_failure_signal(["feature"], "add dark mode")
    assert score == 0.0


def test_coverage_delta_high_deletion():
    # 80% deletions = suspicious
    score = _coverage_delta(additions=20, deletions=80)
    assert score == 0.8


def test_multiplicative_score_all_zeros():
    features = {k: 0.0 for k in FEATURE_NAMES}
    assert _multiplicative_score(features) == 0.0


def test_multiplicative_score_all_ones():
    features = {k: 1.0 for k in FEATURE_NAMES}
    score = _multiplicative_score(features)
    assert 0.9 <= score <= 1.0


def test_feature_names_count():
    assert len(FEATURE_NAMES) == 8
