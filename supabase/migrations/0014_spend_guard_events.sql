-- ============================================================================
-- Migration: 0014_spend_guard_events.sql
-- Description: Durable spend-guard ledger for autonomous agent spending
--              controls. Persists every recorded spend, policy rejection,
--              execution failure, and circuit-breaker transition so daily
--              caps and policy interventions survive process restarts
--              (the guard previously kept counters in process memory only).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.qma_spend_guard_events (
    event_id BIGSERIAL PRIMARY KEY,
    payer_address TEXT NOT NULL,
    event_type TEXT NOT NULL,                      -- SPEND | REJECT | FAILURE | BREAKER_TRIP | BREAKER_RESET
    amount_usdc NUMERIC(20, 6) NOT NULL DEFAULT 0.0,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spend_guard_events_payer_created
    ON public.qma_spend_guard_events (payer_address, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_spend_guard_events_type_created
    ON public.qma_spend_guard_events (event_type, created_at DESC);
