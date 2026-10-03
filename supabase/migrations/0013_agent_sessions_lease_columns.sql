-- 0013: Align local agent_sessions schema with the lease/checkpoint RPCs.
-- The lease functions (0002) reference heartbeat_at, state_version and
-- last_checkpoint_at; the local PostgreSQL copy of agent_sessions drifted and
-- missed them, so every acquire-lease call failed with "column does not exist"
-- and the worker silently never picked up queued sessions.

ALTER TABLE public.agent_sessions
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

ALTER TABLE public.agent_sessions
    ADD COLUMN IF NOT EXISTS state_version INT NOT NULL DEFAULT 1;

ALTER TABLE public.agent_sessions
    ADD COLUMN IF NOT EXISTS last_checkpoint_at TIMESTAMPTZ;

-- Canonical default per 0002_agent_runtime.sql.
ALTER TABLE public.agent_sessions
    ALTER COLUMN run_generation SET DEFAULT 1;
