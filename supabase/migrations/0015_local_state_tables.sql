-- ============================================================================
-- Migration: 0015_local_state_tables.sql
-- Description: Move the remaining process-local JSON state into PostgreSQL so
--              every instance (local Postgres, Supabase, any managed Postgres)
--              shares one source of truth:
--                1. swap_executions             - swap idempotency/execution store
--                2. stablefx_consumed_deposits   - StableFX deposit replay guard
--                3. earn_vault_snapshots         - vault share-price time series
--                4. qma_runtime_flags            - cross-instance runtime flags
--                                                  (emergency halt fast path)
-- Notes: Idempotent. Apply with `python scripts/apply_migrations.py`.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Swap execution store (keyed by quote_id and "idemp:<key>")
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.swap_executions (
    execution_key TEXT PRIMARY KEY,
    quote_id TEXT NOT NULL,
    record JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_swap_executions_quote_id
    ON public.swap_executions (quote_id);

-- ----------------------------------------------------------------------------
-- 2. StableFX deposit replay guard. The primary key makes the reservation
--    atomic across processes and instances (INSERT ... ON CONFLICT DO NOTHING).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stablefx_consumed_deposits (
    deposit_tx_hash TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved', 'broadcast')),
    quote_id TEXT,
    recipient_address TEXT,
    payout_tx_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. Earn vault share-price snapshots
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.earn_vault_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    vault_id TEXT NOT NULL,
    ts DOUBLE PRECISION NOT NULL,
    share_price_usdc NUMERIC(30, 12) NOT NULL DEFAULT 0,
    tvl_usdc NUMERIC(30, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_earn_vault_snapshots_vault_ts
    ON public.earn_vault_snapshots (vault_id, ts);

-- ----------------------------------------------------------------------------
-- 4. Runtime flags shared by every instance
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_runtime_flags (
    flag_name TEXT PRIMARY KEY,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
