-- Fix schema gaps found during code review
-- 1. investigations.status: add 'running' (orchestrator sets this during execution)
-- 2. connectors.type: add 'confluence' and 'slack'
-- 3. connectors.status: align with code ('pending_health' not used — code fixed to use 'pending')
-- 4. triggers: add source/external_id/summary/service_name columns used by webhook handlers

-- ── 1. investigations.status ─────────────────────────────────────────────────
ALTER TABLE investigations
    DROP CONSTRAINT IF EXISTS investigations_status_check;

ALTER TABLE investigations
    ADD CONSTRAINT investigations_status_check
    CHECK (status IN (
        'queued', 'running', 'pulling', 'building_graph',
        'scoring', 'complete', 'failed', 'timeout'
    ));

-- ── 2. connectors.type ───────────────────────────────────────────────────────
ALTER TABLE connectors
    DROP CONSTRAINT IF EXISTS connectors_type_check;

ALTER TABLE connectors
    ADD CONSTRAINT connectors_type_check
    CHECK (type IN (
        'github', 'jira', 'freshdesk', 'email_imap',
        'linear', 'github_issues', 'sentry',
        'database', 'log_files',
        'datadog', 'pagerduty', 'langsmith',
        'confluence', 'slack'
    ));

-- ── 3. triggers: add columns used by webhook handlers ────────────────────────
-- The original triggers table only had: id, org_id, type, payload, status, ...
-- Webhook handlers insert: org_id, source, external_id, payload, summary, service_name, status
ALTER TABLE triggers ADD COLUMN IF NOT EXISTS source        TEXT;
ALTER TABLE triggers ADD COLUMN IF NOT EXISTS external_id  TEXT;
ALTER TABLE triggers ADD COLUMN IF NOT EXISTS summary      TEXT;
ALTER TABLE triggers ADD COLUMN IF NOT EXISTS service_name TEXT;

-- Deduplication constraint used by ON CONFLICT in _upsert_trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'triggers_org_source_external_id_unique'
    ) THEN
        ALTER TABLE triggers
            ADD CONSTRAINT triggers_org_source_external_id_unique
            UNIQUE (org_id, source, external_id);
    END IF;
END
$$;

-- Make existing type column nullable (new rows use source instead)
ALTER TABLE triggers ALTER COLUMN type DROP NOT NULL;
