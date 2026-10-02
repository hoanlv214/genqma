-- ============================================================================
-- Migration: 0010_webhooks_and_delivery_logs.sql
-- Description: Outbound Webhook Subscriptions and Delivery Audit Trail.
-- ============================================================================

-- 1. Webhook endpoints registered by developers / automated agents
CREATE TABLE IF NOT EXISTS public.webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_wallet TEXT NOT NULL,
    target_url TEXT NOT NULL,
    secret_token TEXT NOT NULL,
    events TEXT[] NOT NULL DEFAULT ARRAY['payment.settled', 'report.delivered', 'agent.incident']::TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhooks_owner ON public.webhooks (owner_wallet);
CREATE INDEX IF NOT EXISTS idx_webhooks_active ON public.webhooks (is_active) WHERE is_active = TRUE;

-- 2. Webhook delivery execution log (retries, payloads, HTTP statuses)
CREATE TABLE IF NOT EXISTS public.webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES public.webhooks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'delivered', 'failed')),
    status_code INT,
    error_message TEXT,
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_due ON public.webhook_deliveries (status, next_attempt_at) WHERE status IN ('pending', 'failed');
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook ON public.webhook_deliveries (webhook_id);

ALTER TABLE public.webhooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_deliveries ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.webhooks TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.webhook_deliveries TO service_role;
    END IF;
END $$;
