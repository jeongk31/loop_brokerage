-- Stock splits (corporate actions) + currency on holdings.
-- Run in the Supabase SQL editor (SQL Editor > New query > paste > Run).
--
-- IMPORTANT: run this in the SAME project your app uses (ref vnxfpsjbagdbmheomxzu).
-- If you get: ERROR 42P01 relation "holdings" does not exist  -> you are in the
-- wrong project; switch projects (top-left dashboard switcher) and re-run.
--
-- Strategy: transactions stay immutable/as-traded; splits live here and are
-- applied at derivation time (scripts/derive_holdings.py).

create table if not exists public.stock_splits (
    ticker  text not null,           -- Yahoo ticker (AAPL, TQQQ, 005930.KS, ...)
    ex_date date not null,           -- split effective date
    ratio   numeric not null,        -- 2.0 = 2-for-1 forward; 0.2 = 1-for-5 reverse
    source  text,                    -- 'seed' | 'yfinance' | 'sarwa' | 'manual'
    note    text,
    created_at timestamptz not null default now(),
    primary key (ticker, ex_date)
);

-- Holdings need a currency (KRW for Korean, USD for US) for value/return math.
alter table public.holdings add column if not exists currency text not null default 'KRW';
