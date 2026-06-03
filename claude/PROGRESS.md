# Progress Log

Dated log of what's actually done. Newest first.

## 2026-06-03 — Foundation pass ✅ (code complete; needs user's Supabase to run live)
- Confirmed architecture decisions (see `DECISIONS.md`).
- Created project structure + tracking docs.
- **Schema:** `migrations/001_init.sql` — users, platforms, holdings, transactions,
  loans, price_cache (raw SQL for Supabase editor).
- **Flask app:** factory (`app/__init__.py`), env config, Supabase client singleton.
- **Auth/RBAC:** hashed login codes, session (7-day expiry), `login_required` /
  `admin_required`; `scripts/seed_users.py` generates 4 codes.
- **Ticker autocomplete:** pykrx was unusable (now requires KRX login creds), so
  switched source to the **KRX KIND public listing endpoint** via
  `scripts/build_tickers.py`. Generated `data/tickers.json` = 2,786 tickers
  (2,764 KRX + 22 US). Service does cache-first search + yfinance live fallback +
  append-on-miss. Verified: 삼성→삼성전자, 하이닉스→SK하이닉스, 두산→두산로보틱스 etc.
- **Holdings + transactions:** scoped `repo.py`, admin CRUD routes, viewer read-only,
  templates + mobile CSS with Korean labels, JS autocomplete widget on forms.
- **Verified (no Supabase needed):** app builds, all 12 routes register, `/login`
  renders, protected routes 302→login, `/api/tickers/search` returns correct JSON
  for a logged-in user, all Python compiles cleanly.
- **NOT verified yet (needs Supabase):** real login by code, holdings/transactions
  CRUD, viewer scoping against live rows. User must do the Supabase setup steps.

### Key decision change this pass
- Ticker source: **pykrx → KRX KIND endpoint** (pykrx 1.2.6 now needs KRX_ID/KRX_PW).
  No credentials needed for KIND. Logged in `DECISIONS.md`.

## 2026-06-03 — Combined starting-data summary
- User dropped real broker exports into `STARTING_DATA/`: `IBKR.csv` (Interactive
  Brokers, partial history 2026-04-16+), `삼성증권.xlsx` (full history since 2010),
  and gave 한국투자증권 holdings by hand.
- Wrote `scripts/build_summary.py` → merges all three into **`STARTING_DATA/summary.csv`**,
  one row per real stock BUY/SELL. **590 transactions** (삼성 561 + IBKR 27 + 한투 2),
  56 distinct tickers. Forex/deposits/dividends/taxes/fees/interest dropped (prices only).
- **Currency rule:** Korean stocks → KRW; US stocks → USD (Samsung records US trades
  natively in USD; 한투 TQQQ converted 32,914.5원 ÷ USDKRW 1427.76 = $23.05).
- **Name→ticker mapping:** Korean names via `data/tickers.json`; manual maps in
  build_summary.py for 18 US names, KODEX ETFs, preferred shares (삼성전자우/현대차우),
  SK렌터카, and 현대차 (KIND lists it as 현대자동차).
- **Corrected 한투 prices** (user's original 대우건설 numbers were unrealistic):
  대우건설 = 5,210원 (Naver close 2022-08-02); TQQQ = $23.05.
- yfinance was rate-limited → sourced 대우건설 close from Naver, USDKRW from ECB/Frankfurter.

### IBKR note (resolved)
- The net-negative positions (more sells than buys) are **intentional short positions**,
  not a partial export. IBKR rows are correct as-is.

## 2026-06-03 — Family carve-out, cash, person toggle, LOOP 증권 rebrand
- **Rebrand → "LOOP 증권"** (brand + tab title); footer "powered by" + `static/logo.png`
  (Loop Dimension wordmark) on a dark strip.
- **Family carve-out (total conserved)** via new `transfers` table (migration 005):
  shares move 이정규→family at 이정규's avg cost, applied after derivation (giver can go
  negative). Gave 이지안 QLD 5, 이정한 TQQQ 80, 엄마 TQQQ 31 + NASA 10. 이정규 삼성 TQQQ →
  **−69** (deficit to buy back). Grand total holdings unchanged at ₩37,415,064; total TQQQ
  still 46. `scripts/seed_family.py` rewritten to create transfers + cash.
  `derive_holdings` applies transfers, keeps negatives, full-reload.
- **Cash** (migration 005 `cash_balances`): USD/KRW per family member (not 이정규).
  Included in 총 자산 (이정한 $5,400, 엄마 $2,520 → ₩12.0M). Admin edits in Settings 현금 section.
  총 자산 now ₩49,430,892 (holdings ₩37.4M + cash ₩12.0M).
- **보유종목 person toggle** on dashboard (전체 / 이정규 / 엄마 / 이정한 / 이지안), client-side,
  like 자산 배분. Holdings now live on dashboard grouped by owner→증권사.
- KODEX 조선TOP10 ticker fixed (0115D0.KS) + long-only clamp from prior round retained.

