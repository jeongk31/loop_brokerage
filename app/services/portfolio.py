"""Valuation: combine holdings with cached prices + FX into value / P&L / returns.

All cross-currency totals are expressed in KRW (USD holdings converted at the
cached USD/KRW rate). Per-holding figures stay in the holding's native currency.
"""
from collections import defaultdict

from . import prices
from . import splits as splits_svc
from ..db import get_client


def realized_pl(transactions: list[dict], fx: float) -> dict:
    """Realized gain/loss from sells (average-cost), split-adjusted.

    Realized P/L is split-invariant. Computed in each position's native currency,
    then combined to KRW at the current FX (a simplification — USD realized would
    ideally use trade-date FX; flagged in the UI).
    Returns: {total_krw, by_currency, by_platform, rows}.
    """
    sp = splits_svc.load_splits()
    groups: dict = defaultdict(list)
    for t in transactions:
        groups[(t.get("platform_id"), t["ticker"])].append(t)

    by_ccy: dict = defaultdict(float)
    by_plat: dict = defaultdict(float)
    rows = []
    for (_pid, ticker), trades in groups.items():
        adj = splits_svc.split_adjust(trades, sp)
        adj.sort(key=lambda x: x["trade_date"])
        qty = avg = realized = 0.0
        ccy = trades[0].get("currency") or prices.native_currency(ticker)
        plat = (trades[0].get("platforms") or {}).get("name", "?")
        name = trades[0].get("name", ticker)
        for t in adj:
            q, price = t["_qty"], t["_price"]
            if t["side"] == "buy":
                avg = ((qty * avg + q * price) / (qty + q)) if (qty + q) else price
                qty += q
            else:  # sell — realize against running average cost
                sold = min(q, qty) if qty > 0 else 0
                realized += (price - avg) * sold
                qty -= sold
        if abs(realized) > 1e-6:
            by_ccy[ccy] += realized
            krw = realized if ccy == "KRW" else realized * (fx or 0)
            by_plat[plat] += krw
            rows.append({"ticker": ticker, "name": name, "platform": plat,
                         "currency": ccy, "realized": realized, "realized_krw": krw})

    total_krw = by_ccy.get("KRW", 0.0) + by_ccy.get("USD", 0.0) * (fx or 0)
    rows.sort(key=lambda r: r["realized_krw"])
    return {
        "total_krw": total_krw,
        "by_currency": dict(by_ccy),
        "by_platform": sorted(by_plat.items(), key=lambda x: x[1]),
        "rows": rows,
    }


