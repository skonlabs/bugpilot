"""
Hypothesis ranker — scores and ranks PR candidates as root cause hypotheses.

Features (8):
  1. recency_score       — how recently the PR was merged relative to window
  2. line_overlap_jaccard — Jaccard similarity of PR file lines vs error stack frames
  3. semantic_diff_score — TF-IDF cosine similarity of diff text vs error description
  4. ci_failure_signal   — whether CI failed on this PR (0 or 1)
  5. coverage_delta      — test coverage change (negative = suspicious)
  6. sentry_count_delta  — spike in Sentry error counts after merge
  7. cohort_overlap      — fraction of blast-radius cohort that touched this PR
  8. service_risk_score  — author/service historical bug rate

Scoring:
  - If fewer than 10 confirmed investigations: multiplicative scorer (product of features)
  - After 10 confirmed: BayesianRidge regressor trained on feedback labels

Model is persisted per-org in Redis as a JSON-serialized coefficient vector.
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# Feature names in fixed order
FEATURE_NAMES = [
    "recency_score",
    "line_overlap_jaccard",
    "semantic_diff_score",
    "ci_failure_signal",
    "coverage_delta",
    "sentry_count_delta",
    "cohort_overlap",
    "service_risk_score",
]


# ── Feature computation ────────────────────────────────────────────────────────

def _recency_score(merged_at: Optional[str], window_start: datetime, window_end: datetime) -> float:
    """Inverse of age: PRs merged just before window get highest score."""
    if not merged_at:
        return 0.0
    try:
        merged = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        if merged.tzinfo is None:
            merged = merged.replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0

    window_size = (window_end - window_start).total_seconds()
    if window_size <= 0:
        return 0.0

    # Time from window_start to merge (if before window, score decreases with age)
    age_secs = (window_start - merged).total_seconds()
    if age_secs < 0:
        # Merged during window
        return 1.0

    # Exponential decay: half-life = window_size * 3
    half_life = window_size * 3
    return math.exp(-math.log(2) * age_secs / half_life)


def _line_overlap_jaccard(pr_files: list[dict], error_frames: list[str]) -> float:
    """Jaccard similarity between PR-modified file paths and error stack frame paths."""
    if not pr_files or not error_frames:
        return 0.0

    pr_paths = {f.get("filename", "").lower() for f in pr_files if f.get("filename")}
    frame_paths = set()
    for frame in error_frames:
        # Normalise frame to filename portion
        parts = re.split(r"[\\/]", frame)
        for p in parts:
            if "." in p:
                frame_paths.add(p.lower())

    if not pr_paths or not frame_paths:
        return 0.0

    intersection = pr_paths & frame_paths
    union = pr_paths | frame_paths
    return len(intersection) / len(union)


def _semantic_diff_score(pr_diff_text: str, error_description: str) -> float:
    """TF-IDF cosine similarity between PR diff and error description."""
    if not pr_diff_text or not error_description:
        return 0.0

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        texts = [pr_diff_text[:5000], error_description[:2000]]
        tfidf = vectorizer.fit_transform(texts)
        sim = cosine_similarity(tfidf[0], tfidf[1])[0][0]
        return float(sim)
    except Exception as e:
        log.debug(f"TF-IDF error: {e}")
        return 0.0


def _ci_failure_signal(pr_labels: list[str], pr_title: str) -> float:
    """1.0 if PR has CI failure indicators, 0.0 otherwise."""
    signals = ["ci-fail", "test-fail", "broken", "revert", "hotfix", "rollback"]
    combined = " ".join(pr_labels + [pr_title]).lower()
    return 1.0 if any(s in combined for s in signals) else 0.0


def _coverage_delta(pr_additions: int, pr_deletions: int) -> float:
    """
    Proxy coverage delta: large deletions relative to additions suggests
    test removal. Returns 0.0 (good) to 1.0 (suspicious).
    """
    total = pr_additions + pr_deletions
    if total == 0:
        return 0.0
    deletion_ratio = pr_deletions / total
    return deletion_ratio


def _sentry_count_delta(sentry_events: list[dict], merged_at: Optional[str]) -> float:
    """
    Compare error count in 1h before vs 1h after PR merge.
    Returns 0.0–1.0 normalised spike score.
    """
    if not sentry_events or not merged_at:
        return 0.0

    try:
        merge_time = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        if merge_time.tzinfo is None:
            merge_time = merge_time.replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0

    before_count = 0
    after_count = 0
    for ev in sentry_events:
        ts_str = ev.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        delta = (ts - merge_time).total_seconds()
        count = int(ev.get("count", 1))
        if -3600 <= delta < 0:
            before_count += count
        elif 0 <= delta <= 3600:
            after_count += count

    if before_count == 0 and after_count == 0:
        return 0.0
    if before_count == 0:
        return min(1.0, after_count / 10)  # spike from zero
    ratio = after_count / (before_count + 1)
    return min(1.0, (ratio - 1.0) / 9.0) if ratio > 1.0 else 0.0


def _cohort_overlap(blast_user_ids: list[str], pr_author: str) -> float:
    """
    Placeholder: fraction of blast-radius cohort that touched this PR.
    Real implementation would check PR review participants.
    """
    # For now: 0.3 if blast radius is non-empty (data available)
    return 0.3 if blast_user_ids else 0.0


def _service_risk_score(conn, org_id: str, pr_author: str) -> float:
    """Author historical bug rate from AGE graph."""
    try:
        from backend.worker.graph_builder import get_author_risk_score
        return get_author_risk_score(conn, org_id, pr_author)
    except Exception:
        return 0.5


# ── Model loading/saving ───────────────────────────────────────────────────────

def _model_key(org_id: str) -> str:
    return f"model:{org_id}:bayesian_ridge"


def _load_model(redis_client, org_id: str):
    """Load BayesianRidge model coefficients from Redis, or return None."""
    try:
        data = redis_client.get(_model_key(org_id))
        if not data:
            return None
        d = json.loads(data)
        from sklearn.linear_model import BayesianRidge
        model = BayesianRidge()
        model.coef_ = np.array(d["coef"])
        model.alpha_ = d["alpha"]
        model.lambda_ = d["lambda"]
        model.intercept_ = d.get("intercept", 0.0)
        # sklearn requires these to be set for predict
        model.sigma_ = np.eye(len(d["coef"])) * d.get("sigma_scale", 1.0)
        return model
    except Exception as e:
        log.warning(f"Model load error: {e}")
        return None


def _save_model(redis_client, org_id: str, model) -> None:
    try:
        data = {
            "coef": model.coef_.tolist(),
            "alpha": float(model.alpha_),
            "lambda": float(model.lambda_),
            "intercept": float(model.intercept_),
        }
        redis_client.setex(_model_key(org_id), 86400 * 7, json.dumps(data))
    except Exception as e:
        log.warning(f"Model save error: {e}")


def _confirmed_count(conn, org_id: str) -> int:
    """Count confirmed investigations used for training."""
    try:
        from backend.database import set_org_context
        set_org_context(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM training_data WHERE org_id = %s AND label = 1",
                (org_id,),
            )
            row = cur.fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _multiplicative_score(features: dict[str, float]) -> float:
    """
    Multiplicative baseline scorer used before 10 confirmed investigations.
    Weights are hand-tuned priors.
    """
    weights = {
        "recency_score": 0.30,
        "line_overlap_jaccard": 0.25,
        "semantic_diff_score": 0.20,
        "ci_failure_signal": 0.10,
        "coverage_delta": 0.05,
        "sentry_count_delta": 0.05,
        "cohort_overlap": 0.03,
        "service_risk_score": 0.02,
    }
    score = sum(weights.get(k, 0.0) * v for k, v in features.items())
    return min(1.0, max(0.0, score))


# ── Main ranker ────────────────────────────────────────────────────────────────

def rank_hypotheses(
    org_id: str,
    pr_events: list[dict],
    ticket_events: list[dict],
    sentry_events: list[dict],
    blast_user_ids: list[str],
    window_start: datetime,
    window_end: datetime,
    db_conn,
    redis_client,
    limit: int = 5,
) -> list[dict]:
    """
    Score all PR candidates and return top `limit` ranked hypotheses.

    Each hypothesis dict:
      rank, pr_id, pr_url, pr_title, pr_author, pr_merged_at,
      file_path, line_number, diff_type, confidence, feature_scores, evidence
    """
    if not pr_events:
        return []

    # Extract error description from ticket/sentry events
    descriptions = []
    error_frames = []
    for ev in ticket_events:
        descriptions.append(ev.get("title", "") + " " + ev.get("description", ""))
    for ev in sentry_events:
        descriptions.append(ev.get("title", ""))
        culprit = ev.get("culprit", "")
        if culprit:
            error_frames.append(culprit)
    error_description = " ".join(descriptions)[:5000]

    # Determine scoring strategy
    confirmed = _confirmed_count(db_conn, org_id)
    use_bayesian = confirmed >= 10
    model = _load_model(redis_client, org_id) if use_bayesian else None

    scored = []
    for pr in pr_events:
        # Build PR diff text from files
        diff_text = " ".join(
            f.get("patch", "") for f in pr.get("files", [])
        )

        features = {
            "recency_score": _recency_score(
                pr.get("pr_merged_at"), window_start, window_end
            ),
            "line_overlap_jaccard": _line_overlap_jaccard(
                pr.get("files", []), error_frames
            ),
            "semantic_diff_score": _semantic_diff_score(diff_text, error_description),
            "ci_failure_signal": _ci_failure_signal(
                pr.get("labels", []), pr.get("pr_title", "")
            ),
            "coverage_delta": _coverage_delta(
                pr.get("additions", 0), pr.get("deletions", 0)
            ),
            "sentry_count_delta": _sentry_count_delta(
                sentry_events, pr.get("pr_merged_at")
            ),
            "cohort_overlap": _cohort_overlap(blast_user_ids, pr.get("pr_author", "")),
            "service_risk_score": _service_risk_score(
                db_conn, org_id, pr.get("pr_author", "")
            ),
        }

        if use_bayesian and model is not None:
            try:
                feature_vec = np.array([[features[k] for k in FEATURE_NAMES]])
                confidence = float(model.predict(feature_vec)[0])
                confidence = min(1.0, max(0.0, confidence))
            except Exception:
                confidence = _multiplicative_score(features)
        else:
            confidence = _multiplicative_score(features)

        # Pick the most-modified file as the hypothesis "location"
        files = pr.get("files", [])
        top_file = max(files, key=lambda f: f.get("additions", 0) + f.get("deletions", 0)) if files else {}

        scored.append({
            "pr_id": pr.get("pr_id"),
            "pr_url": pr.get("pr_url"),
            "pr_title": pr.get("pr_title"),
            "pr_author": pr.get("pr_author"),
            "pr_merged_at": pr.get("pr_merged_at"),
            "file_path": top_file.get("filename"),
            "line_number": None,
            "diff_type": top_file.get("status", "modified"),
            "confidence": round(confidence, 4),
            "feature_scores": features,
            "evidence": {
                "diff_snippet": diff_text[:500],
                "sentry_title": sentry_events[0].get("title") if sentry_events else None,
            },
            "conflict_note": None,
        })

    # Sort by confidence descending
    scored.sort(key=lambda h: h["confidence"], reverse=True)

    # Add rank
    for i, h in enumerate(scored[:limit]):
        h["rank"] = i + 1

    return scored[:limit]


def train_model(org_id: str, db_conn, redis_client) -> None:
    """
    Retrain BayesianRidge from confirmed/refuted training_data rows.
    Called asynchronously after feedback is recorded.
    """
    from backend.database import set_org_context
    set_org_context(db_conn, org_id)

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT feature_vector, label, weight FROM training_data WHERE org_id = %s",
            (org_id,),
        )
        rows = cur.fetchall()

    if len(rows) < 10:
        return  # not enough data

    X = []
    y = []
    w = []
    for fv, label, weight in rows:
        features = fv if isinstance(fv, dict) else json.loads(fv)
        X.append([features.get(k, 0.0) for k in FEATURE_NAMES])
        y.append(int(label))
        w.append(float(weight))

    X = np.array(X)
    y = np.array(y)
    w = np.array(w)

    from sklearn.linear_model import BayesianRidge
    model = BayesianRidge()
    model.fit(X, y, sample_weight=w)
    _save_model(redis_client, org_id, model)
    log.info(f"BayesianRidge retrained for org {org_id} on {len(rows)} samples")
