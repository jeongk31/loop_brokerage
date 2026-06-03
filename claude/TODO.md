# TODO

## DONE
- [x] Flask app: factory, config, Supabase client, login-code auth + RBAC
- [x] Transactions + holdings routes/repo/templates, mobile CSS
- [x] Comprehensive ticker DB in Supabase (`tickers`, ~15.6k) + autocomplete via ILIKE
- [x] Supabase live: migrations 001/002/003 run, 4 users seeded
- [x] Starting data: `summary.csv` (713 tx) from 삼성/IBKR/Sarwa/한투 → imported
- [x] Splits strategy A: `stock_splits` table + `refresh_splits.py` + apply-at-derivation
- [x] Researched & loaded 25 splits (2019–26) for all traded tickers; TQQQ short fixed
- [x] Holdings derived & populated (20 open positions)

## Prices + dashboard — DONE
- [x] `app/services/prices.py`: current price via Naver (KR + US), `price_cache`
- [x] USD→KRW FX (Frankfurter) for unified totals
- [x] Holdings page: current price, value, unrealized P/L, return % per holding
- [x] Dashboard: 총 자산 / 평가금액 / 평가손익 / 수익률 + platform breakdown + 시세 새로고침
- [x] `scripts/refresh_prices.py` (will join the daily cron)

## DEPLOYMENT PASS (Railway) — includes the maintenance cron
- [ ] Deploy to Railway (Procfile/gunicorn, env vars, secure cookies, HTTPS)
- [ ] **Daily cron job** (`scripts/daily_update.py`) running ALL of:
      1. `refresh_splits.py`        — pull new splits from yfinance (works on Railway)
      2. `derive_holdings.py`       — re-derive holdings (splits change share counts)
      3. `refresh_prices.py`        — update `price_cache` for held tickers + FX rate
      4. `build_portfolio_history.py` — append today's snapshot to portfolio_history
      (idempotent; future splits, daily prices, and the value-over-time chart all stay current)
- [ ] Admin "Add split / Recompute holdings" controls (manual backstop)
- [ ] Optional: split-detection nudge (overnight ~2x price move on a held ticker)

## LATER FEATURES
- [x] Charts: platform allocation (donut), 국내/해외 (donut), top holdings (bar), per-stock price history (line, Naver)
- [x] Chart: **portfolio value over time** — `portfolio_history` table + `build_portfolio_history.py`; 2,122 daily snapshots, downsampled in chart; last day matches live total ✓
- [~] CSV upload UI — SKIPPED (one-time load already done via scripts; no UI needed per user)
- [x] Loan tracking CRUD + net-worth-after-loans (순자산) on dashboard (admin only)
- [x] Settings: rename users, regenerate login codes, manage platform names (admin only)

## OPEN DATA ITEMS
- [ ] Run `refresh_splits.py` once from your own machine to confirm yfinance matches the 25 researched splits
- [ ] Confirm `owner` per platform (all currently 관리자) — reassign if any belong to a family member
- [ ] IBKR ORCL −57 is a real (confirmed) short; all other positions reconciled
