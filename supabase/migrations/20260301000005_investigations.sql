-- Per-org sequential ID generator: "INV-001", "INV-002", etc.
CREATE SEQUENCE IF NOT EXISTS investigation_global_seq START 1;

CREATE TABLE IF NOT EXISTS investigations (
    id               TEXT PRIMARY KEY DEFAULT (
                         'INV-' || LPAD(nextval('investigation_global_seq')::TEXT, 3, '0')
                     ),
    org_id           UUID NOT NULL REFERENCES orgs(id),
    status           TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
                         'queued', 'pulling', 'building_graph', 'scoring',
                         'complete', 'failed', 'timeout'
                     )),
    layer            TEXT NOT NULL DEFAULT 'l2' CHECK (layer IN ('l1', 'l2', 'l3')),
    trigger_type     TEXT NOT NULL CHECK (trigger_type IN (
                         'jira_webhook', 'freshdesk_webhook', 'email_inbound',
                         'linear_webhook', 'github_issues_webhook', 'sentry_webhook',
                         'slack_slash_cmd', 'cli_manual', 'api', 'watch_daemon'
                     )),
    trigger_ref      TEXT,              -- "ENG-4821", "12345", "EMAIL-A1B2C3D4", "FREEFORM-XXXXXXXX"
    trigger_source   TEXT,              -- "jira", "freshdesk", "email", "sentry", "slack", "cli"
    service_name     TEXT,
    window_start     TIMESTAMPTZ,
    window_end       TIMESTAMPTZ,

    -- Top hypothesis results (denormalised for fast history queries)
    top_pr_id        TEXT,
    top_pr_url       TEXT,
    top_file         TEXT,
    top_line         INTEGER,
    top_confidence   NUMERIC(4,3),
    top_diff_type    TEXT,
    failure_class    TEXT,
    llm_narrative    TEXT,

    -- Blast radius
    blast_count      INTEGER,
    blast_value_usd  NUMERIC(12,2),
    blast_cohort     TEXT,
    blast_status     TEXT CHECK (blast_status IN ('growing', 'bounded', 'unknown')),

    -- Feedback
    feedback         TEXT CHECK (feedback IN ('confirmed', 'refuted', NULL)),
    feedback_at      TIMESTAMPTZ,
    feedback_by      TEXT,
    feedback_cause   TEXT,

    -- Timing
    queued_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    duration_ms      INTEGER,

    -- Connector tracking
    connectors_used    TEXT[],
    connectors_missing TEXT[],

    -- Error tracking
    error_message    TEXT,
    error_code       TEXT
);

CREATE INDEX IF NOT EXISTS idx_inv_org     ON investigations(org_id);
CREATE INDEX IF NOT EXISTS idx_inv_status  ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_inv_trigger ON investigations(trigger_ref);
CREATE INDEX IF NOT EXISTS idx_inv_queued  ON investigations(queued_at);
CREATE INDEX IF NOT EXISTS idx_inv_search  ON investigations USING gin(
    to_tsvector('english', COALESCE(trigger_ref,'') || ' ' || COALESCE(llm_narrative,''))
);

-- Per-step progress (polled by CLI every 2 seconds during investigation)
CREATE TABLE IF NOT EXISTS investigation_progress (
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    step             TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('pending','running','complete','error')),
    message          TEXT,
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    duration_ms      INTEGER,
    PRIMARY KEY(investigation_id, step)
);

-- Full hypotheses (all ranked candidates, not just the top one)
CREATE TABLE IF NOT EXISTS investigation_hypotheses (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    rank             INTEGER NOT NULL,
    pr_id            TEXT,
    pr_url           TEXT,
    pr_title         TEXT,
    pr_author        TEXT,
    pr_merged_at     TIMESTAMPTZ,
    file_path        TEXT,
    line_number      INTEGER,
    diff_type        TEXT,
    confidence       NUMERIC(4,3),
    feature_scores   JSONB,    -- {recency_score, line_overlap_jaccard, semantic_diff_score,
                               --  ci_failure_signal, coverage_delta, sentry_count_delta,
                               --  cohort_overlap, service_risk_score}
    evidence         JSONB,    -- [{source: "sentry", description: "..."}, ...]
    conflict_note    TEXT
);

CREATE INDEX IF NOT EXISTS idx_hyp_inv ON investigation_hypotheses(investigation_id);

-- Trigger queue (polled by bugpilot watch daemon every 5 seconds)
CREATE TABLE IF NOT EXISTS triggers (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id           UUID NOT NULL REFERENCES orgs(id),
    type             TEXT NOT NULL CHECK (type IN (
                         'jira_ticket', 'freshdesk_ticket', 'email_ticket',
                         'linear_issue', 'github_issue', 'sentry_alert',
                         'slack_slash_cmd', 'api'
                     )),
    payload          JSONB NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'processing', 'done', 'skipped')),
    investigation_id TEXT REFERENCES investigations(id),
    received_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at     TIMESTAMPTZ,
    skip_reason      TEXT        -- "quiet_hours", "below_severity", "duplicate"
);

CREATE INDEX IF NOT EXISTS idx_trig_org_pending ON triggers(org_id, status)
    WHERE status = 'pending';
