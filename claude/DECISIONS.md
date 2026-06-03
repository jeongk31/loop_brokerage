# Architecture Decisions

A running log of the choices we've locked in, so we don't re-litigate them.

| # | Decision | Choice | Notes |
|---|----------|--------|-------|
| 1 | Database | **Supabase from the start** | No local SQLite. |
| 2 | DB access from Flask | **supabase-py client** w/ **service role key** | Backend-only key; RBAC enforced in app code, not RLS (MVP). |
| 3 | Schema management | **Raw SQL in Supabase SQL editor** | Migration files in `migrations/`; user pastes them into Supabase. |
| 4 | Build scope | **Foundation first** | auth + RBAC + holdings + transactions + autocomplete. Rest later. |
| 5 | Ticker autocomplete | **Supabase `tickers` table** (was JSON file) | App queries Supabase via ILIKE (pg_trgm index) per keystroke. Comprehensive: ~15,602 rows. No runtime API/library calls. JSON-file + yfinance-fallback approach retired. |
| 5a | Ticker data sources | **4 free sources** | US stocks + ETFs (incl. leveraged) from api.nasdaq.com screener; KR stocks from KRX KIND; KR ETFs from Naver etfItemList. Loaded by `scripts/build_tickers_db.py`. US=symbol as-is; KR=<code>.<KS/KQ/KN>, KR ETFs=.KS. |
| 5b | data/tickers.json | **Kept only for build_summary.py** | Still used as the Korean name→ticker map when parsing 삼성증권 export. Not used by the live app anymore. |
| 6 | Auth | **Hashed login codes** (werkzeug) | Raw codes never stored; iterate users + check_password_hash (only 4 users). |
| 7 | Sessions | Flask signed session, 7-day expiry | `session.permanent = True`, `PERMANENT_SESSION_LIFETIME`. |
| 8 | Hosting | Railway (gunicorn via Procfile) | Deploy hardening is a later pass. |

| 9 | Stock splits | **Strategy A: immutable tx + `stock_splits` table, apply at derivation** | Transactions are never mutated (truthful to what was paid). Splits stored separately and applied when deriving holdings. Maintained BOTH ways: auto-refresh from yfinance (`scripts/refresh_splits.py`, runs in user's env / Railway) + admin-editable + seed for known splits. |
| 10 | Holdings | **Derived from ledger** (full reload) via `scripts/derive_holdings.py` | Average-cost method; handles shorts & zero-crossings; skips closed (~0) positions. Korean positions verified vs real 2026 Naver prices. `currency` column added to holdings. |
| 11 | Data completeness | **Reconcile derived vs actual** | Splits ≠ completeness. Some positions (e.g. Samsung TQQQ still nets short post-split) need the user's actual current holdings as an anchor to find missing history/transfers. Derivation flags non-IBKR shorts as suspicious. |

## Open items
- Supabase project + `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` must be supplied in local `.env`
  before the app can run end-to-end. README documents creating the project.
