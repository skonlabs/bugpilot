-- Enable RLS on every table
ALTER TABLE orgs                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE connectors               ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigations           ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation_progress   ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation_hypotheses ENABLE ROW LEVEL SECURITY;
ALTER TABLE triggers                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_data            ENABLE ROW LEVEL SECURITY;

-- RLS policy: all tables scoped to app.current_org_id
-- The backend sets this with: SET LOCAL app.current_org_id = '<uuid>';
-- (see backend/app/auth.py middleware)

CREATE POLICY org_isolation_orgs ON orgs
    USING (id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY org_isolation_api_keys ON api_keys
    USING (org_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY org_isolation_connectors ON connectors
    USING (org_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY org_isolation_investigations ON investigations
    USING (org_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY org_isolation_progress ON investigation_progress
    USING (investigation_id IN (
        SELECT id FROM investigations
        WHERE org_id = current_setting('app.current_org_id', true)::uuid
    ));

CREATE POLICY org_isolation_hypotheses ON investigation_hypotheses
    USING (investigation_id IN (
        SELECT id FROM investigations
        WHERE org_id = current_setting('app.current_org_id', true)::uuid
    ));

CREATE POLICY org_isolation_triggers ON triggers
    USING (org_id = current_setting('app.current_org_id', true)::uuid);

CREATE POLICY org_isolation_training ON training_data
    USING (org_id = current_setting('app.current_org_id', true)::uuid);
