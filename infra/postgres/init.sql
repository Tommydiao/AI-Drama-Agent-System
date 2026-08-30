-- Phase-2 target schema. Runtime Phase 1 remains SQLite behind ProjectRepository.
CREATE TABLE IF NOT EXISTS project (
  id uuid PRIMARY KEY,
  title text NOT NULL,
  premise text NOT NULL,
  production_state text NOT NULL DEFAULT 'PLANNED',
  paused_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shot (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES project(id),
  position integer NOT NULL,
  production_state text NOT NULL DEFAULT 'PLANNED',
  creative_repair_count integer NOT NULL DEFAULT 0,
  UNIQUE(project_id, position)
);

CREATE TABLE IF NOT EXISTS shot_version (
  id uuid PRIMARY KEY,
  shot_id uuid NOT NULL REFERENCES shot(id),
  version_status text NOT NULL DEFAULT 'DRAFT',
  spec_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operation (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES project(id),
  idempotency_key text NOT NULL,
  state text NOT NULL DEFAULT 'PLANNED',
  is_paid boolean NOT NULL DEFAULT false,
  no_charge_policy_fact boolean NOT NULL DEFAULT false,
  UNIQUE(project_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS budget_reservation (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES project(id),
  operation_id uuid NOT NULL REFERENCES operation(id),
  state text NOT NULL DEFAULT 'REQUESTED',
  amount_minor bigint NOT NULL,
  currency text NOT NULL,
  UNIQUE(operation_id)
);

