-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- AGE is enabled via Supabase Dashboard, not via SQL migration.
-- Load AGE at query time with: LOAD 'age'; SET search_path = ag_catalog, ...
-- Do not put LOAD 'age' here — it does not survive across connections.
