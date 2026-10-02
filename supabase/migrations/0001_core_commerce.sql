-- ============================================================================
-- Migration: 0001_core_commerce.sql
-- Description: Core commerce tables, payment events, and invoices with numeric(20,6) precision
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- 1. Payment Events (Immutable audit ledger)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_payment_events (
    event_id TEXT PRIMARY KEY,
    invoice_id TEXT,
    settlement_id TEXT,
    payer_address TEXT,
    symbol TEXT,
    tier TEXT,
    provider_id TEXT DEFAULT 'funding_memory',
    amount_usdc NUMERIC(20, 6) NOT NULL CHECK (amount_usdc > 0),
    protocol_fee NUMERIC(20, 6) DEFAULT 0.0,
    creator_payout NUMERIC(20, 6) DEFAULT 0.0,
    gateway_status TEXT,
    transaction_hash TEXT,
    explorer_url TEXT,
    paid_at BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    event JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_payment_events_payer ON public.qma_payment_events(payer_address);
CREATE INDEX IF NOT EXISTS idx_payment_events_paid_at ON public.qma_payment_events(paid_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_payment_events_settlement ON public.qma_payment_events(settlement_id);

-- ----------------------------------------------------------------------------
-- 2. Paid Reports (Entitlements)
-- ----------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_paid_reports_payer ON public.qma_paid_reports(payer_address);
CREATE INDEX IF NOT EXISTS idx_paid_reports_symbol ON public.qma_paid_reports(symbol);
CREATE INDEX IF NOT EXISTS idx_paid_reports_settlement ON public.qma_paid_reports(settlement_id);

-- ----------------------------------------------------------------------------
-- 3. Invoices (State machine & negotiation)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_invoices (
    invoice_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'paid', 'expired', 'failed', 'refused')),
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

CREATE UNIQUE INDEX IF NOT EXISTS qma_invoices_settlement_unique_idx
    ON public.qma_invoices (settlement_id) WHERE settlement_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_invoices_status ON public.qma_invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_payer ON public.qma_invoices(payer_address);

-- ----------------------------------------------------------------------------
-- 4. Creator Applications & Claims
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_creator_applications (
    application_id TEXT PRIMARY KEY,
    creator_wallet TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at BIGINT,
    updated_at BIGINT,
    application JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS public.qma_creator_claims (
    claim_id TEXT PRIMARY KEY,
    creator_wallet TEXT,
    amount_usdc NUMERIC(20, 6) DEFAULT 0.0,
    claim JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. Withdrawals & Provider Controls
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.qma_withdrawals (
    operation_id TEXT PRIMARY KEY,
    wallet_address TEXT,
    amount_usdc NUMERIC(20, 6) DEFAULT 0.0,
    operation JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.qma_provider_controls (
    provider_id TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT true,
    updated_at BIGINT,
    control JSONB
);
