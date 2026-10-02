-- ============================================================================
-- Migration: 0008_earn_vault_positions.sql
-- Description: Morpho / Arc ERC-4626 Vault positions and idle treasury rebalancing.
-- Replaces root earn_vault_positions.json with a hardened PostgreSQL table.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.earn_vault_positions (
    position_id TEXT PRIMARY KEY,
    wallet TEXT NOT NULL,
    vault_id TEXT NOT NULL,
    vault_address TEXT,
    shares NUMERIC(28, 18) NOT NULL DEFAULT 0.0,
    principal_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    last_deposit_at TIMESTAMPTZ,
    last_rebalance_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_wallet_vault UNIQUE (wallet, vault_id)
);

CREATE INDEX IF NOT EXISTS idx_earn_positions_wallet ON public.earn_vault_positions (wallet);
CREATE INDEX IF NOT EXISTS idx_earn_positions_vault ON public.earn_vault_positions (vault_id);
CREATE INDEX IF NOT EXISTS idx_earn_positions_rebalance ON public.earn_vault_positions (last_rebalance_at DESC);

ALTER TABLE public.earn_vault_positions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.earn_vault_positions TO service_role;
    END IF;
END $$;
