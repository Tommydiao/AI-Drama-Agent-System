-- Application schema is owned exclusively by Alembic.
-- This initialization script only prepares separate Temporal databases for local integration.

SELECT 'CREATE DATABASE temporal OWNER ai_drama'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal')\gexec

SELECT 'CREATE DATABASE temporal_visibility OWNER ai_drama'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility')\gexec
