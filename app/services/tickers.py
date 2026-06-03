"""Ticker autocomplete — backed by the Supabase `tickers` table.

The table is populated by scripts/build_tickers_db.py (US stocks + ETFs, KR
stocks + ETFs ≈ 15.6k rows). Search matches Korean/English name, Yahoo ticker,
or KR code (partial, case-insensitive) via Postgres ILIKE with a trigram index.
"""
import re

from ..db import get_client

# Strip characters that would break a PostgREST or()/ilike filter.
_SANITIZE = re.compile(r"[,()*%\\]")


def _label(rec: dict) -> str:
    return f"{rec['name']} — {rec['ticker']}"


def search(query: str, limit: int = 10) -> list[dict]:
    """Return [{label, ticker, name, code}] for the query."""
    q = _SANITIZE.sub(" ", (query or "")).strip()
    if not q:
        return []

    pat = f"*{q}*"
    try:
        resp = (
            get_client()
            .table("tickers")
            .select("ticker, name, code, type, country")
            .or_(f"name.ilike.{pat},ticker.ilike.{pat},code.ilike.{pat}")
            .limit(40)
            .execute()
        )
    except Exception:  # noqa: BLE001 — table missing / network: fail soft
        return []

    hits = resp.data or []
    ql = q.lower()

    def rank(r: dict) -> tuple:
        code = (r.get("code") or "").lower()
        ticker = (r.get("ticker") or "").lower()
        name = (r.get("name") or "").lower()
        exact = 0 if ql in (code, ticker) else 1
        prefix = 0 if name.startswith(ql) or ticker.startswith(ql) else 1
        return (exact, prefix, len(name))

    hits.sort(key=rank)
    return [
        {
            "label": _label(r),
            "ticker": r["ticker"],
            "name": r["name"],
            "code": r.get("code") or "",
        }
        for r in hits[:limit]
    ]
