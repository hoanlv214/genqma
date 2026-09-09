-- Migration: 20260824_agent_wallets.sql
-- Description: Agent wallet registry — one Circle Agent Wallet per owner wallet,
-- stored independently of agent_sessions so the wallet binding (and any USDC
-- the wallet still holds) survives session deletion.
--
-- Deploy order: backend code that reads this registry degrades gracefully when
-- the table is missing (falls back to agent_sessions.runtime_state and ignores
-- registry writes), so this migration may be applied before or after the
-- backend deploy. Apply it once per environment in the Supabase SQL editor.

-- 1. Registry table: one row per owner wallet
CREATE TABLE IF NOT EXISTS agent_wallets (
    owner_wallet TEXT PRIMARY KEY,
    agent_wallet_id TEXT NOT NULL,
    agent_wallet_address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Backfill from existing session bindings (first row per owner wins)
INSERT INTO agent_wallets (owner_wallet, agent_wallet_id, agent_wallet_address)
SELECT DISTINCT ON (runtime_state->>'owner_wallet')
    runtime_state->>'owner_wallet',
    runtime_state->>'agent_wallet_id',
    runtime_state->>'agent_wallet_address'
FROM agent_sessions
WHERE runtime_state ? 'owner_wallet'
  AND runtime_state ? 'agent_wallet_id'
  AND runtime_state ? 'agent_wallet_address'
ON CONFLICT (owner_wallet) DO NOTHING;

-- 3. Service-role only: the registry is backend-managed, never client-writable
REVOKE ALL ON agent_wallets FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON agent_wallets TO service_role;
