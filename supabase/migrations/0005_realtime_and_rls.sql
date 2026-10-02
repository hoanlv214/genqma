-- ============================================================================
-- Migration: 0005_realtime_and_rls.sql
-- Description: Row Level Security, permissions, and Supabase Realtime publication
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Ensure cross-environment roles exist (Supabase / Neon / Local Postgres)
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated;
    END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- 1. Enable Row Level Security (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE public.qma_payment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_paid_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_creator_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_creator_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_withdrawals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_provider_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_session_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qma_ledger_entries ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2. Public Read Policies (for explorers, dashboards, and audit verification)
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    -- Public read for payment events
    DROP POLICY IF EXISTS "public_read_payment_events" ON public.qma_payment_events;
    CREATE POLICY "public_read_payment_events" ON public.qma_payment_events FOR SELECT USING (true);

    -- Public read for paid report entitlements
    DROP POLICY IF EXISTS "public_read_paid_reports" ON public.qma_paid_reports;
    CREATE POLICY "public_read_paid_reports" ON public.qma_paid_reports FOR SELECT USING (true);

    -- Public read for invoices
    DROP POLICY IF EXISTS "public_read_invoices" ON public.qma_invoices;
    CREATE POLICY "public_read_invoices" ON public.qma_invoices FOR SELECT USING (true);

    -- Public read for cryptographic ledger entries
    DROP POLICY IF EXISTS "public_read_ledger_entries" ON public.qma_ledger_entries;
    CREATE POLICY "public_read_ledger_entries" ON public.qma_ledger_entries FOR SELECT USING (true);

    -- Service role write policies
    DROP POLICY IF EXISTS "service_write_payment_events" ON public.qma_payment_events;
    CREATE POLICY "service_write_payment_events" ON public.qma_payment_events FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS "service_write_paid_reports" ON public.qma_paid_reports;
    CREATE POLICY "service_write_paid_reports" ON public.qma_paid_reports FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS "service_write_invoices" ON public.qma_invoices;
    CREATE POLICY "service_write_invoices" ON public.qma_invoices FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS "service_write_creator_claims" ON public.qma_creator_claims;
    CREATE POLICY "service_write_creator_claims" ON public.qma_creator_claims FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS "service_write_withdrawals" ON public.qma_withdrawals;
    CREATE POLICY "service_write_withdrawals" ON public.qma_withdrawals FOR ALL TO service_role USING (true) WITH CHECK (true);

    DROP POLICY IF EXISTS "service_write_ledger_entries" ON public.qma_ledger_entries;
    CREATE POLICY "service_write_ledger_entries" ON public.qma_ledger_entries FOR ALL TO service_role USING (true) WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Restrict RPC Permissions to Service Role
-- ----------------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.claim_agent_session_lease(TEXT, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_agent_session_lease(TEXT, INT) TO service_role;

REVOKE ALL ON FUNCTION public.checkpoint_session_tick(TEXT, TEXT, INT, TEXT, JSONB, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.checkpoint_session_tick(TEXT, TEXT, INT, TEXT, JSONB, INT) TO service_role;

REVOKE ALL ON FUNCTION public.append_qma_ledger_event(TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.append_qma_ledger_event(TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, TEXT) TO service_role;

REVOKE ALL ON FUNCTION public.reserve_agent_wallet_spend(TEXT, NUMERIC, NUMERIC) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reserve_agent_wallet_spend(TEXT, NUMERIC, NUMERIC) TO service_role;

REVOKE ALL ON FUNCTION public.release_agent_wallet_spend(TEXT, NUMERIC) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.release_agent_wallet_spend(TEXT, NUMERIC) TO service_role;

-- ----------------------------------------------------------------------------
-- 4. Enable Supabase Realtime Stream
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.qma_payment_events;
        ALTER PUBLICATION supabase_realtime ADD TABLE public.qma_invoices;
        ALTER PUBLICATION supabase_realtime ADD TABLE public.qma_ledger_entries;
    END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
