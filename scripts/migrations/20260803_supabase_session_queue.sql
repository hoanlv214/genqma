-- Migration: 20260803_supabase_session_queue.sql
-- Description: Schema extensions, RLS permissions, and PL/pgSQL RPCs for durable session ticks and Supabase Queue execution.

-- 1. Extend agent_sessions table with lease, tick, and versioning columns
ALTER TABLE agent_sessions 
  ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS lease_owner TEXT,
  ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS state_version INT NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS run_generation INT NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS last_checkpoint_at TIMESTAMPTZ;

-- 2. Index for fast queue acquisition of due ticks
CREATE INDEX IF NOT EXISTS idx_agent_sessions_tick_queue 
  ON agent_sessions (status, next_run_at) 
  WHERE status IN ('queued', 'running');

-- 3. Atomic RPC to acquire a tick lease on a due session
CREATE OR REPLACE FUNCTION acquire_session_tick_lease(
  p_worker_id TEXT,
  p_lease_duration_sec INT DEFAULT 60
)
RETURNS SETOF agent_sessions AS $$
DECLARE
  v_picked_id UUID;
  v_row agent_sessions%ROWTYPE;
BEGIN
  SELECT id INTO v_picked_id
  FROM agent_sessions
  WHERE status IN ('queued', 'running')
    AND (next_run_at IS NULL OR next_run_at <= NOW())
    AND (lease_expires_at IS NULL OR lease_expires_at < NOW())
  ORDER BY next_run_at ASC NULLS FIRST, created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_picked_id IS NOT NULL THEN
    UPDATE agent_sessions
    SET status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (GREATEST(p_lease_duration_sec, 15) || ' seconds')::INTERVAL,
        heartbeat_at = NOW(),
        run_generation = run_generation + 1,
        updated_at = NOW()
    WHERE id = v_picked_id
    RETURNING * INTO v_row;

    RETURN NEXT v_row;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- 4. Atomic RPC to checkpoint runtime state and schedule next tick
CREATE OR REPLACE FUNCTION checkpoint_session_tick(
  p_session_id UUID,
  p_worker_id TEXT,
  p_run_generation INT,
  p_status TEXT,
  p_runtime_state JSONB,
  p_next_run_in_sec INT DEFAULT 15
)
RETURNS BOOLEAN AS $$
DECLARE
  v_updated_count INT;
  v_is_terminal BOOLEAN;
BEGIN
  v_is_terminal := p_status IN ('completed', 'failed', 'stopped');

  -- Protect against writing over an externally stopped session
  UPDATE agent_sessions
  SET status = p_status::session_status,
      runtime_state = p_runtime_state,
      state_version = state_version + 1,
      last_checkpoint_at = NOW(),
      heartbeat_at = NOW(),
      lease_owner = CASE WHEN v_is_terminal THEN NULL ELSE p_worker_id END,
      lease_expires_at = CASE WHEN v_is_terminal THEN NULL ELSE NOW() + (GREATEST(p_next_run_in_sec, 10) || ' seconds')::INTERVAL END,
      next_run_at = CASE WHEN v_is_terminal THEN NULL ELSE NOW() + (GREATEST(p_next_run_in_sec, 5) || ' seconds')::INTERVAL END,
      updated_at = NOW()
  WHERE id = p_session_id
    AND lease_owner = p_worker_id
    AND run_generation = p_run_generation
    AND status NOT IN ('stopped', 'completed', 'failed');

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;
  RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;

-- 5. Heartbeat RPC to extend active lease
CREATE OR REPLACE FUNCTION heartbeat_session_lease(
  p_session_id UUID,
  p_worker_id TEXT,
  p_run_generation INT,
  p_lease_duration_sec INT DEFAULT 60
)
RETURNS BOOLEAN AS $$
DECLARE
  v_updated_count INT;
BEGIN
  UPDATE agent_sessions
  SET heartbeat_at = NOW(),
      lease_expires_at = NOW() + (GREATEST(p_lease_duration_sec, 15) || ' seconds')::INTERVAL,
      updated_at = NOW()
  WHERE id = p_session_id
    AND lease_owner = p_worker_id
    AND run_generation = p_run_generation
    AND status IN ('queued', 'running');

  GET DIAGNOSTICS v_updated_count = ROW_COUNT;
  RETURN v_updated_count > 0;
END;
$$ LANGUAGE plpgsql;

-- 6. Safety net RPC to reclaim expired leases
CREATE OR REPLACE FUNCTION reclaim_expired_leases()
RETURNS INT AS $$
DECLARE
  v_reclaimed_count INT;
BEGIN
  UPDATE agent_sessions
  SET lease_owner = NULL,
      lease_expires_at = NULL,
      next_run_at = NOW(),
      updated_at = NOW()
  WHERE status = 'running'
    AND lease_expires_at IS NOT NULL
    AND lease_expires_at < NOW();

  GET DIAGNOSTICS v_reclaimed_count = ROW_COUNT;
  RETURN v_reclaimed_count;
END;
$$ LANGUAGE plpgsql;

-- 7. Rolling-deployment compatibility: Update legacy pick_queued_session to set lease_owner
CREATE OR REPLACE FUNCTION pick_queued_session()
RETURNS SETOF agent_sessions AS $$
DECLARE
  picked_row agent_sessions%rowtype;
BEGIN
  UPDATE agent_sessions
  SET status = 'running',
      lease_owner = 'legacy_worker',
      lease_expires_at = NOW() + INTERVAL '10 minutes',
      run_generation = run_generation + 1,
      updated_at = NOW()
  WHERE id = (
    SELECT id
    FROM agent_sessions
    WHERE status = 'queued'
      AND (lease_expires_at IS NULL OR lease_expires_at < NOW())
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING * INTO picked_row;

  IF FOUND THEN
    RETURN NEXT picked_row;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- 8. Restrict RPC permissions (Security & RLS hardening)
REVOKE EXECUTE ON FUNCTION acquire_session_tick_lease(TEXT, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION acquire_session_tick_lease(TEXT, INT) TO service_role;

REVOKE EXECUTE ON FUNCTION checkpoint_session_tick(UUID, TEXT, INT, TEXT, JSONB, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION checkpoint_session_tick(UUID, TEXT, INT, TEXT, JSONB, INT) TO service_role;

REVOKE EXECUTE ON FUNCTION heartbeat_session_lease(UUID, TEXT, INT, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION heartbeat_session_lease(UUID, TEXT, INT, INT) TO service_role;

REVOKE EXECUTE ON FUNCTION reclaim_expired_leases() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION reclaim_expired_leases() TO service_role;

REVOKE EXECUTE ON FUNCTION pick_queued_session() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION pick_queued_session() TO service_role;
