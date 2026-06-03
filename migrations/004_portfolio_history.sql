-- Daily portfolio value series (precomputed) for the "value over time" chart.
-- Run in the Supabase SQL editor (same project: vnxfpsjbagdbmheomxzu).
-- Populated by scripts/build_portfolio_history.py; the daily cron appends today's row.

create table if not exists public.portfolio_history (
    snapshot_date date primary key,
    value_krw     numeric not null,
    computed_at   timestamptz not null default now()
);
