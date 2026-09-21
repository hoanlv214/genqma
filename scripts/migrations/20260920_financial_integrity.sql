-- Apply before deploying the financial-integrity backend update.
-- Existing duplicate settlements must be reconciled; never delete them blindly.
begin;
create unique index if not exists qma_invoices_settlement_unique_idx
  on public.qma_invoices (settlement_id) where settlement_id is not null;
create table if not exists public.qma_creator_claims (
  claim_id text primary key,
  claim jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists public.qma_withdrawals (
  operation_id text primary key,
  operation jsonb not null,
  created_at timestamptz not null default now()
);
alter table public.qma_creator_claims enable row level security;
alter table public.qma_withdrawals enable row level security;
revoke all on public.qma_creator_claims, public.qma_withdrawals from anon, authenticated;
grant all on public.qma_creator_claims, public.qma_withdrawals to service_role;
notify pgrst, 'reload schema';
commit;
