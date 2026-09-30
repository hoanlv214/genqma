-- ============================================================================
-- QMA Unified Master Database Schema (PostgreSQL / Supabase)
-- ============================================================================
-- Version: 2.0 (Consolidated master schema for clean database initialization)
-- Includes: Core Commerce Tables, Durable Agent Runtime, MCP OAuth 2.1,
--           Unique Settlement Constraints, Performance Indexes, and RPC Functions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Core Commerce Tables
-- ----------------------------------------------------------------------------

-- Table: qma_payment_events (Immutable payment ledger & audit trail)
CREATE TABLE IF NOT EXISTS public.qma_payment_events (
    event_id TEXT PRIMARY KEY,
    invoice_id TEXT,
    settlement_id TEXT,
    payer_address TEXT,
    symbol TEXT,
    tier TEXT,
    provider_id TEXT DEFAULT 'funding_memory',
    amount_usdc NUMERIC(20, 6),
    gateway_status TEXT,
    transaction_hash TEXT,
    explorer_url TEXT,
    paid_at BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event JSONB
);

-- Table: qma_paid_reports (Permanent report entitlement snapshots)
CREATE TABLE IF NOT EXISTS public.qma_paid_reports (
    entitlement_id TEXT PRIMARY KEY,
    payer_address TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tier TEXT NOT NULL,
    provider_id TEXT DEFAULT 'funding_memory',
    query_hash TEXT,
    settlement_id TEXT,
    paid_at BIGINT,
    saved_at BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    entitlement JSONB NOT NULL
);

-- Table: qma_invoices (Payment negotiation & x402 split state machine)
CREATE TABLE IF NOT EXISTS public.qma_invoices (
    invoice_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    settlement_id TEXT,
    payer_address TEXT,
    symbol TEXT,
    tier TEXT,
    provider_id TEXT DEFAULT 'funding_memory',
    query_hash TEXT,
    created_at BIGINT,
    expires_at BIGINT,
    paid_at BIGINT,
    invoice JSONB NOT NULL
);

-- Table: qma_creator_applications (Creator onboarding & signal provider applications)
CREATE TABLE IF NOT EXISTS public.qma_creator_applications (
    application_id TEXT PRIMARY KEY,
    creator_wallet TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at BIGINT,
    updated_at BIGINT,
    application JSONB NOT NULL
);

-- Table: qma_provider_controls (Admin governance & live provider activation)
CREATE TABLE IF NOT EXISTS public.qma_provider_controls (
    provider_id TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT true,
    updated_at BIGINT,
    control JSONB
);

-- ----------------------------------------------------------------------------
-- 2. Durable AI Agent Runtime & Session Queue
-- ----------------------------------------------------------------------------

