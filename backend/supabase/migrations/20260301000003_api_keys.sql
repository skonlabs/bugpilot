CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id       UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    key_hash     TEXT NOT NULL UNIQUE,  -- SHA256 hex of raw key. Raw key never stored.
    key_prefix   TEXT NOT NULL,         -- First 8 chars for display: "bp_live_"
    key_suffix   TEXT NOT NULL,         -- Last 4 chars for display
    scope        TEXT NOT NULL DEFAULT 'full'
                 CHECK (scope IN ('full', 'read_only', 'ci_only')),
    name         TEXT,                  -- User-assigned label
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ,
    created_by   TEXT                   -- Email of creator
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash)
    WHERE revoked_at IS NULL;
