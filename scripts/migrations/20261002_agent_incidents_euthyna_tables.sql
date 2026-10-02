-- ============================================================================
-- Migration: 20261002_agent_incidents_euthyna_tables.sql
-- Description: Idempotent tables for fail-closed incident and Euthyna audit persistence.
-- Deliverable for operator application; do NOT execute directly in tests.
-- ============================================================================

-- 1. Agent Incidents Table
CREATE TABLE IF NOT EXISTS public.agent_incidents (
    incident_id TEXT PRIMARY KEY,
    session_id TEXT,
    trace_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    incident JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_incidents_session_id ON public.agent_incidents (session_id);

-- 2. Euthyna Audit Trail Table
CREATE TABLE IF NOT EXISTS public.euthyna_audit_trail (
    record_id TEXT PRIMARY KEY,
    actor TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    record JSONB NOT NULL DEFAULT '{}'::jsonb,
    action TEXT,
    tx_hash TEXT,
    previous_hash TEXT,
    timestamp TEXT,
    amount_usdc NUMERIC(20, 6) DEFAULT 0.0,
    treasury_liquid_before NUMERIC(20, 6) DEFAULT 0.0,
    treasury_liquid_after NUMERIC(20, 6) DEFAULT 0.0,
    usyc_vault_shares NUMERIC(20, 6) DEFAULT 0.0,
    arcscan_url TEXT,
    policy_rule_applied TEXT,
    cfo_reasoning TEXT,
    provider_id TEXT,
    genlayer_consensus TEXT,
    integrity_hash TEXT,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_euthyna_audit_actor ON public.euthyna_audit_trail (actor);
CREATE INDEX IF NOT EXISTS idx_euthyna_audit_action ON public.euthyna_audit_trail (action);
CREATE INDEX IF NOT EXISTS idx_euthyna_audit_created ON public.euthyna_audit_trail (created_at DESC);

-- 3. Row Level Security & Service Role Grants
ALTER TABLE public.agent_incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.euthyna_audit_trail ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.agent_incidents TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.euthyna_audit_trail TO service_role;
    END IF;
END $$;