-- Table: agent_wallets (Gasless Circle Agent Wallets on Arc Testnet / Mainnet)
CREATE TABLE IF NOT EXISTS public.agent_wallets (
    address TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    balance_usdc NUMERIC(20, 6) DEFAULT 0.0,
    gateway_balance_usdc NUMERIC(20, 6) DEFAULT 0.0,
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Table: agent_sessions (Autonomous background polling & research sessions)
CREATE TABLE IF NOT EXISTS public.agent_sessions (
    id TEXT PRIMARY KEY,
    owner_wallet TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    task TEXT NOT NULL,
    budget_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    max_price_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    allowed_providers TEXT[] DEFAULT ARRAY['funding_memory']::TEXT[],
    allowed_tiers TEXT[] DEFAULT ARRAY['preview', 'full']::TEXT[],
    execution_mode TEXT NOT NULL DEFAULT 'dry_run',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    runtime_state JSONB DEFAULT '{}'::jsonb,
    policy JSONB DEFAULT '{}'::jsonb,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    run_generation BIGINT NOT NULL DEFAULT 0
);

-- Table: agent_session_events (Detailed runtime action stream & audit log)
CREATE TABLE IF NOT EXISTS public.agent_session_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.agent_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. Model Context Protocol (MCP) OAuth 2.1 & Client Connections
-- ----------------------------------------------------------------------------

-- Table: mcp_connections (Client bindings and delegated spending limits)
CREATE TABLE IF NOT EXISTS public.mcp_connections (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    redirect_uris TEXT[] DEFAULT ARRAY[]::TEXT[],
    owner_wallet TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table: mcp_auth_codes (Single-use PKCE authorization codes)
CREATE TABLE IF NOT EXISTS public.mcp_auth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES public.mcp_connections(client_id) ON DELETE CASCADE,
    owner_wallet TEXT NOT NULL,
    caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    pkce_challenge TEXT NOT NULL,
    redirect_uri TEXT NOT NULL DEFAULT '',
    used BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table: mcp_spend_ledger (Audit trail of tools executed by MCP clients)
CREATE TABLE IF NOT EXISTS public.mcp_spend_ledger (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES public.mcp_connections(client_id) ON DELETE CASCADE,
    owner_wallet TEXT NOT NULL,
    invoice_id TEXT,
    settlement_id TEXT,
    provider_id TEXT DEFAULT 'funding_memory',
    symbol TEXT,
    tier TEXT,
    amount_usdc NUMERIC(20, 6) NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 4. Constraints & Deduplication (Financial Invariants)
-- ----------------------------------------------------------------------------

-- Strict Unique Settlement: Prevent double-spend / replay across paid reports
CREATE UNIQUE INDEX IF NOT EXISTS qma_payment_events_settlement_paid_idx 
    ON public.qma_payment_events(settlement_id) 
    WHERE settlement_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS qma_paid_reports_settlement_unique_idx 
    ON public.qma_paid_reports(settlement_id) 
    WHERE settlement_id IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 5. Performance Indexes
-- ----------------------------------------------------------------------------

-- Indexes: qma_payment_events
CREATE INDEX IF NOT EXISTS qma_payment_events_payer_idx ON public.qma_payment_events (payer_address);
CREATE INDEX IF NOT EXISTS qma_payment_events_symbol_idx ON public.qma_payment_events (symbol);
CREATE INDEX IF NOT EXISTS qma_payment_events_paid_at_idx ON public.qma_payment_events (paid_at DESC);
CREATE INDEX IF NOT EXISTS qma_payment_events_invoice_idx ON public.qma_payment_events (invoice_id);
CREATE INDEX IF NOT EXISTS idx_payment_events_provider_created ON public.qma_payment_events (provider_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_events_event_gin ON public.qma_payment_events USING gin (event);

-- Indexes: qma_paid_reports
CREATE INDEX IF NOT EXISTS qma_paid_reports_payer_idx ON public.qma_paid_reports (payer_address);
CREATE INDEX IF NOT EXISTS qma_paid_reports_symbol_idx ON public.qma_paid_reports (symbol);
CREATE INDEX IF NOT EXISTS qma_paid_reports_paid_at_idx ON public.qma_paid_reports (paid_at DESC);
CREATE INDEX IF NOT EXISTS qma_paid_reports_saved_at_idx ON public.qma_paid_reports (saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_paid_reports_query_hash ON public.qma_paid_reports (query_hash);
CREATE INDEX IF NOT EXISTS idx_paid_reports_entitlement_gin ON public.qma_paid_reports USING gin (entitlement);

-- Indexes: qma_invoices
CREATE INDEX IF NOT EXISTS qma_invoices_status_idx ON public.qma_invoices (status);
CREATE INDEX IF NOT EXISTS qma_invoices_payer_idx ON public.qma_invoices (payer_address);
CREATE INDEX IF NOT EXISTS qma_invoices_settlement_idx ON public.qma_invoices (settlement_id);
CREATE INDEX IF NOT EXISTS qma_invoices_created_at_idx ON public.qma_invoices (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_status_expires ON public.qma_invoices (status, expires_at);
CREATE INDEX IF NOT EXISTS idx_invoices_invoice_gin ON public.qma_invoices USING gin (invoice);

-- Indexes: agent_sessions
CREATE INDEX IF NOT EXISTS idx_agent_sessions_status ON public.agent_sessions(status);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_owner ON public.agent_sessions(owner_wallet);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_lease ON public.agent_sessions(lease_expires_at) WHERE lease_expires_at IS NOT NULL;

-- Indexes: agent_session_events
CREATE INDEX IF NOT EXISTS idx_agent_session_events_session ON public.agent_session_events(session_id, id);

-- Indexes: mcp_auth_codes & mcp_spend_ledger
CREATE INDEX IF NOT EXISTS idx_mcp_auth_codes_expiry ON public.mcp_auth_codes(expires_at) WHERE used = false;
CREATE INDEX IF NOT EXISTS idx_mcp_spend_owner ON public.mcp_spend_ledger(owner_wallet);

-- ----------------------------------------------------------------------------
-- 6. RPC Functions (Atomic Queue Leasing)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.claim_agent_session_lease(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 60
)
RETURNS TABLE (
    id TEXT,
    owner_wallet TEXT,
    status TEXT,
    task TEXT,
    budget_usdc NUMERIC,
    max_price_usdc NUMERIC,
    allowed_providers TEXT[],
    allowed_tiers TEXT[],
    execution_mode TEXT,
    runtime_state JSONB,
    policy JSONB,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    run_generation BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_session_id TEXT;
BEGIN
    -- Select next available candidate session using FOR UPDATE SKIP LOCKED
    SELECT s.id INTO v_session_id
    FROM public.agent_sessions s
    WHERE s.status = 'queued'
       OR (s.status = 'running' AND s.lease_expires_at < NOW())
    ORDER BY s.created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF v_session_id IS NULL THEN
        RETURN;
    END IF;

    -- Update session lease and increment run_generation for fencing
    RETURN QUERY
    UPDATE public.agent_sessions s
    SET 
        status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        started_at = COALESCE(s.started_at, NOW()),
        run_generation = s.run_generation + 1
    WHERE s.id = v_session_id
    RETURNING 
        s.id,
        s.owner_wallet,
        s.status,
        s.task,
        s.budget_usdc,
        s.max_price_usdc,
        s.allowed_providers,
        s.allowed_tiers,
        s.execution_mode,
        s.runtime_state,
        s.policy,
        s.lease_owner,
        s.lease_expires_at,
        s.run_generation;
END;
$$;
