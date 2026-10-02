-- ============================================================================
-- Migration: 0011_euthyna_and_traction_views.sql
-- Description: Euthyna cryptographic audit trail table, treasury policy table,
--              and optimized analytical database views for traction, metrics,
--              payer leaderboard, and provider revenue breakdowns.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Euthyna Cryptographic Audit Trail Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.euthyna_audit_trail (
    record_id TEXT PRIMARY KEY,
    previous_hash TEXT,
    timestamp TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    amount_usdc NUMERIC(20, 6) DEFAULT 0.0,
    treasury_liquid_before NUMERIC(20, 6) DEFAULT 0.0,
    treasury_liquid_after NUMERIC(20, 6) DEFAULT 0.0,
    usyc_vault_shares NUMERIC(20, 6) DEFAULT 0.0,
    tx_hash TEXT,
    arcscan_url TEXT,
    policy_rule_applied TEXT,
    cfo_reasoning TEXT,
    provider_id TEXT,
    genlayer_consensus TEXT,
    integrity_hash TEXT,
    status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_euthyna_audit_actor ON public.euthyna_audit_trail (actor);
CREATE INDEX IF NOT EXISTS idx_euthyna_audit_action ON public.euthyna_audit_trail (action);
CREATE INDEX IF NOT EXISTS idx_euthyna_audit_created ON public.euthyna_audit_trail (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_euthyna_audit_tx ON public.euthyna_audit_trail (tx_hash) WHERE tx_hash IS NOT NULL;

ALTER TABLE public.euthyna_audit_trail ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.euthyna_audit_trail TO service_role;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Corporate Treasury Policy Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_treasury_policy (
    policy_id TEXT PRIMARY KEY DEFAULT 'default',
    policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.qma_treasury_policy ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.qma_treasury_policy TO service_role;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Optimized Analytical Views (Read-Only Offload for High-Traffic Endpoints)
-- ----------------------------------------------------------------------------

-- A. Daily Traction Aggregate View (Offloads looping over raw events on /api/v1/traction)
CREATE OR REPLACE VIEW public.v_platform_traction_daily AS
SELECT
    to_char(to_timestamp(COALESCE(paid_at, EXTRACT(EPOCH FROM created_at)::bigint)), 'YYYY-MM-DD') AS day_bucket,
    COUNT(*) AS total_reports,
    COUNT(CASE WHEN gateway_status IN ('SETTLED', 'COMPLETED', 'completed', 'ACCEPTED', 'accepted') OR transaction_hash IS NOT NULL THEN 1 END) AS settled_reports,
    COALESCE(SUM(amount_usdc), 0)::NUMERIC(20, 6) AS total_volume_usdc,
    COALESCE(SUM(CASE WHEN gateway_status IN ('SETTLED', 'COMPLETED', 'completed', 'ACCEPTED', 'accepted') OR transaction_hash IS NOT NULL THEN amount_usdc ELSE 0 END), 0)::NUMERIC(20, 6) AS settled_volume_usdc,
    COUNT(DISTINCT payer_address) AS unique_active_payers
FROM public.qma_payment_events
GROUP BY to_char(to_timestamp(COALESCE(paid_at, EXTRACT(EPOCH FROM created_at)::bigint)), 'YYYY-MM-DD')
ORDER BY day_bucket DESC;

-- B. Platform Metrics Summary View (Used by /api/v1/metrics and /api/v1/platform/summary)
CREATE OR REPLACE VIEW public.v_platform_metrics_summary AS
SELECT
    COUNT(*) AS total_paid_count,
    COALESCE(SUM(amount_usdc), 0)::NUMERIC(20, 6) AS total_revenue_usdc,
    COUNT(DISTINCT payer_address) AS unique_payers,
    MAX(COALESCE(paid_at, EXTRACT(EPOCH FROM created_at)::bigint)) AS last_paid_at,
    COUNT(CASE WHEN gateway_status IN ('SETTLED', 'COMPLETED', 'completed', 'ACCEPTED', 'accepted') OR transaction_hash IS NOT NULL THEN 1 END) AS settled_count
FROM public.qma_payment_events;

-- C. Payer Traction Leaderboard View (Used by /api/v1/platform/payers)
CREATE OR REPLACE VIEW public.v_payer_traction_leaderboard AS
SELECT
    payer_address,
    COUNT(*) AS payment_count,
    COALESCE(SUM(amount_usdc), 0)::NUMERIC(20, 6) AS total_spent_usdc,
    MAX(COALESCE(paid_at, EXTRACT(EPOCH FROM created_at)::bigint)) AS last_paid_at,
    MAX(created_at) AS last_seen_at
FROM public.qma_payment_events
WHERE payer_address IS NOT NULL
GROUP BY payer_address
ORDER BY total_spent_usdc DESC;

-- D. Provider Revenue Breakdown View
CREATE OR REPLACE VIEW public.v_provider_revenue_breakdown AS
SELECT
    COALESCE(provider_id, 'funding_memory') AS provider_id,
    COUNT(*) AS invoice_count,
    COALESCE(SUM(amount_usdc), 0)::NUMERIC(20, 6) AS total_revenue_usdc,
    COUNT(DISTINCT payer_address) AS unique_buyers
FROM public.qma_payment_events
GROUP BY COALESCE(provider_id, 'funding_memory')
ORDER BY total_revenue_usdc DESC;
