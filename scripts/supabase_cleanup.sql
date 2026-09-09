-- QMA Supabase cleanup/audit script.
-- Run from Supabase SQL Editor after exporting/backing up the tables.
-- Goal: keep real paid data, mark legacy rows clearly, and avoid counting old
-- single-price ledger rows as current Preview/Full reports.

-- 1) Audit current state.
select
  'qma_invoices' as table_name,
  count(*) as rows,
  count(*) filter (where status = 'pending') as pending_rows,
  count(*) filter (where status = 'expired') as expired_rows,
  count(*) filter (where status = 'paid') as paid_rows,
  count(*) filter (where settlement_id is not null) as with_settlement,
  count(*) filter (where payer_address is not null) as with_payer
from public.qma_invoices
union all
select
  'qma_payment_events',
  count(*),
  null,
  null,
  null,
  count(*) filter (where settlement_id is not null),
  count(*) filter (where payer_address is not null)
from public.qma_payment_events
union all
select
  'qma_paid_reports',
  count(*),
  null,
  null,
  null,
  count(*) filter (where settlement_id is not null),
  count(*) filter (where payer_address is not null)
from public.qma_paid_reports;

-- 2) Mark old migrated single-price events as legacy.
-- These were real testnet payments, but predate the Preview/Full tier model.
update public.qma_payment_events
set
  tier = 'legacy',
  event = jsonb_set(coalesce(event, '{}'::jsonb), '{tier}', '"legacy"', true)
where coalesce(tier, '') = ''
  and amount_usdc = 0.05
  and settlement_id is not null;

-- 3) Repair paid invoices if a previous migration left payment fields but did
-- not update status. This should normally update 0 rows after current code.
update public.qma_invoices
set
  status = 'paid',
  invoice = jsonb_set(coalesce(invoice, '{}'::jsonb), '{status}', '"paid"', true)
where status <> 'paid'
  and settlement_id is not null
  and payer_address is not null
  and paid_at is not null;

-- 4) Expire stale unpaid invoices. Keep them for audit; do not delete.
update public.qma_invoices
set
  status = 'expired',
  invoice = jsonb_set(coalesce(invoice, '{}'::jsonb), '{status}', '"expired"', true)
where status = 'pending'
  and settlement_id is null
  and paid_at is null
  and created_at < extract(epoch from now() - interval '1 day');

-- 5) Backfill missing payment events from report entitlements.
-- This preserves one-off cases where a report snapshot exists but the event row
-- did not get migrated. Amount is inferred from current tier pricing.
insert into public.qma_payment_events (
  event_id,
  invoice_id,
  settlement_id,
  payer_address,
  symbol,
  tier,
  provider_id,
  amount_usdc,
  gateway_status,
  transaction_hash,
  explorer_url,
  paid_at,
  event
)
select
  r.settlement_id as event_id,
  r.entitlement->'invoice'->>'invoice_id' as invoice_id,
  r.settlement_id,
  lower(r.payer_address),
  r.symbol,
  r.tier,
  coalesce(r.provider_id, 'funding_memory'),
  case
    when r.tier = 'preview' then 0.001
    when r.tier = 'full' then 0.005
    else null
  end as amount_usdc,
  coalesce(r.entitlement->'invoice'->>'gateway_status', 'completed') as gateway_status,
  r.entitlement->'invoice'->>'transaction_hash' as transaction_hash,
  r.entitlement->'invoice'->>'explorer_url' as explorer_url,
  r.paid_at,
  jsonb_build_object(
    'settlement_id', r.settlement_id,
    'payer_address', lower(r.payer_address),
    'symbol', r.symbol,
    'tier', r.tier,
    'provider_id', coalesce(r.provider_id, 'funding_memory'),
    'amount_usdc', case
      when r.tier = 'preview' then 0.001
      when r.tier = 'full' then 0.005
      else null
    end,
    'paid_at', r.paid_at,
    'source', 'backfilled_from_paid_report'
  ) as event
from public.qma_paid_reports r
left join public.qma_payment_events e
  on e.settlement_id = r.settlement_id
where r.settlement_id is not null
  and e.event_id is null;

-- 6) Current public traction query.
-- Use this for grant/admin numbers. It excludes legacy rows from Preview/Full
-- counts but still exposes legacy separately for transparency.
select
  count(*) filter (where tier in ('preview', 'full')) as current_paid_unlocks,
  count(*) filter (where tier = 'legacy') as legacy_paid_unlocks,
  count(distinct lower(payer_address)) as unique_buyer_wallets,
  coalesce(sum(amount_usdc) filter (where tier in ('preview', 'full')), 0) as current_usdc,
  coalesce(sum(amount_usdc), 0) as total_usdc_settled,
  count(*) filter (where event->>'buyer_type' = 'agent') as agent_api_unlocks
from public.qma_payment_events
where settlement_id is not null
  and payer_address is not null
  and paid_at is not null;
