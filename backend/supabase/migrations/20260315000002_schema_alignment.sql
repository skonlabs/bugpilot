-- Schema alignment: fix mismatches between code and schema found during code review
-- 1. connectors.config: make nullable (credentials live in AWS Secrets Manager, not DB)
-- 2. investigations: add window_minutes column (used by queue.py INSERT + message)
-- 3. investigations: connectors_used/missing TEXT[] → JSONB (orchestrator uses json.dumps + ::jsonb)
-- 4. training_data: ensure index exists for weight-decayed queries

-- ── 1. connectors.config: drop NOT NULL ──────────────────────────────────────
-- Credentials are stored in AWS Secrets Manager.
-- The DB column is retained for potential future use (e.g. non-secret config).
ALTER TABLE connectors ALTER COLUMN config DROP NOT NULL;

-- ── 2. investigations: add window_minutes ────────────────────────────────────
-- queue.py enqueues with window_minutes; orchestrator reads it from the SQS message.
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS window_minutes INTEGER NOT NULL DEFAULT 30;

-- ── 3. investigations: connectors_used/missing TEXT[] → JSONB ────────────────
-- orchestrator.py persists: json.dumps(list) cast via ::jsonb
ALTER TABLE investigations
    ALTER COLUMN connectors_used    TYPE JSONB USING COALESCE(to_jsonb(connectors_used), '[]'::jsonb),
    ALTER COLUMN connectors_missing TYPE JSONB USING COALESCE(to_jsonb(connectors_missing), '[]'::jsonb);