def user_history(enriched: list[dict], cash_total_krw: float, fx: float, days: int = 180):
    """Value-over-time for a member whose holdings are static (transferred once):
    current qty x daily close (+ constant cash). (dates, values) in KRW."""
    import pandas as pd

    held = [h for h in enriched if h.get("current_price") is not None and float(h["quantity"])]
    if not held:
        return [], []
    axis = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days, freq="D")
    total = pd.Series(float(cash_total_krw), index=axis)
    for h in held:
        hist = prices.history(h["ticker"], days=days + 15)
        if not hist:
            continue
        close = pd.Series({pd.Timestamp(p["date"]): p["close"] for p in hist}).reindex(axis).ffill().bfill()
        val = float(h["quantity"]) * close
        if h["currency"] == "USD":
            val = val * (fx or 0)
        total = total.add(val.fillna(0), fill_value=0)
    step = max(1, len(total) // 400)
    pts = list(total.items())[::step]
    return ([d.date().isoformat() for d, _ in pts], [round(float(v)) for _, v in pts])


def history_series(max_points: int = 500):
    """(dates, values) from portfolio_history — paginated + downsampled. ([],[]) if none."""
    try:
        rows, start = [], 0
        while True:
            page = (get_client().table("portfolio_history")
                    .select("snapshot_date, value_krw").order("snapshot_date")
                    .range(start, start + 999).execute().data or [])
            rows += page
            if len(page) < 1000:
                break
            start += 1000
    except Exception:  # noqa: BLE001
        return [], []
    if not rows:
        return [], []
    step = max(1, len(rows) // max_points)
    sampled = rows[::step]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    return ([r["snapshot_date"] for r in sampled],
            [round(float(r["value_krw"])) for r in sampled])


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def enrich(holdings: list[dict], cache: dict, fx: float) -> list[dict]:
    """Add current_price, value, cost_basis, pl, return_pct, value_krw to each holding."""
    out = []
    for h in holdings:
        qty, avg = _f(h["quantity"]), _f(h["avg_cost"])
        ccy = h.get("currency") or prices.native_currency(h["ticker"])
        prow = cache.get(h["ticker"])
        price = _f(prow["price"]) if prow else None

        cost = qty * avg
        value = qty * price if price is not None else None
        pl = (value - cost) if value is not None else None
        ret = (pl / abs(cost) * 100) if (pl is not None and cost) else None
        to_krw = (lambda v: v if ccy == "KRW" else v * fx) if fx else (lambda v: v)

        out.append({
            **h,
            "currency": ccy,
            "current_price": price,
            "as_of": prow["as_of"] if prow else None,
            "cost_basis": cost,
            "value": value,
            "pl": pl,
            "return_pct": ret,
            "value_krw": to_krw(value) if value is not None else None,
            "cost_krw": to_krw(cost),
            "stale": prow is None,
        })
    return out


def summary(enriched: list[dict], fx: float) -> dict:
    """Portfolio totals in KRW + per-platform / per-currency breakdowns."""
    total_value = sum(h["value_krw"] for h in enriched if h["value_krw"] is not None)
    total_cost = sum(h["cost_krw"] for h in enriched)
    pl = total_value - total_cost
    ret = (pl / abs(total_cost) * 100) if total_cost else None

    by_platform: dict = {}
    by_currency: dict = {}
    for h in enriched:
        plat = (h.get("platforms") or {}).get("name", "?")
        by_platform.setdefault(plat, 0.0)
        if h["value_krw"] is not None:
            by_platform[plat] += h["value_krw"]
        by_currency.setdefault(h["currency"], 0.0)
        if h["value_krw"] is not None:
            by_currency[h["currency"]] += h["value_krw"]

    return {
        "total_value_krw": total_value,
        "total_cost_krw": total_cost,
        "total_pl_krw": pl,
        "return_pct": ret,
        "fx": fx,
        "by_platform": sorted(by_platform.items(), key=lambda x: -x[1]),
        "by_currency": sorted(by_currency.items(), key=lambda x: -x[1]),
        "any_stale": any(h["stale"] for h in enriched),
    }


def group_by_platform(enriched: list[dict]) -> list[dict]:
    """Group enriched holdings by 증권사 with per-platform subtotals (value + P/L)."""
    by_plat: dict = {}
    for h in enriched:
        plat = (h.get("platforms") or {}).get("name", "기타")
        by_plat.setdefault(plat, []).append(h)
    grouped = []
    for plat, hs in by_plat.items():
        val = sum(h["value_krw"] or 0 for h in hs)
        cost = sum(h["cost_krw"] for h in hs)
        grouped.append({"platform": plat, "holdings": hs, "value_krw": val,
                        "pl_krw": val - cost})
    grouped.sort(key=lambda g: -g["value_krw"])
    return grouped


def group_by_owner(enriched: list[dict]) -> list[dict]:
    """Group enriched holdings by owner, each with platform sub-groups + totals."""
    by_owner: dict = {}
    for h in enriched:
        owner = (h.get("users") or {}).get("display_name", "?")
        by_owner.setdefault(owner, []).append(h)
    out = []
    for owner, hs in by_owner.items():
        val = sum(h["value_krw"] or 0 for h in hs)
        cost = sum(h["cost_krw"] for h in hs)
        out.append({"owner": owner, "grouped": group_by_platform(hs),
                    "value_krw": val, "pl_krw": val - cost})
    out.sort(key=lambda o: -o["value_krw"])
    return out


def load_cash(user_ids: list[str], fx: float) -> dict:
    """Cash for the given users: {by_currency, total_krw}.

    Always reports both KRW and USD (0 when absent) so members consistently see
    each currency balance.
    """
    by_ccy: dict = {"KRW": 0.0, "USD": 0.0}
    if user_ids:
        rows = (get_client().table("cash_balances").select("currency, amount")
                .in_("user_id", user_ids).execute().data or [])
        for r in rows:
            by_ccy[r["currency"]] = by_ccy.get(r["currency"], 0.0) + float(r["amount"])
    total = by_ccy.get("KRW", 0.0) + by_ccy.get("USD", 0.0) * (fx or 0)
    return {"by_currency": by_ccy, "total_krw": total}


def load_view(holdings: list[dict]) -> tuple[list[dict], dict]:
    """Convenience: read price_cache + FX, return (enriched_holdings, summary)."""
    cache = prices.get_cached()
    fx = _f(cache.get(prices.FX_KEY, {}).get("price")) or None
    enriched = enrich(holdings, cache, fx)
    enriched.sort(key=lambda h: -(h["value_krw"] or 0))
    return enriched, summary(enriched, fx)