## 2026-06-03 — Accuracy audit + fixes
- Audited master CSV vs sources vs DB: counts reconcile exactly (705); **Sarwa holdings
  snapshot (May 2026: QLD 5 @ $92.15) matches derivation exactly** — methodology validated.
- **BUG FIX 1 — KODEX 조선TOP10 wrong ticker**: was 494670.KS (= TIGER 조선TOP10, ₩28,375),
  corrected to **0115D0.KS** (₩9,875). Fake +169%/₩2.8M → real −₩66k. This was the price
  inaccuracy. Fixed in build_summary KR_OVERRIDE; pipeline re-run.
- **BUG FIX 2 — long-only holdings**: user never shorts. Replaced crossing logic with
  clamp-at-zero in `derive_holdings.replay` + `build_portfolio_history`. TQQQ 삼성 now **42**
  (matches user's app), not 34. QLD 15 ✓, Korean positions unchanged.
- Confirmed with user: 삼성 = QLD 15, TQQQ 42, + Korean stocks. 총 자산 ₩37.4M.
- Rebrand: "LEE Family Office" → **"LEE 자산"** (all templates).

### Built (this round)
- **Realized P/L** (`portfolio.realized_pl`, avg-cost on sells, split-adjusted): dashboard
  card (평가손익 미실현 + 실현손익) + `/realized` page (합계, by currency, 증권사별, 종목별).
  Total ₩27.4M (USD $17.6k + KRW ₩637k). USD→KRW at current FX (flagged).
- **보유종목 per 증권사**: grouped by platform w/ subtotals. Later consolidated ONTO the
  dashboard (all holdings listed inline, grouped); separate 보유종목 page/nav removed,
  /holdings redirects to dashboard. `portfolio.group_by_platform()` shared helper.
- **전체/본인 scope toggle** in topbar (admin): `auth.view_scope()` + `/scope/<mode>`;
  threaded through holdings/transactions/charts/realized/dashboard repo queries.
  (value-over-time chart stays family-total, admin only.)

## 2026-06-03 — UI overhaul + rebrand + ORCL/shorts removal
- Renamed users to real names: 이정규 (admin), 엄마/이정한/이지안 (viewers). OWNER in
  build_summary → 이정규.
- **Removed ORCL entirely + dropped the "short" concept** (user won't short). EXCLUDE_TICKERS
  in build_summary; full pipeline re-run → 705 tx, 19 holdings, 0 shorts. Removed 숏 badge,
  is_short field, suspicious-shorts flagging. Total assets ₩17M → **₩38.2M** (−₩21M ORCL
  liability gone; IBKR now +₩15.2M).
- Rebrand: **"가족 포트폴리오" → "LEE Family Office"** (topbar wordmark + avatar, login).
- Full CSS redesign: dark navy topbar, soft-shadow cards, hero gradient stat, refined
  tables/badges/buttons/forms, mobile-friendly.
- Dashboard now has charts: 총 자산 추이 line + 자산 배분 donut with a **증권사별 / 종목별 /
  시장별 toggle**. portfolio.history_series() shared helper.
- Note: active sessions cache display_name → name updates on next login (cosmetic).

## 2026-06-03 — Portfolio value over time (FEATURE-COMPLETE)
- `migrations/004_portfolio_history.sql`: `portfolio_history` table (run by user).
- `scripts/build_portfolio_history.py`: reconstructs daily value (split-adjusted qty-as-of-date
  × Naver adjusted close × daily Frankfurter FX) → 2,122 snapshots. Last day = live total
  (₩17,055,778) ✓ cross-check.
- `/charts`: 총 자산 추이 line (admin only; paginated read + downsampled to ~500 pts).
- All MVP features now built. Remaining: Railway deploy + daily cron (appends snapshot).

## 2026-06-03 — Charts
- `routes/charts.py` + `charts.html` (Chart.js CDN) + nav link: platform allocation donut,
  국내/해외 donut, top-10 holdings bar, interactive per-stock price line.
- `prices.history(ticker, days)` (Naver KR siseJson / US chart endpoint w/ suffix probe).
- `/api/price-history` endpoint. Verified live: page renders, API returns series.
- Deferred: portfolio-value-over-time (needs historical qty×price reconstruction).

## 2026-06-03 — Settings (admin)
- `routes/settings.py` + `settings.html` + nav link (admin only): rename family members,
  regenerate login codes (new code shown once, hashed), add/rename platforms.
- `auth.gen_code()` helper extracted. Verified: admin renders, viewers 403 on read+write.

## 2026-06-03 — Loans + net worth (순자산)
- Admin-only loans CRUD: `routes/loans.py`, repo loan helpers, `loans.html` + `loan_form.html`,
  nav link (admin only). Loan summary: 잔액 합계 + 월 상환액 합계.
- Dashboard (admin): 순자산 = 총 자산 − 대출 잔액; loan-balance card.
- Verified live: create/list works, net worth computes, viewers get 403 on /loans.

## 2026-06-03 — Prices + dashboard valuation
- `app/services/prices.py`: current prices via **Naver** (KR via siseJson, US via
  api.stock.naver.com basic w/ suffix probe .O/.K/.A/bare), FX USD/KRW via Frankfurter.
  Cached in `price_cache`. (yfinance blocked in sandbox → Naver chosen; testable + reliable.)
- `scripts/refresh_prices.py`: refresh price_cache for held tickers + FX (17/17 ok).
- `app/services/portfolio.py`: enrich holdings (current price, value, P/L, return %) +
  portfolio summary; USD→KRW conversion for unified totals.
- Dashboard + holdings pages rebuilt: 총 자산 / 매수원가 / 평가손익 / 수익률, platform
  breakdown, per-holding live valuation, red=gain/blue=loss, admin '시세 새로고침' button.
- Verified live (port 5001): 총 자산 ₩17,055,778, P/L +₩4,788,677 (+39.0%), USD/KRW 1517.
- price source = Naver (per env constraint); swap to yfinance later if desired.

## 2026-06-03 — Comprehensive split research + holdings fixed
- Researched ALL splits (2019–2026) for every traded ticker via 3 parallel web agents.
- Loaded **25 splits** into `stock_splits` (source='research'): incl. TQQQ 3×
  (2021-01-21, 2022-01-13, 2025-11-20), QLD 3×, SQQQ reverse ×5, USO 1:8 reverse,
  FCEL reverse ×2, AAPL/AMZN/GOOGL/NVDA/TSLA, 카카오 5:1, 리노공업 5:1,
  HPSP/현대바이오 무상증자.
- Key fix: TQQQ had a **Nov 20 2025 2:1 split** I'd missed → 삼성 TQQQ −193 (phantom
  short) corrected to **+34 long**. No suspicious shorts remain.
- Re-derived: 20 open holdings, 19 long + 1 (real IBKR ORCL) short.
- `derive_holdings.py` now reads splits from the table; `refresh_splits.py` SEED holds
  the researched set + pulls authoritative history from yfinance when run outside the sandbox.

## 2026-06-03 — Comprehensive ticker DB in Supabase
- Replaced the JSON-file autocomplete with a Supabase `tickers` table.
- `migrations/002_tickers.sql` (user ran it): `tickers` table + pg_trgm indexes.
- `scripts/build_tickers_db.py` fetches & upserts 4 universes → **15,602 unique tickers**:
  US stocks 7,150 + US ETFs 4,552 (incl. leveraged) + KR stocks 2,764 + KR ETFs 1,136.
- Sources: api.nasdaq.com screener (stocks/etf), KRX KIND, Naver etfItemList.
- Rewrote `app/services/tickers.py` → queries Supabase via ILIKE (name/ticker/code),
  ranks in Python. No runtime API/library calls.
- Verified live (port 5001, authed): SOXL → Direxion Semi Bull 3X; 두산로보 → 454910.KS.
- Note: US stocks stored with **English names**, so Korean-name search finds KR names
  only; US stocks are searched by English name or ticker (expected).

## 2026-06-03 — Live on Supabase + data imported
- Fixed `.env`: SUPABASE_URL was the dashboard URL → corrected to API URL
  `https://vnxfpsjbagdbmheomxzu.supabase.co`; generated a real SECRET_KEY.
- Connection verified; user ran `migrations/001_init.sql` → 6 tables created.
- `scripts/seed_users.py` → 4 users created (관리자 admin + 어머니/형제1/형제2 viewers).
  Codes given to user once (not stored here).
- Wrote `scripts/import_summary.py` → imported all **713 transactions** from
  `summary.csv`; auto-created platforms (IBKR, Sarwa, 삼성증권, 한국투자증권), mapped
  owner 관리자 → admin user. Full-reload semantics (deletes existing tx for those
  platforms first), so it's safe to re-run.
- Verified 713 rows in DB + FK joins (platforms/users) resolve.
- Holdings table still empty — next step is deriving net holdings from the ledger.

## 2026-06-03 — Added Sarwa
- User added 32 Sarwa monthly statement PDFs in `STARTING_DATA/sarwa/`.
- Extended `scripts/build_summary.py` with `parse_sarwa()`: PyMuPDF `find_tables()` on
  each statement's "Transaction" section, keeping only `Trade Entry` buy/sell rows
  (cash sweeps, stock splits, dividends, interest dropped). All USD.
- Wrote `STARTING_DATA/sarwa.csv` (123 trades, 10 tickers: AAPL AMZN BND META NVDA
  PLTR QLD TIP TQQQ USO; 2023-10 → 2026-05) and merged into `summary.csv`.
- Verified: 32 PDFs = 32 distinct months (no duplicate-month double counting).
- **summary.csv now 713 transactions:** 삼성 561 + Sarwa 123 + IBKR 27 + 한투 2.
- Note: PyMuPDF (fitz) is now a dependency for build_summary — added to requirements.
