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
    """Recompute the holdings table from scratch. Returns row count written.

    Transactions and intra-family transfers are merged into one dated event
    stream per (user, platform, ticker): a transfer the member RECEIVED is a
    seed buy at the giver's average cost, so later buys/sells (e.g. when an admin
    trades on a member's behalf) correctly add to / reduce the gifted position.
    The giver's side is applied afterwards and may go negative (a deficit).
    """
    c = get_client()
    sp = splits_svc.load_splits()

    # Per-position event stream: {date, side, qty, price, name, currency}.
    events: dict = defaultdict(list)
    groups: dict = defaultdict(list)
    for t in _fetch_transactions(c):
        groups[(t["user_id"], t["platform_id"], t["ticker"])].append(t)
    for key, trades in groups.items():
        for t in splits_svc.split_adjust(trades, sp):
            events[key].append({"date": t["trade_date"], "side": t["side"],
                                "qty": t["_qty"], "price": t["_price"],
                                "name": t["name"], "currency": t["currency"]})

    giver: list = []   # (key, qty, avg_cost, name, currency) — applied after, may go negative
    for t in (c.table("transfers").select("*").execute().data or []):
        qy = float(t["quantity"])
        if t["to_user_id"]:                             # received shares = seed buy (post-split)
            events[(t["to_user_id"], t["to_platform_id"], t["ticker"])].append(
                {"date": t.get("transfer_date") or "0000-01-01", "side": "buy",
                 "qty": qy, "price": float(t["avg_cost"]),
                 "name": t["name"], "currency": t["currency"]})
        if t["from_user_id"]:
            giver.append(((t["from_user_id"], t["from_platform_id"], t["ticker"]),
                          qy, float(t["avg_cost"]), t["name"], t["currency"]))

    pos: dict = {}
    for key, evs in events.items():
        evs.sort(key=lambda e: e["date"])
        q = avg = 0.0
        name = ccy = None
        for e in evs:
            name, ccy = e["name"], e["currency"]        # last by date wins
            qq, price = e["qty"], e["price"]
            if e["side"] == "buy":                       # weighted-average cost
                avg = (q * avg + qq * price) / (q + qq) if (q + qq) > EPS else price
                q += qq
            else:                                        # sell — clamp at zero (long only)
                q -= min(qq, q)
                if q < EPS:
                    q = avg = 0.0
        if abs(q) > EPS:
            pos[key] = {"name": name, "quantity": q, "avg_cost": avg, "currency": ccy}

    for key, qy, avg_cost, name, currency in giver:     # giver deficit (may go negative)
        p = pos.setdefault(key, {"name": name, "quantity": 0.0,
                                 "avg_cost": avg_cost, "currency": currency})
        p["quantity"] -= qy

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
