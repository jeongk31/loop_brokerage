"""Carve family holdings out of 이정규's holdings (total conserved) + set cash.

Uses the `transfers` table: shares move from 이정규 to a family member at 이정규's
average cost, applied after holdings are derived from trades. Where the gift
exceeds what 이정규 holds (TQQQ), 이정규's position goes NEGATIVE — a deficit to
buy back to break even.

  이지안: QLD 5            (from 이정규 / 삼성증권)
  이정한: TQQQ 80 + $5,400 (from 이정규 / 삼성증권)
  엄마  : TQQQ 31 + NASA 10 + $2,520  (TQQQ from 삼성증권, NASA from IBKR)

Idempotent: clears family buy-transactions and prior transfers first.
Run AFTER migration 005.  python scripts/seed_family.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_client  # noqa: E402

NAMES = {"TQQQ": "ProShares UltraPro QQQ", "QLD": "ProShares Ultra QQQ",
         "NASA": "TEMA Space Innovators ETF"}
DATE = "2026-01-02"
CASH = [("이정한", "USD", 5400), ("엄마", "USD", 3820)]
DEST_PLATFORM = "삼성증권"   # family holdings land here


# (to_member, ticker, current_shares, from_platform) — carved from 이정규's holdings.
GIFTS = [
    ("이지안", "QLD", 10, "IBKR"),
    ("이정한", "TQQQ", 40, "삼성증권"),
    ("이정한", "QLD", 35, "IBKR"),
    ("엄마", "TQQQ", 16, "삼성증권"),
    ("엄마", "QLD", 14, "IBKR"),
    ("엄마", "NASA", 10, "IBKR"),
]


def main() -> None:
    c = get_client()
    users = {u["display_name"]: u["id"] for u in c.table("users").select("id, display_name").execute().data}
    plats = {p["name"]: p["id"] for p in c.table("platforms").select("id, name").execute().data}
    me = users["이정규"]
    dest = plats[DEST_PLATFORM]

    # 이정규's avg cost per source (platform, ticker), from current holdings.
    mine = {(h["platform_id"], h["ticker"]): float(h["avg_cost"])
            for h in c.table("holdings").select("platform_id, ticker, avg_cost").eq("user_id", me).execute().data}

    # Clean prior runs.
    fam_ids = [users[n] for n in ("이지안", "이정한", "엄마")]
    c.table("transactions").delete().in_("user_id", fam_ids).execute()  # remove old additive buys
    c.table("transfers").delete().neq("ticker", "").execute()

    rows = []
    for member, ticker, shares, from_plat in GIFTS:
        avg = mine.get((plats[from_plat], ticker), 0)
        rows.append({
            "ticker": ticker, "name": NAMES[ticker], "currency": "USD",
            "quantity": shares, "avg_cost": round(avg, 6),
            "from_user_id": me, "from_platform_id": plats[from_plat],
            "to_user_id": users[member], "to_platform_id": dest,
            "transfer_date": DATE, "note": "family allocation",
        })
    c.table("transfers").insert(rows).execute()
    print(f"Inserted {len(rows)} transfers.")
    for member, ticker, shares, fp in GIFTS:
        print(f"  {member} <- {shares} {ticker} @ ${mine.get((plats[fp], ticker),0):.2f} (from {fp})")

    for member, ccy, amt in CASH:
        c.table("cash_balances").upsert({"user_id": users[member], "currency": ccy, "amount": amt}).execute()
        print(f"  cash: {member} {amt} {ccy}")


if __name__ == "__main__":
    main()
