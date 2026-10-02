-- ============================================================================
-- Migration: 0009_api_keys_and_rate_limits.sql
-- Description: API Key authentication, developer metering, and atomic rate limit counters.
-- ============================================================================

-- 1. API Keys issued to developer wallets (Identity + Rate Limit tracking)
CREATE TABLE IF NOT EXISTS public.api_keys (
    id TEXT PRIMARY KEY,
    prefix TEXT NOT NULL UNIQUE,
    key_hash TEXT NOT NULL,
    wallet TEXT NOT NULL,
    label TEXT,
    scopes TEXT[] NOT NULL DEFAULT ARRAY['reports:read', 'agent:execute']::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_wallet ON public.api_keys (wallet);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON public.api_keys (prefix);

-- 2. Distributed rate limit sliding-window counters
CREATE TABLE IF NOT EXISTS public.rate_limit_counters (
    identifier TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INT NOT NULL DEFAULT 1,
    PRIMARY KEY (identifier, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_window ON public.rate_limit_counters (window_start DESC);

-- 3. Atomic rate limit increment RPC
CREATE OR REPLACE FUNCTION public.check_and_increment_rate_limit(
    p_identifier TEXT,
    p_window_start TIMESTAMPTZ,
    p_max_requests INT
) RETURNS BOOLEAN AS $$
DECLARE
    v_count INT;
BEGIN
    INSERT INTO public.rate_limit_counters (identifier, window_start, request_count)
    VALUES (p_identifier, p_window_start, 1)
    ON CONFLICT (identifier, window_start)
    DO UPDATE SET request_count = public.rate_limit_counters.request_count + 1
    RETURNING request_count INTO v_count;

    RETURN v_count <= p_max_requests;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rate_limit_counters ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.api_keys TO service_role;
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.rate_limit_counters TO service_role;
        GRANT EXECUTE ON FUNCTION public.check_and_increment_rate_limit TO service_role;
    END IF;
END $$;
