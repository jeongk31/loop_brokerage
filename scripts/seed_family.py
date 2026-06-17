"""Randomly reassign ownership of selected holdings from 이정규 to family.

Ownership-only: the shares physically stay in 이정규's real accounts; we just
reattribute a RANDOM slice of each (platform, ticker) to family members via the
`transfers` table. Every allocation is bounded by 이정규's actual position, so:

  - the grand total of each ticker always matches 이정규's physical holdings, and
  - no one (including 이정규) can ever go negative.

Scope = TQQQ, QLD, NASA (what family was previously gifted). GOOGL and every
other holding are intentionally left untouched. Idempotent: clears prior
transfers + family transactions for the in-scope tickers first (reversing the
cash from any deleted family trades).

Run AFTER migration 005:  python scripts/seed_family.py
"""
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402

TICKERS = ["TQQQ", "QLD", "NASA"]            # reassign these; leave GOOGL etc. alone
FAMILY = ["엄마", "이정한", "이지안"]
NAMES = {"TQQQ": "ProShares UltraPro QQQ", "QLD": "ProShares Ultra QQQ",
         "NASA": "TEMA Space Innovators ETF"}
DATE = "2026-01-02"
SEED = 20260617                               # deterministic: re-runs reproduce the same split
EPS = 1e-9


def physical_positions(c, jk) -> dict:
    """이정규's real (qty, avg) per (platform, ticker) for in-scope tickers.

    Split-adjusted, average-cost, long-only — i.e. what he actually holds.
    """
    splits: dict = defaultdict(list)
    for r in (c.table("stock_splits").select("ticker, ex_date, ratio").execute().data or []):
        splits[r["ticker"]].append((r["ex_date"], float(r["ratio"])))

    def adj(tk, td, q, p):
        for ex, ratio in splits.get(tk, ()):
            if td < ex:
                q *= ratio
                p /= ratio
        return q, p

    tx: dict = defaultdict(list)
    for t in (c.table("transactions")
              .select("platform_id,ticker,trade_date,side,quantity,price")
              .eq("user_id", jk).execute().data or []):
        if t["ticker"] in TICKERS:
            tx[(t["platform_id"], t["ticker"])].append(t)

    pos = {}
    for (pid, tk), trades in tx.items():
        q = avg = 0.0
        for t in sorted(trades, key=lambda x: x["trade_date"]):
            aq, ap = adj(tk, t["trade_date"], float(t["quantity"]), float(t["price"]))
            if t["side"] == "buy":
                avg = (q * avg + aq * ap) / (q + aq) if (q + aq) > EPS else ap
                q += aq
            else:
                q -= min(aq, q)
                if q < EPS:
                    q = avg = 0.0
        if q >= 1:
            pos[(pid, tk)] = (int(round(q)), round(avg, 6))
    return pos


def main() -> None:
    random.seed(SEED)
    c = get_client()
    users = {u["display_name"]: u["id"]
             for u in c.table("users").select("id, display_name").execute().data}
    plats = {p["id"]: p["name"]
             for p in c.table("platforms").select("id, name").execute().data}
    jk = users["이정규"]
    fam_ids = [users[n] for n in FAMILY]

    # 1. Clear prior allocations + family trades for the in-scope tickers only,
    #    reversing the cash that any deleted family trade had moved.
    c.table("transfers").delete().in_("ticker", TICKERS).execute()
    doomed = (c.table("transactions").select("*")
              .in_("user_id", fam_ids).in_("ticker", TICKERS).execute().data or [])
    for t in doomed:
        gross = float(t["quantity"]) * float(t["price"])
        delta = -gross if t["side"] == "sell" else gross   # undo: sell added cash, buy removed it
        cur = (c.table("cash_balances").select("amount")
               .eq("user_id", t["user_id"]).eq("currency", t["currency"]).execute().data)
        amt = (float(cur[0]["amount"]) if cur else 0.0) + delta
        c.table("cash_balances").upsert({"user_id": t["user_id"], "currency": t["currency"],
                                         "amount": round(amt, 2)}).execute()
    if doomed:
        (c.table("transactions").delete()
         .in_("user_id", fam_ids).in_("ticker", TICKERS).execute())

    # 2. Random ownership reassignment, per (platform, ticker), bounded by physical.
    #    Give away up to half of each position so it stays mostly 이정규's.
    pos = physical_positions(c, jk)
    rows = []
    for (pid, tk), (qty, avg) in sorted(pos.items(), key=lambda x: (x[0][1], plats.get(x[0][0], ""))):
        give = random.randint(qty // 4, qty // 2)          # how many shares leave 이정규
        alloc = {m: 0 for m in FAMILY}
        for _ in range(give):
            alloc[random.choice(FAMILY)] += 1
        for m, n in alloc.items():
            if n:
                rows.append({"ticker": tk, "name": NAMES.get(tk, tk), "currency": "USD",
                             "quantity": n, "avg_cost": avg,
                             "from_user_id": jk, "from_platform_id": pid,
                             "to_user_id": users[m], "to_platform_id": pid,
                             "transfer_date": DATE, "note": "random ownership reassignment"})
    if rows:
        c.table("transfers").insert(rows).execute()

    # 3. Report: prove totals match and no one is negative.
    print(f"Reassigned {len(rows)} ownership slices (seed={SEED}).")
    for (pid, tk), (qty, avg) in sorted(pos.items(), key=lambda x: x[0][1]):
        given = sum(r["quantity"] for r in rows if r["from_platform_id"] == pid and r["ticker"] == tk)
        detail = ", ".join(f"{users_inv(users, r['to_user_id'])} {r['quantity']}"
                           for r in rows if r["from_platform_id"] == pid and r["ticker"] == tk)
        print(f"  {plats.get(pid):10} {tk:6} total {qty:>4}  ->  이정규 keeps {qty-given:>4}, "
              f"family {given:>3} ({detail or '-'})")

    from app.services.holdings import rederive   # keep holdings table in sync now
    n = rederive()
    print(f"\nHoldings re-derived: {n} rows.")


def users_inv(users: dict, uid: str) -> str:
    for name, i in users.items():
        if i == uid:
            return name
    return "?"


if __name__ == "__main__":
    main()
