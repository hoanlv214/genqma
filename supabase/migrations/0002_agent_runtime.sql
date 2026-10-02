-- ============================================================================
-- Migration: 0002_agent_runtime.sql
-- Description: Durable Agent Runtime, Agent Wallets, and Session Queue RPCs
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Agent Wallets (Gasless Circle Agent Wallets on Arc)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_wallets (
    address TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    balance_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    spent_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    spend_cap_usdc NUMERIC(20, 6) NOT NULL DEFAULT 10000.0,
    gateway_balance_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ----------------------------------------------------------------------------
-- 2. Agent Sessions (Autonomous Background Tasks & Diligence Sprints)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_sessions (
    id TEXT PRIMARY KEY,
    owner_wallet TEXT NOT NULL,
    agent_label TEXT DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'paused', 'completed', 'failed', 'stopped')),
    mode TEXT DEFAULT 'continuous',
    interval_seconds INT DEFAULT 300,
    max_cycles INT DEFAULT 100,
    budget_usdc NUMERIC(20, 6) DEFAULT 50.0,
    spent_usdc NUMERIC(20, 6) DEFAULT 0.0,
    strategy_config JSONB DEFAULT '{}'::jsonb,
    runtime_state JSONB DEFAULT '{}'::jsonb,
    next_run_at TIMESTAMPTZ DEFAULT NOW(),
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    state_version INT NOT NULL DEFAULT 1,
    run_generation INT NOT NULL DEFAULT 1,
    last_checkpoint_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_queue 
    ON public.agent_sessions(status, next_run_at) 
    WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS idx_agent_sessions_owner ON public.agent_sessions(owner_wallet);

-- ----------------------------------------------------------------------------
-- 3. Agent Session Events (Telemetry & Audit Logs)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_session_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES public.agent_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    cycle_index INT DEFAULT 0,
    action_type TEXT,
    symbol TEXT,
    status TEXT,
    amount_usdc NUMERIC(20, 6) DEFAULT 0.0,
    message TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_session_events_session ON public.agent_session_events(session_id, created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. MCP OAuth 2.1 State
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    redirect_uris JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.agent_oauth_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id TEXT REFERENCES public.agent_oauth_clients(client_id) ON DELETE CASCADE,
    wallet_address TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'read:reports',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. Queue Lease RPCs (Concurrency & Zero Race Conditions)
-- ----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.claim_agent_session_lease(TEXT, INT) CASCADE;
DROP FUNCTION IF EXISTS public.acquire_session_tick_lease(TEXT, INT) CASCADE;
DROP FUNCTION IF EXISTS public.checkpoint_session_tick CASCADE;
DROP FUNCTION IF EXISTS public.heartbeat_session_lease CASCADE;

CREATE OR REPLACE FUNCTION public.claim_agent_session_lease(
    p_worker_id TEXT,
    p_lease_duration_sec INT DEFAULT 60
) RETURNS SETOF public.agent_sessions AS $$
DECLARE
    v_picked_id TEXT;
    v_row public.agent_sessions%ROWTYPE;
BEGIN
    SELECT id INTO v_picked_id
    FROM public.agent_sessions
    WHERE status IN ('queued', 'running')
      AND (next_run_at IS NULL OR next_run_at <= NOW())
      AND (lease_expires_at IS NULL OR lease_expires_at < NOW())
    ORDER BY next_run_at ASC NULLS FIRST, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF v_picked_id IS NOT NULL THEN
        UPDATE public.agent_sessions
        SET status = 'running',
            lease_owner = p_worker_id,
            lease_expires_at = NOW() + (GREATEST(p_lease_duration_sec, 15) || ' seconds')::INTERVAL,
            heartbeat_at = NOW(),
            run_generation = run_generation + 1,
            updated_at = NOW()
        WHERE id = v_picked_id
        RETURNING * INTO v_row;

        RETURN NEXT v_row;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.acquire_session_tick_lease(
    p_worker_id TEXT,
    p_lease_duration_sec INT DEFAULT 60
) RETURNS SETOF public.agent_sessions AS $$
BEGIN
    RETURN QUERY SELECT * FROM public.claim_agent_session_lease(p_worker_id, p_lease_duration_sec);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.checkpoint_session_tick(
    p_session_id TEXT,
    p_worker_id TEXT,
    p_run_generation INT,
    p_status TEXT,
    p_runtime_state JSONB,
    p_next_run_in_sec INT DEFAULT 15
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated_count INT;
    v_is_terminal BOOLEAN;
BEGIN
    v_is_terminal := p_status IN ('completed', 'failed', 'stopped');

    UPDATE public.agent_sessions
    SET status = p_status,
        runtime_state = p_runtime_state,
        state_version = state_version + 1,
        last_checkpoint_at = NOW(),
        heartbeat_at = NOW(),
        lease_owner = CASE WHEN v_is_terminal THEN NULL ELSE p_worker_id END,
        lease_expires_at = CASE WHEN v_is_terminal THEN NULL ELSE NOW() + (GREATEST(p_next_run_in_sec, 10) || ' seconds')::INTERVAL END,
        next_run_at = CASE WHEN v_is_terminal THEN NULL ELSE NOW() + (GREATEST(p_next_run_in_sec, 5) || ' seconds')::INTERVAL END,
        updated_at = NOW()
    WHERE id = p_session_id
      AND lease_owner = p_worker_id
      AND run_generation = p_run_generation
      AND status NOT IN ('stopped', 'completed', 'failed');

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.heartbeat_session_lease(
    p_session_id TEXT,
    p_worker_id TEXT,
    p_run_generation INT,
    p_lease_duration_sec INT DEFAULT 60
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated_count INT;
BEGIN
    UPDATE public.agent_sessions
    SET heartbeat_at = NOW(),
        lease_expires_at = NOW() + (GREATEST(p_lease_duration_sec, 15) || ' seconds')::INTERVAL,
        updated_at = NOW()
    WHERE id = p_session_id
      AND lease_owner = p_worker_id
      AND run_generation = p_run_generation
      AND status IN ('queued', 'running');

    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;
