-- Family Portfolio Tracker — initial schema
-- Run this in the Supabase SQL editor (SQL Editor > New query > paste > Run).
-- Safe to re-run: uses IF NOT EXISTS / idempotent guards where possible.

-- UUID generator (Supabase ships pgcrypto; gen_random_uuid lives there)
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- users: admin + viewers. Login codes are stored ONLY as a salted hash.
-- ---------------------------------------------------------------------------
create table if not exists users (
    id           uuid primary key default gen_random_uuid(),
    display_name text not null,
    role         text not null check (role in ('admin', 'viewer')),
    code_hash    text not null,
    created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- platforms: brokerage names (토스증권, 키움, 미래에셋, ...)
-- ---------------------------------------------------------------------------
create table if not exists platforms (
    id         uuid primary key default gen_random_uuid(),
    name       text not null unique,
    created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- holdings: current positions. current price/value/return computed at runtime.
-- ---------------------------------------------------------------------------
create table if not exists holdings (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references users(id) on delete cascade,
    platform_id      uuid references platforms(id) on delete set null,
    ticker           text not null,            -- Yahoo ticker, e.g. 005930.KS / AAPL
    name             text not null,            -- display name, e.g. 삼성전자
    quantity         numeric not null default 0,
    avg_cost         numeric not null default 0,
    is_family_shared boolean not null default false,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists idx_holdings_user on holdings(user_id);
create index if not exists idx_holdings_shared on holdings(is_family_shared);

-- ---------------------------------------------------------------------------
-- transactions: buy/sell history.
-- ---------------------------------------------------------------------------
create table if not exists transactions (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    platform_id uuid references platforms(id) on delete set null,
    ticker      text not null,
    name        text not null,
    side        text not null check (side in ('buy', 'sell')),  -- 매수 / 매도
    trade_date  date not null,
    quantity    numeric not null,
    price       numeric not null,
    fee         numeric not null default 0,
    currency    text not null default 'KRW',
    notes       text,
    created_at  timestamptz not null default now()
);
create index if not exists idx_tx_user on transactions(user_id);
create index if not exists idx_tx_date on transactions(trade_date);

-- ---------------------------------------------------------------------------
-- loans: admin-only. Used in net-worth math in a later pass.
-- ---------------------------------------------------------------------------
create table if not exists loans (
    id               uuid primary key default gen_random_uuid(),
    name             text not null,
    lender           text,
    original_amount  numeric not null default 0,
    remaining_amount numeric not null default 0,
    interest_rate    numeric,                  -- annual %, e.g. 4.5
    monthly_payment  numeric,
    start_date       date,
    maturity_date    date,
    notes            text,
    created_at       timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- price_cache: latest fetched price per ticker (yfinance), to avoid repeat calls.
-- ---------------------------------------------------------------------------
create table if not exists price_cache (
    ticker     text primary key,
    price      numeric not null,
    as_of      date,                           -- market date of the close
    fetched_at timestamptz not null default now()
);
