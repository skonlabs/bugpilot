CREATE TABLE IF NOT EXISTS orgs (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              TEXT NOT NULL,
    plan              TEXT NOT NULL DEFAULT 'free'
                      CHECK (plan IN ('free', 'starter', 'growth', 'enterprise')),
    -- Terms of Service
    terms_accepted    BOOLEAN NOT NULL DEFAULT FALSE,
    terms_accepted_at TIMESTAMPTZ,
    terms_version     TEXT,
    terms_cli_version TEXT,
    terms_platform    TEXT,
    -- Timestamps
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Settings (encrypted by application before storage)
    settings          JSONB NOT NULL DEFAULT '{}'
    -- settings keys: slack_webhook (enc), slack_signing_secret (enc),
    --   quiet_hours, severity_threshold[], min_confidence,
    --   blast_radius_raw_ids, investigation_retention_days
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER orgs_updated_at
  BEFORE UPDATE ON orgs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
