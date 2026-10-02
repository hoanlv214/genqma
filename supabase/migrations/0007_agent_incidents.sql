-- ============================================================================
-- Migration: 0007_agent_incidents.sql
-- Description: Autonomous Agent Safety Incident Engine & Circuit Breaker storage.
-- Replaces root agent_incidents.json with a hardened PostgreSQL table.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.agent_incidents (
    incident_id TEXT PRIMARY KEY,
    session_id TEXT,
    trace_id TEXT,
    severity TEXT NOT NULL DEFAULT 'P3_INFO',
    status TEXT NOT NULL DEFAULT 'OPEN',
    category TEXT,
    rule TEXT,
    details TEXT,
    financial_context JSONB DEFAULT '{}'::jsonb,
    actor_type TEXT DEFAULT 'SYSTEM_CIRCUIT_BREAKER',
    actor_address TEXT,
    euthyna_hash TEXT,
    admin_note TEXT,
    incident JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_incidents_status ON public.agent_incidents (status);
CREATE INDEX IF NOT EXISTS idx_agent_incidents_severity ON public.agent_incidents (severity);
CREATE INDEX IF NOT EXISTS idx_agent_incidents_session ON public.agent_incidents (session_id);
CREATE INDEX IF NOT EXISTS idx_agent_incidents_created ON public.agent_incidents (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_incidents_rule ON public.agent_incidents (rule);

ALTER TABLE public.agent_incidents ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_incidents TO service_role;
    END IF;
END $$;
