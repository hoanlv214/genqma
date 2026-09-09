create type session_status as enum ('draft', 'queued', 'running', 'completed', 'failed', 'stopped');

create table if not exists agent_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null, -- references auth.users(id) if using Supabase auth
  title text not null,
  task text not null,
  budget_usdc numeric(18,6) not null,
  status session_status not null default 'draft',
  runtime_state jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists agent_session_events (
  id bigint generated always as identity primary key,
  session_id uuid not null references agent_sessions(id) on delete cascade,
  event_type text not null,
  payload jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_agent_sessions_user_id on agent_sessions(user_id);
create index if not exists idx_agent_sessions_status on agent_sessions(status);
create index if not exists idx_agent_session_events_session_id on agent_session_events(session_id);

-- Trigger for updated_at
create or replace function update_updated_at_column()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists update_agent_sessions_updated_at on agent_sessions;
create trigger update_agent_sessions_updated_at
before update on agent_sessions
for each row execute function update_updated_at_column();

-- RPC for atomic queue acquisition
create or replace function pick_queued_session()
returns setof agent_sessions as $$
declare
  picked_row agent_sessions%rowtype;
begin
  update agent_sessions
  set status = 'running', updated_at = now()
  where id = (
    select id
    from agent_sessions
    where status = 'queued'
    order by created_at asc
    limit 1
    for update skip locked
  )
  returning * into picked_row;

  if found then
    return next picked_row;
  end if;
end;
$$ language plpgsql;
