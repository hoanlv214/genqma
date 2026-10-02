-- ============================================================================
-- Migration: 0004_atomic_spend_policy.sql
-- Description: Atomic spending policy enforcement & budget reservation RPCs
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Reserve Agent Wallet Spend (Enforces autonomous spend cap atomically)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.reserve_agent_wallet_spend(
    p_wallet_address TEXT,
    p_amount         NUMERIC,
    p_spend_cap      NUMERIC DEFAULT 10000.0
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated INT;
BEGIN
    UPDATE public.agent_wallets
       SET spent_usdc = ROUND(spent_usdc + p_amount, 6),
           balance_usdc = ROUND(balance_usdc - p_amount, 6),
           updated_at = NOW()
     WHERE address = p_wallet_address
       AND ROUND(spent_usdc + p_amount, 6) <= p_spend_cap
       AND balance_usdc >= p_amount;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 2. Release / Rollback Agent Wallet Spend (Upon payment rejection or timeout)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.release_agent_wallet_spend(
    p_wallet_address TEXT,
    p_amount         NUMERIC
) RETURNS VOID AS $$
BEGIN
    UPDATE public.agent_wallets
       SET spent_usdc = GREATEST(0, ROUND(spent_usdc - p_amount, 6)),
           balance_usdc = ROUND(balance_usdc + p_amount, 6),
           updated_at = NOW()
     WHERE address = p_wallet_address;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 3. Reserve Session Spend (Enforces individual session budget cap)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.reserve_session_spend(
    p_session_id TEXT,
    p_amount     NUMERIC
) RETURNS BOOLEAN AS $$
DECLARE
    v_updated INT;
BEGIN
    UPDATE public.agent_sessions
       SET spent_usdc = ROUND(spent_usdc + p_amount, 6),
           updated_at = NOW()
     WHERE id = p_session_id
       AND ROUND(spent_usdc + p_amount, 6) <= budget_usdc;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;
