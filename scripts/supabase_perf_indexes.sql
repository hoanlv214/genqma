-- QMA Supabase performance indexes for existing deployments.
-- Safe to run multiple times. These do not change or delete existing data.
--
-- Fresh projects created from docs/SUPABASE.md already include:
-- - qma_payment_events_payer_idx on (payer_address, paid_at desc)
-- - qma_paid_reports_wallet_idx on (payer_address, saved_at desc)

create table if not exists public.qma_provider_controls (
  provider_id text primary key,
  enabled boolean not null default true,
  updated_at double precision,
  control jsonb not null default '{}'::jsonb
);

create index if not exists qma_paid_reports_settlement_idx
  on public.qma_paid_reports (settlement_id);

create unique index if not exists qma_invoices_settlement_unique_idx
  on public.qma_invoices (settlement_id)
  where settlement_id is not null;

create unique index if not exists qma_payment_events_settlement_unique_idx
  on public.qma_payment_events (settlement_id)
  where settlement_id is not null;

create index if not exists qma_invoices_payer_status_paid_idx
  on public.qma_invoices (payer_address, status, paid_at desc);
