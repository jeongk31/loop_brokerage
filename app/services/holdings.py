"""Re-derive holdings from transactions (+ splits, transfers). Long-only.

Called after any transaction/holding change so the app stays in sync (no need to
wait for the daily cron). Mirrors scripts/derive_holdings.py.
"""
from collections import defaultdict

from ..db import get_client
from . import splits as splits_svc

EPS = 1e-6


def _fetch_transactions(c) -> list[dict]:
    rows, start = [], 0
    while True:
        page = (c.table("transactions")
                .select("user_id,platform_id,ticker,name,trade_date,side,quantity,price,currency")
                .range(start, start + 999).execute().data or [])
        rows += page
        if len(page) < 1000:
            break
        start += 1000
    return rows


def rederive() -> int:
    """Recompute the holdings table from scratch. Returns row count written."""
    c = get_client()
    sp = splits_svc.load_splits()
    groups: dict = defaultdict(list)
    for t in _fetch_transactions(c):
        groups[(t["user_id"], t["platform_id"], t["ticker"])].append(t)

    pos: dict = {}
    for (u, pl, tk), trades in groups.items():
        adj = splits_svc.split_adjust(trades, sp)
        adj.sort(key=lambda x: x["trade_date"])
        q = avg = 0.0
        for t in adj:
            qq, price = t["_qty"], t["_price"]
            if t["side"] == "buy":                      # weighted-average cost
                avg = (q * avg + qq * price) / (q + qq) if (q + qq) > EPS else price
                q += qq
            else:                                       # sell — clamp at zero (long only)
                q -= min(qq, q)
                if q < EPS:
                    q = avg = 0.0
        if abs(q) > EPS:
            last = max(trades, key=lambda x: x["trade_date"])
            pos[(u, pl, tk)] = {"name": last["name"], "quantity": q,
                                "avg_cost": avg, "currency": last["currency"]}

    # intra-family transfers (giver may go negative)
    for t in (c.table("transfers").select("*").execute().data or []):
        qy = float(t["quantity"])
        if t["from_user_id"]:
            p = pos.setdefault((t["from_user_id"], t["from_platform_id"], t["ticker"]),
                               {"name": t["name"], "quantity": 0.0,
                                "avg_cost": float(t["avg_cost"]), "currency": t["currency"]})
            p["quantity"] -= qy
        if t["to_user_id"]:
            key = (t["to_user_id"], t["to_platform_id"], t["ticker"])
            p = pos.get(key)
            if p:
                tot = p["quantity"] + qy
                p["avg_cost"] = ((p["quantity"] * p["avg_cost"] + qy * float(t["avg_cost"])) / tot) if tot else float(t["avg_cost"])
                p["quantity"] = tot
            else:
                pos[key] = {"name": t["name"], "quantity": qy,
                            "avg_cost": float(t["avg_cost"]), "currency": t["currency"]}

    holdings = [
        {"user_id": u, "platform_id": pl, "ticker": tk, "name": v["name"],
         "quantity": round(v["quantity"], 8), "avg_cost": round(v["avg_cost"], 6),
         "currency": v["currency"], "is_family_shared": False}
        for (u, pl, tk), v in pos.items() if abs(v["quantity"]) > EPS
    ]
    c.table("holdings").delete().neq("ticker", "").execute()
    for i in range(0, len(holdings), 200):
        c.table("holdings").insert(holdings[i:i + 200]).execute()
    return len(holdings)
