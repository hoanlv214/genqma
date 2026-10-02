-- ============================================================================
-- Migration: 0003_hash_chained_ledger.sql
-- Description: Tamper-evident cryptographic hash-chained ledger with advisory locks
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.qma_ledger_entries (
    seq          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id           UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    ts           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor        TEXT NOT NULL CHECK (actor IN ('agent', 'cfo', 'human', 'system')),
    domain       TEXT NOT NULL,
    action       TEXT NOT NULL,
    summary      TEXT NOT NULL,
    detail       JSONB NOT NULL DEFAULT '{}'::jsonb,
    body_hash    TEXT NOT NULL,   -- SHA-256 of canonical entry body
    signature    TEXT NOT NULL,   -- Ed25519 or EIP-712 signature over body_hash
    prev_hash    TEXT NOT NULL,   -- Hash of previous sequence item in chain
    hash         TEXT NOT NULL    -- SHA-256(prev_hash || body_hash || signature)
);

CREATE INDEX IF NOT EXISTS idx_ledger_entries_seq_desc ON public.qma_ledger_entries(seq DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_domain ON public.qma_ledger_entries(domain);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_hash ON public.qma_ledger_entries(hash);

-- ----------------------------------------------------------------------------
-- Atomic Append RPC with Advisory Lock (prevents ledger forking under concurrency)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.append_qma_ledger_event(
    p_actor     TEXT,
    p_domain    TEXT,
    p_action    TEXT,
    p_summary   TEXT,
    p_detail    JSONB,
    p_body_hash TEXT,
    p_signature TEXT
) RETURNS public.qma_ledger_entries AS $$
DECLARE
    v_prev_hash TEXT;
    v_hash      TEXT;
    v_row       public.qma_ledger_entries%ROWTYPE;
BEGIN
    -- Transaction-scoped advisory lock serializes concurrent ledger writes
    PERFORM pg_advisory_xact_lock(hashtext('qma_ledger_lock'));

    SELECT hash INTO v_prev_hash 
    FROM public.qma_ledger_entries 
    ORDER BY seq DESC 
    LIMIT 1;

    v_prev_hash := COALESCE(v_prev_hash, REPEAT('0', 64));
    v_hash := encode(digest(v_prev_hash || p_body_hash || p_signature, 'sha256'), 'hex');

    INSERT INTO public.qma_ledger_entries (
        actor, domain, action, summary, detail,
        body_hash, signature, prev_hash, hash
    ) VALUES (
        p_actor, p_domain, p_action, p_summary, COALESCE(p_detail, '{}'::jsonb),
        p_body_hash, p_signature, v_prev_hash, v_hash
    )
    RETURNING * INTO v_row;

    RETURN v_row;
END;
$$ LANGUAGE plpgsql;
