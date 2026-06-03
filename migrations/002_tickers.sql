-- Comprehensive ticker universe for autocomplete.
-- Run in the Supabase SQL editor (SQL Editor > New query > paste > Run).
-- Populated by scripts/build_tickers_db.py (US stocks + ETFs, KR stocks + ETFs).

create extension if not exists pg_trgm;   -- fast ILIKE '%...%' search

create table if not exists tickers (
    ticker   text primary key,          -- Yahoo ticker: AAPL, TQQQ, 005930.KS, 069500.KS
    name     text not null,             -- display name (Korean for KR, English for US)
    code     text,                      -- KR 6-digit code; null/empty for US
    market   text,                      -- KOSPI/KOSDAQ/KONEX/NASDAQ/NYSE/AMEX/ETF
    country  text not null,             -- 'KR' or 'US'
    type     text not null default 'stock'  -- 'stock' or 'etf'
);

-- Trigram indexes make partial-name / partial-ticker autocomplete fast.
create index if not exists idx_tickers_name_trgm   on tickers using gin (name gin_trgm_ops);
create index if not exists idx_tickers_ticker_trgm on tickers using gin (ticker gin_trgm_ops);
create index if not exists idx_tickers_code        on tickers (code);
