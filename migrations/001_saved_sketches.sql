-- Shared saved-sketch library for Drawing Debbie and KARR AI.
--
-- KARR AI accesses rows with the signed-in user's JWT and RLS. The standalone
-- Streamlit app is a shared workspace behind one password gate; its server-only
-- service-role client writes the configured GATE_USER_ID and always filters by
-- that value plus app_scope.

begin;

create table if not exists public.saved_sketches (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null,
  app_scope      text not null,
  name           text not null,
  schema_version integer not null,
  summary        text not null,
  config         jsonb not null,
  view_state     jsonb not null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  constraint saved_sketches_app_scope_check
    check (app_scope ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
  constraint saved_sketches_name_check
    check (
      char_length(btrim(name)) between 1 and 80
      and name = btrim(name)
    ),
  constraint saved_sketches_schema_version_check
    check (schema_version > 0),
  constraint saved_sketches_summary_check
    check (char_length(summary) between 1 and 200),
  constraint saved_sketches_config_object_check
    check (jsonb_typeof(config) = 'object'),
  constraint saved_sketches_view_state_object_check
    check (jsonb_typeof(view_state) = 'object')
);

create unique index if not exists saved_sketches_owner_scope_name_unique
  on public.saved_sketches (user_id, app_scope, lower(name));

create index if not exists saved_sketches_owner_scope_recent
  on public.saved_sketches (user_id, app_scope, updated_at desc);

create or replace function public.set_saved_sketch_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists saved_sketches_set_updated_at
  on public.saved_sketches;
create trigger saved_sketches_set_updated_at
before update on public.saved_sketches
for each row execute function public.set_saved_sketch_updated_at();

alter table public.saved_sketches enable row level security;

drop policy if exists "saved_sketches_select_own" on public.saved_sketches;
create policy "saved_sketches_select_own"
  on public.saved_sketches
  for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "saved_sketches_insert_own" on public.saved_sketches;
create policy "saved_sketches_insert_own"
  on public.saved_sketches
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

drop policy if exists "saved_sketches_update_own" on public.saved_sketches;
create policy "saved_sketches_update_own"
  on public.saved_sketches
  for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "saved_sketches_delete_own" on public.saved_sketches;
create policy "saved_sketches_delete_own"
  on public.saved_sketches
  for delete
  to authenticated
  using ((select auth.uid()) = user_id);

revoke all on table public.saved_sketches from anon;
grant select, insert, update, delete on table public.saved_sketches
  to authenticated;
grant all on table public.saved_sketches to service_role;

commit;
