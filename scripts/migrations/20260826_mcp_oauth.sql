-- Migration: 20260826_mcp_oauth.sql
-- Description: OAuth 2.1 (PKCE) authorization server storage for the hosted
-- QMA MCP server. `mcp_connections` holds dynamically-registered MCP clients
-- bound to an owner wallet with server-enforced spend caps;
-- `mcp_auth_codes` holds single-use, short-lived authorization codes;
-- `mcp_spend_ledger` records every paid purchase made through a connection
-- so budget caps are enforced across restarts and replicas.
--
-- Apply once per environment in the Supabase SQL editor.

-- 1. Registered MCP clients / connections
CREATE TABLE IF NOT EXISTS mcp_connections (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL,
    redirect_uris JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_wallet TEXT,
    caps JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- One owner may bind a given client once; the row is reused on re-approval.
CREATE INDEX IF NOT EXISTS idx_mcp_connections_owner
  ON mcp_connections (owner_wallet) WHERE owner_wallet IS NOT NULL;

-- 2. Single-use authorization codes (10-minute TTL enforced in app logic)
CREATE TABLE IF NOT EXISTS mcp_auth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    owner_wallet TEXT NOT NULL,
    caps JSONB NOT NULL,
    pkce_challenge TEXT NOT NULL,
    redirect_uri TEXT,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL
);

-- 3. Per-connection spend ledger for budget-cap enforcement
CREATE TABLE IF NOT EXISTS mcp_spend_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT NOT NULL,
    invoice_id TEXT,
    amount_usdc NUMERIC(20,6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcp_spend_connection
  ON mcp_spend_ledger (connection_id, created_at);

-- 4. Service-role only: OAuth state is backend-managed, never client-writable
REVOKE ALL ON mcp_connections FROM PUBLIC, anon, authenticated;
REVOKE ALL ON mcp_auth_codes FROM PUBLIC, anon, authenticated;
REVOKE ALL ON mcp_spend_ledger FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_connections TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_auth_codes TO service_role;
GRANT SELECT, INSERT ON mcp_spend_ledger TO service_role;
