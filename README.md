# 가족 포트폴리오 — Family Portfolio Tracker

Private family portfolio dashboard. Flask + Supabase + yfinance. An **admin**
manages all data; **viewers** (family) see only their own data plus
family-shared stocks. Login is by private code — no email/password.

> **Status: Foundation pass.** Done: login-code auth, role-based access,
> holdings, transactions, ticker autocomplete. Not yet built (see
> `claude/TODO.md`): live prices, dashboard returns, charts, CSV upload, loans,
> settings.

## 1. Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
```

Generate a session key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Put it in `.env` as `SECRET_KEY`.

## 2. Create the Supabase project

1. Go to https://supabase.com → **New project**. Pick a name + database password.
2. In the project, open **Project Settings → API**:
   - copy **Project URL** → `.env` `SUPABASE_URL`
   - copy the **service_role** secret key → `.env` `SUPABASE_SERVICE_KEY`
     (this key is backend-only; never expose it client-side).
3. Open **SQL Editor → New query**, paste the contents of
   `migrations/001_init.sql`, and **Run**. This creates the 6 tables.

## 3. Generate the ticker autocomplete cache

```bash
python scripts/build_tickers.py
```

Pulls all KOSPI/KOSDAQ/KONEX listings (≈2,800) plus a curated US/ETF set into
`data/tickers.json`. Re-run anytime to refresh new listings.

## 4. Seed the family users + login codes

```bash
python scripts/seed_users.py
```

Prints four login codes **once** — save them and give one to each family
member. Only salted hashes are stored. Default users: 관리자 (admin), 어머니,
형제1, 형제2 (viewers). Rename display names in `scripts/seed_users.py`.
Re-run with `--reset` to wipe and regenerate.

## 5. Run locally

```bash
python run.py        # http://localhost:5000
```

Log in at `/login`. Admin can add holdings/transactions (with Korean ticker
autocomplete: type 삼성 → 삼성전자 005930.KS). Viewers are read-only and only
see their own data + family-shared holdings.

## 6. Deploy to Railway

1. Push this repo to GitHub.
2. Railway → **New Project → Deploy from GitHub repo**.
3. Add the same env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SECRET_KEY`,
   `FLASK_ENV=production`) in the Railway service **Variables**.
4. Railway uses the `Procfile` (`gunicorn run:app`) automatically.

## Project layout

```
app/            Flask app (factory, auth, routes, services, templates, static)
migrations/     Raw SQL to run in the Supabase SQL editor
scripts/        build_tickers.py, seed_users.py
data/           tickers.json (generated cache)
claude/         PROGRESS.md / TODO.md / DECISIONS.md — work log
```

## Security notes

- Login codes: stored as salted Werkzeug hashes; never in raw form.
- All write routes require `@admin_required`; viewer reads are scoped to the
  session user in `app/services/repo.py`. Changing a URL id cannot leak another
  user's private rows (returns 404).
- Sessions expire after `SESSION_DAYS` (default 7).
```
