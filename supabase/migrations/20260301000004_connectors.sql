CREATE TABLE IF NOT EXISTS connectors (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id            UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    type              TEXT NOT NULL CHECK (type IN (
                          'github', 'jira', 'freshdesk', 'email_imap',
                          'linear', 'github_issues', 'sentry',
                          'database', 'log_files',
                          'datadog', 'pagerduty', 'langsmith'
                      )),
    -- name: required, used in CLI output and reports. Supports multiple instances per type.
    name              TEXT NOT NULL DEFAULT 'default',
    -- service_map: maps service names to relevant resources (repos, tables, etc.)
    service_map       JSONB NOT NULL DEFAULT '{}',
    -- role: for database connector only
    role              TEXT CHECK (role IN ('blast_radius', 'error_log_table', 'both')),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                          'pending', 'healthy', 'degraded', 'error', 'disconnected'
                      )),
    -- config: AES-256-GCM encrypted JSON blob
    -- Per connector type, config JSON contains:
    -- github:     {installation_id, app_id, primary_repos[], monorepo_service_map{},
    --              index_status, last_indexed_at}
    -- jira:       {url, email, api_token(enc), projects[], webhook_id, webhook_secret(enc)}
    -- freshdesk:  {subdomain, api_key(enc), webhook_secret(enc)}
    -- email_imap: {host, port, email, password(enc), folder, keywords[], last_uid}
    -- sentry:     {org_slug, auth_token(enc), projects[], webhook_secrets{project:secret(enc)}}
    -- database:   {host, port, database, user, password(enc), tables[], ssl_mode,
    --              role, error_log_table{table, columns{timestamp,level,service,message,
    --              stack_trace,request_id}, level_filter[]}}
    -- log_files:  {type(ssh|local), host, user, ssh_key_path, log_paths[], format,
    --              json_fields{timestamp,level,service,message,stack_trace,request_id},
    --              level_filter[], window_hours}
    config            BYTEA NOT NULL,
    last_health_check TIMESTAMPTZ,
    health_details    JSONB,            -- {connector_version, latency_ms, rate_limit_remaining}
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- CRITICAL: supports multiple connectors of same type (different names)
    CONSTRAINT connectors_org_type_name_unique UNIQUE(org_id, type, name)
);

CREATE TRIGGER connectors_updated_at
  BEFORE UPDATE ON connectors FOR EACH ROW EXECUTE FUNCTION update_updated_at();
