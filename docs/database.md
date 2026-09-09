# QMA Database Architecture & Setup Guide

This document outlines the database schema, setup process, and data invariants for the **QMA (Quantitative Market Analogs)** platform.

---

## 1. Quick Setup (1-Click Initialization)

To initialize a clean QMA database in **Supabase** or **PostgreSQL**:

1. Open your **Supabase Dashboard** → **SQL Editor**.
2. Copy and run the consolidated schema file: [`scripts/schema.sql`](file:///c:/Users/Admin/Downloads/code/buy/qma/scripts/schema.sql).
3. Copy your project URL and Service Role Key into your `.env`:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   SUPABASE_SCHEMA=public
   ```

---

## 2. Table Summary & Schemas

| Table Name | Purpose | Primary Key | Critical Indexes & Constraints |
|---|---|---|---|
| `qma_payment_events` | Immutable ledger of all completed payments | `event_id` | `UNIQUE (settlement_id)`, `payer_address`, `paid_at DESC` |
| `qma_paid_reports` | Entitlement snapshots of unlocked reports | `entitlement_id` | `UNIQUE (settlement_id)`, `payer_address`, `symbol` |
| `qma_invoices` | Invoice lifecycle & split state machine | `invoice_id` | `status`, `payer_address`, `settlement_id`, `created_at DESC` |
| `qma_creator_applications` | Creator applications for data providers | `application_id` | `creator_wallet`, `provider_id`, `status` |
| `qma_provider_controls` | Admin controls to enable/disable providers | `provider_id` | `enabled`, `updated_at` |
| `agent_wallets` | Gasless Circle Agent Wallet balances | `address` | `status`, `last_sync_at` |
| `agent_sessions` | Durable autonomous agent research queue | `id` | `status`, `owner_wallet`, `lease_expires_at` |
| `agent_session_events` | Granular event audit stream per session | `id` | `(session_id, id)` |
| `mcp_connections` | OAuth 2.1 client bindings & spending caps | `client_id` | `owner_wallet`, `status` |
| `mcp_auth_codes` | Single-use PKCE authorization codes | `code` | `expires_at` (WHERE used = false) |
| `mcp_spend_ledger` | Audit log of tools executed by MCP clients | `id` | `owner_wallet`, `paid_at` |

---

## 3. Financial Invariants & Concurrency Safety

1. **Strict Settlement Deduplication (`UNIQUE INDEX`)**:
   - `qma_payment_events_settlement_paid_idx`: Enforces that each `settlement_id` can only be credited once across the entire network.
   - `qma_paid_reports_settlement_unique_idx`: Prevents issuing duplicate entitlements for the same settlement hash.

2. **Durable Worker Queue & Distributed Leases**:
   - `claim_agent_session_lease(p_worker_id, p_lease_duration_seconds)`: Uses PostgreSQL `FOR UPDATE SKIP LOCKED` to atomically claim queued sessions without race conditions across multiple worker pods.
   - Increments `run_generation` to fence out stale worker instances.

3. **Single-Use PKCE Codes**:
   - `mcp_auth_codes`: Authorization codes are single-use (`used = true` atomically updated via PostgREST `PATCH`) with a 600-second TTL.

---

## 4. Local vs Production Storage

QMA supports dual-storage backends via [`backend/app/repositories/storage.py`](file:///c:/Users/Admin/Downloads/code/buy/qma/backend/app/repositories/storage.py):

* **Local / Test Mode (`JsonStorage`)**: When `SUPABASE_URL` is omitted, the platform stores state in local JSON files (`paid_reports.json`, `payment_ledger.json`).
* **Production Mode (`SupabaseStorage`)**: When `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are provided, the backend connects directly to PostgreSQL via PostgREST with connection pooling.
