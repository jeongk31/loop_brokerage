-- Intra-family share transfers + cash balances.
-- Run in the Supabase SQL editor (project vnxfpsjbagdbmheomxzu).

-- Transfers: reattribute shares from one member to another WITHOUT changing the
-- grand total. Applied after holdings are derived from trades, so the giver's
-- position may go negative (a deficit to buy back to break even).
create table if not exists public.transfers (
    id              uuid primary key default gen_random_uuid(),
    ticker          text not null,
    name            text not null,
    currency        text not null default 'USD',
    quantity        numeric not null,        -- current (post-split) shares moved
    avg_cost        numeric not null default 0,
    from_user_id    uuid references users(id) on delete set null,
    from_platform_id uuid references platforms(id) on delete set null,
    to_user_id      uuid references users(id) on delete set null,
    to_platform_id  uuid references platforms(id) on delete set null,
    transfer_date   date,
    note            text,
    created_at      timestamptz not null default now()
);

-- Cash balances per member + currency (KRW / USD).
create table if not exists public.cash_balances (
    user_id   uuid not null references users(id) on delete cascade,
    currency  text not null check (currency in ('KRW', 'USD')),
    amount    numeric not null default 0,
    primary key (user_id, currency)
);
