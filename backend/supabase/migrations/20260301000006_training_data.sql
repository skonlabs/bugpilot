CREATE TABLE IF NOT EXISTS training_data (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id           UUID NOT NULL REFERENCES orgs(id),
    investigation_id TEXT NOT NULL REFERENCES investigations(id),
    -- 8-feature vector matching FEATURE_NAMES in hypothesis_ranker.py:
    -- {recency_score, line_overlap_jaccard, semantic_diff_score, ci_failure_signal,
    --  coverage_delta, sentry_count_delta, cohort_overlap, service_risk_score}
    feature_vector   JSONB NOT NULL,
    label            SMALLINT NOT NULL CHECK (label IN (0, 1)),  -- 1=confirmed, 0=refuted
    hypothesis_rank  INTEGER NOT NULL,
    -- Weight decays over time: 0.5x after 180 days, 0.1x after 365 days
    weight           NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_train_org ON training_data(org_id);
