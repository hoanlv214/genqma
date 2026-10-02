-- ============================================================================
-- Migration: 0006_mcp_oauth.sql
-- Description: Model Context Protocol (MCP) OAuth 2.1 (PKCE) Authorization Server
-- Storage for hosted QMA MCP server & client connection management.
-- ============================================================================

-- 1. Registered MCP clients / connections
CREATE TABLE IF NOT EXISTS public.mcp_connections (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    redirect_uris JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_wallet TEXT,
    caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mcp_connections_owner
    ON public.mcp_connections (owner_wallet) WHERE owner_wallet IS NOT NULL;

-- 2. Single-use PKCE authorization codes
CREATE TABLE IF NOT EXISTS public.mcp_auth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    owner_wallet TEXT NOT NULL,
    caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    pkce_challenge TEXT NOT NULL,
    redirect_uri TEXT,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_auth_codes_expiry
    ON public.mcp_auth_codes (expires_at) WHERE used = FALSE;

-- 3. Per-connection spend ledger for delegated budget-cap enforcement
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'mcp_spend_ledger' AND column_name = 'client_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'mcp_spend_ledger' AND column_name = 'connection_id'
    ) THEN
        ALTER TABLE public.mcp_spend_ledger RENAME COLUMN client_id TO connection_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'mcp_spend_ledger' AND column_name = 'paid_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'mcp_spend_ledger' AND column_name = 'created_at'
    ) THEN
        ALTER TABLE public.mcp_spend_ledger RENAME COLUMN paid_at TO created_at;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.mcp_spend_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT NOT NULL,
    invoice_id TEXT,
    amount_usdc NUMERIC(20, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_spend_connection
    ON public.mcp_spend_ledger (connection_id, created_at DESC);

-- 4. Enable RLS & service-role grants (safe across Local Postgres, Neon, Supabase)
ALTER TABLE public.mcp_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mcp_auth_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mcp_spend_ledger ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.mcp_connections TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.mcp_auth_codes TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.mcp_spend_ledger TO service_role;
    END IF;
END $$;
