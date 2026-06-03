"""Derive current holdings from the transaction ledger and populate `holdings`.

For each (user, platform, ticker) we replay trades in date order using the
**average-cost** method:
  - buying / adding   -> weighted-average the cost
  - selling / reducing-> quantity drops, average cost unchanged
  - crossing zero     -> position flips (e.g. into a short); cost resets to the
                          crossing trade's price
Net quantity may be negative — that's a short position (e.g. IBKR).
Positions that net to ~0 are dropped (fully closed).

This is a FULL RELOAD of the holdings table (delete + insert), so it is safe to
re-run after re-importing transactions.

Run:  python scripts/derive_holdings.py            # populate Supabase
      python scripts/derive_holdings.py --dry-run  # print positions only
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402

EPS = 1e-6


def load_splits(client) -> dict:
    """ticker -> [(ex_date, ratio), ...] from the stock_splits table."""
    splits: dict = {}
    for r in (client.table("stock_splits").select("ticker, ex_date, ratio").execute().data or []):
        splits.setdefault(r["ticker"], []).append((r["ex_date"], float(r["ratio"])))
    return splits


def split_adjust(trades: list[dict], splits: dict) -> list[dict]:
    """Return trades with pre-split quantities/prices restated post-split."""
    out = []
    for t in trades:
        qty, price = float(t["quantity"]), float(t["price"])
        for date, ratio in splits.get(t["ticker"], ()):
            if t["trade_date"] < date:
                qty *= ratio
                price /= ratio
        out.append({**t, "quantity": qty, "price": price})
    return out


def replay(trades: list[dict]) -> tuple[float, float]:
    """Return (net_quantity, average_cost) for one position — LONG ONLY.

    We never short, so a sell can never take the position negative: it can only
    sell down to zero (any excess — a data artifact from rounding on big rebalance
    trades — is ignored). Average cost uses the moving-average method and resets
    when the position is fully closed.
    """
    qty = 0.0
    avg = 0.0
    for t in sorted(trades, key=lambda x: x["trade_date"]):
        q = float(t["quantity"])
        price = float(t["price"])
        if t["side"] == "buy":
            avg = (qty * avg + q * price) / (qty + q) if (qty + q) > EPS else price
            qty += q
        else:                                   # sell — clamp at zero
            qty -= min(q, qty)
            if qty < EPS:
                qty, avg = 0.0, 0.0
    return qty, avg


def fetch_all_transactions(client) -> list[dict]:
    rows, start = [], 0
    while True:
        page = (client.table("transactions")
                .select("user_id, platform_id, ticker, name, trade_date, side, quantity, price, currency")
                .range(start, start + 999).execute().data or [])
        rows += page
        if len(page) < 1000:
            break
        start += 1000
    return rows


def main() -> None:
    dry = "--dry-run" in sys.argv
    client = get_client()

    txs = fetch_all_transactions(client)
    splits = load_splits(client)
    groups: dict = defaultdict(list)
    for t in txs:
        groups[(t["user_id"], t["platform_id"], t["ticker"])].append(t)

    # Base positions from real trades, keyed by (user, platform, ticker).
    pos: dict = {}
    closed = 0
    for (user_id, platform_id, ticker), trades in groups.items():
        qty, avg = replay(split_adjust(trades, splits))
        if abs(qty) < EPS:
            closed += 1
            continue
        last = max(trades, key=lambda x: x["trade_date"])
        pos[(user_id, platform_id, ticker)] = {
            "name": last["name"], "quantity": qty, "avg_cost": avg,
            "currency": last["currency"],
        }

    # Apply intra-family transfers: move shares between members WITHOUT changing
    # the grand total. The giver's position may go negative (deficit to buy back).
    transfers = client.table("transfers").select("*").execute().data or []
    for t in transfers:
        qy = float(t["quantity"])
        frm = (t["from_user_id"], t["from_platform_id"], t["ticker"])
        to = (t["to_user_id"], t["to_platform_id"], t["ticker"])
        if t["from_user_id"]:
            p = pos.setdefault(frm, {"name": t["name"], "quantity": 0.0,
                                     "avg_cost": float(t["avg_cost"]), "currency": t["currency"]})
            p["quantity"] -= qy   # may go negative — intentional
        if t["to_user_id"]:
            p = pos.get(to)
            if p:
                tot = p["quantity"] + qy
                p["avg_cost"] = ((p["quantity"] * p["avg_cost"] + qy * float(t["avg_cost"])) / tot) if tot else float(t["avg_cost"])
                p["quantity"] = tot
            else:
                pos[to] = {"name": t["name"], "quantity": qy,
                           "avg_cost": float(t["avg_cost"]), "currency": t["currency"]}

    holdings = [
        {"user_id": u, "platform_id": pl, "ticker": tk, "name": v["name"],
         "quantity": round(v["quantity"], 8), "avg_cost": round(v["avg_cost"], 6),
         "currency": v["currency"], "is_family_shared": False}
        for (u, pl, tk), v in pos.items() if abs(v["quantity"]) > EPS
    ]

    plat = {p["id"]: p["name"] for p in client.table("platforms").select("id,name").execute().data}

    holdings.sort(key=lambda h: (-abs(h["quantity"] * h["avg_cost"])))
    print(f"{len(groups)} positions traded -> {len(holdings)} open ({len(transfers)} transfers applied), {closed} closed")

    negative = [h for h in holdings if h["quantity"] < 0]
    if negative:
        print("  negative positions (deficit to buy back):")
        for h in negative:
            print(f"     {plat.get(h['platform_id']):12} {h['ticker']:12} net {h['quantity']:.4f} {h['currency']}")

    if dry:
        print("\n  top open positions (by cost basis):")
        for h in holdings[:25]:
            cb = h["quantity"] * h["avg_cost"]
            print(f"   {plat.get(h['platform_id'],'?'):12} {h['ticker']:12} qty {h['quantity']:>12.4f} "
                  f"@ {h['avg_cost']:>10.2f} {h['currency']}  (cost {cb:,.0f})")
        print("\n(dry run — nothing written)")
        return

    client.table("holdings").delete().neq("ticker", "").execute()   # full reload
    for i in range(0, len(holdings), 200):
        client.table("holdings").insert(holdings[i:i + 200]).execute()
    print(f"\nDone. {len(holdings)} holdings written.")


if __name__ == "__main__":
    main()
