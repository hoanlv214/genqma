-- ============================================================================
-- Migration: 0012_local_postgres_alignment.sql
-- Description: Schema alignment and RPC additions for local PostgreSQL consolidation
-- Audit Reference: scratch/reports/be_context_scan_2026-10-02.md & schema audit (2026-10-02)
-- Protocol: Controlled Refactoring & Codebase Intelligence Protocol (CRCIP) Batch 3
-- Notes: Idempotent migration deliverable. Do not execute automatically.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Agent Wallets columns & UNIQUE constraint
-- ----------------------------------------------------------------------------
ALTER TABLE public.agent_wallets ADD COLUMN IF NOT EXISTS spent_usdc NUMERIC(20,6) NOT NULL DEFAULT 0;
ALTER TABLE public.agent_wallets ADD COLUMN IF NOT EXISTS spend_cap_usdc NUMERIC(20,6) NOT NULL DEFAULT 10000;
ALTER TABLE public.agent_wallets ADD COLUMN IF NOT EXISTS owner_wallet TEXT;
ALTER TABLE public.agent_wallets ADD COLUMN IF NOT EXISTS agent_wallet_id TEXT;
ALTER TABLE public.agent_wallets ADD COLUMN IF NOT EXISTS agent_wallet_address TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'agent_wallets_owner_wallet_key'
    ) THEN
        ALTER TABLE public.agent_wallets ADD CONSTRAINT agent_wallets_owner_wallet_key UNIQUE (owner_wallet);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. MCP Connections last_used_at timestamp
-- ----------------------------------------------------------------------------
ALTER TABLE public.mcp_connections ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

-- ----------------------------------------------------------------------------
-- 3. Reclaim Expired Leases RPC Function
-- Matches call site in backend/app/api/v1/endpoints/sessions.py:469
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.reclaim_expired_leases()
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE public.agent_sessions
    SET lease_owner = NULL,
        lease_expires_at = NULL,
        updated_at = NOW()
    WHERE lease_owner IS NOT NULL
      AND lease_expires_at IS NOT NULL
      AND lease_expires_at < NOW()
      AND status NOT IN ('completed', 'failed', 'stopped');

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN COALESCE(v_count, 0);
END;
$$ LANGUAGE plpgsql;
